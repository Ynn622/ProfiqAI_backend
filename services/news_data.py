import requests
import pandas as pd
import re
from datetime import datetime
import jieba
from collections import Counter

from services.function_util import fetchStockInfo

stopwords_set = set()       # 停用詞集合

with open("data/stopWords_TW.txt", 'r', encoding='utf-8') as f:
    stopwords_set = { line.strip() for line in f if line.strip() }

with open("data/stockName.txt", "r", encoding="utf-8") as f:
    for line in f: 
        jieba.add_word(line.strip())  # 將公司名稱加入 jieba 詞庫

def news_summary(stock_id: str, page: int=1) -> pd.DataFrame:
    """
    爬取 udn新聞網 及 cnyes鉅亨網 指定股票的新聞摘要。
    Returns:
        DataFrame: 時間戳、新聞標題、摘要、網址、來源。
    """
    _, stockName = fetchStockInfo(stock_id)

    udn_df = get_udn_news_summary(f'{stockName} {stock_id}', page=page)
    cnyes_df = get_cnyes_news_summary(stock_id, page=page)

    df = pd.concat([udn_df, cnyes_df], ignore_index=True)
    df.sort_values(by='TimeStamp', ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

def get_udn_news_summary(keyword, page=1) -> pd.DataFrame:
    """
    爬取 udn新聞網 指定股票的新聞資料「摘要」。
    Returns:
        DataFrame: 時間戳、新聞標題、摘要、網址、來源。
    """
    data = []
    col = ["TimeStamp", "Title", "Summary", "Url", "Source"]

    udn_url = f"https://udn.com/api/more?page={page}&id=search:{keyword}&channelId=2&type=searchword&last_page=100"
    udn_json_news = requests.get(udn_url).json()['lists']
    for item in udn_json_news:
        url = item['titleLink']
        title = item['title']
        summary = item['paragraph']
        time_str = item['time']['dateTime']
        timestamp = int(datetime.strptime(time_str, "%Y-%m-%d %H:%M").timestamp())   # 轉成時間戳（單位：秒）
        data.append([timestamp, title, summary, url, 'udn'])
    return pd.DataFrame(data, columns=col)

def get_cnyes_news_summary(keyword, page=1) -> pd.DataFrame:
    """
    爬取 cnyes鉅亨網 指定股票的新聞資料「摘要」。
    Returns:
        DataFrame: 時間戳、新聞標題、摘要、網址、來源。
    """
    data = []
    col = ["TimeStamp", "Title", "Summary", "Url", "Source"]

    cnyes_url = f"https://ess.api.cnyes.com/ess/api/v1/news/keyword?q={keyword}&limit=20&page={page}"
    cnyes_json_news = requests.get(cnyes_url).json()['data']['items']
    for item in cnyes_json_news:
        id = item['newsId']
        url = f"https://news.cnyes.com/news/id/{id}"
        title = item['title'].replace('⊕','*')
        title = re.sub(r'<.*?>', '', title)
        if "盤中速報" in title: continue   # 跳過指定關鍵字
        timestamp = item['publishAt']+28800
        summary = item['summary']
        data.append([timestamp, title, summary, url, 'cnyes'])
    return pd.DataFrame(data, columns=col)


def stock_news_split_word(stock_id: str):
    """
    對指定股票的新聞內容 進行斷詞處理。
    """
    from services.function_util import FetchStockNews
    df = FetchStockNews(stock_id, num=15)  # 取得新聞資料
    text = ' '.join(df['Content'].dropna())
    clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', '', text)  # 移除非中文字、英文字母和數字
    cut_text = ' '.join(jieba.cut(clean_text))  # 斷詞
    filtered_words = [word for word in cut_text.split() if ((word not in stopwords_set) and (len(word) > 1) and (not word.isdigit()))]
    word_counts = Counter(filtered_words)  # 計算詞頻
    threshold = max(4, len(filtered_words) // 700)
    filtered_counts = {word: count for word, count in word_counts.items() if count >= threshold}
    return df, filtered_counts
