import requests
import pandas as pd
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import jieba
from collections import Counter
from bs4 import BeautifulSoup as bs
import html
import time

from util.config import Env  # 確保環境變數被載入

stopwords_set = set()       # 停用詞集合

with open("data/stopWords_TW.txt", 'r', encoding='utf-8') as f:
    stopwords_set = { line.strip() for line in f if line.strip() }

with open("data/stockName.txt", "r", encoding="utf-8") as f:
    for line in f: 
        jieba.add_word(line.strip())  # 將公司名稱加入 jieba 詞庫


def FetchStockNews(stock_name: str, num: int = 10) -> pd.DataFrame:
    """
    爬取指定股票的最新新聞資料。
    toolFetchStockNews() 會自動調用此函數。
    """
    from services.news_data import get_udn_news_summary
    from services.stock_data import fetchStockInfo
    
    stock_id, stockName = fetchStockInfo(stock_name)
    stock_id = stock_id.split('.')[0]
    stockName = re.sub(r'[-*].*$', '', stockName)  # 去除股票名稱中的特殊字符
    
    udn_df = get_udn_news_summary(f'{stockName} {stock_id}')[:num]
    
    two_months_ago = time.time() - 60 * 24 * 3600
    udn_df = udn_df[udn_df['TimeStamp'] >= two_months_ago]
    urls = udn_df['Url'].tolist()[:num]

    news_content = []
    for i, url in enumerate(urls):
        if Env.RELOAD: print(f"抓取新聞中 - {i+1}/{len(urls)} ", end="\r")  # debug 時 顯示進度
        try:
            news = requests.get(url).text
            news_find = bs(news,'html.parser').find("section",class_="article-content__editor").find_all("p")[:-1]
            news_data = "\n".join(x.text.strip() for x in news_find)
            news_data = news_data.replace("\n\n","\n").strip()
            news_content.append(news_data)
        except Exception as e:
            print(f"🔴 [Error] 抓取新聞錯誤：{e}")
            news_content.append('')
            continue
    udn_df['Content'] = news_content
    udn_df['Date'] = udn_df['TimeStamp'].apply(lambda x: datetime.fromtimestamp(x).strftime("%Y-%m-%d %H:%M"))  # 轉換 時間戳->日期
    return udn_df[['Date', 'Title', 'Content']]

def FetchTwiiNews() -> pd.DataFrame:
    """
    爬取台灣加權指數(^TWII)與櫃買市場(^TWOII)的最新新聞。
    toolFetchTwiiNews() 會自動調用此函數。
    """
    data = []
    col = ["Date","Title","Content"]
    start = datetime.now()
    end = start - timedelta(days=1)
    start = end - timedelta(days=20)
    url = f"https://api.cnyes.com/media/api/v1/newslist/category/tw_quo?page=1&limit=15&startAt={int(start.timestamp())}&endAt={int(end.timestamp())}"
    web = requests.get(url).json()['items']
    json_news = web['data']
    for i in range(web['to']-web['from']+1):
        content = json_news[i]["content"]
        content = re.sub(r'<.*?>', '', html.unescape(content))
        if content.find("http")!=-1:
            content = content[:content.find("http")]
        title = json_news[i]["title"]
        title = re.sub(r"^〈.*?〉", "", title)
        timestamp = json_news[i]["publishAt"]+28800
        news_time = time.strftime("%Y/%m/%d %H:%M", time.gmtime(timestamp))
        data.append([news_time,title,content])
    return pd.DataFrame(data,columns=col)

def news_summary(stock_id: str, page: int=1) -> pd.DataFrame:
    """
    爬取 udn新聞網 及 cnyes鉅亨網 指定股票的新聞摘要。
    Returns:
        DataFrame: 時間戳、新聞標題、摘要、網址、來源。
    """
    from services.stock_data import fetchStockInfo
    _, stockName = fetchStockInfo(stock_id)

    udn_df = get_udn_news_summary(f'{stockName} {stock_id}', page=page)
    cnyes_df = get_cnyes_news_summary(stockName, page=page)

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
        timestamp = int(datetime.strptime(time_str, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Taipei")).timestamp())   # 轉成時間戳（單位：秒）
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
        timestamp = item['publishAt']
        summary = item['summary']
        data.append([timestamp, title, summary, url, 'cnyes'])
    return pd.DataFrame(data, columns=col)


def stock_news_split_word(stock_id: str):
    """
    對指定股票的新聞內容 進行斷詞處理。
    """
    from services.news_data import FetchStockNews
    df = FetchStockNews(stock_id, num=15)  # 取得新聞資料
    text = ' '.join(df['Content'].dropna())
    clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', '', text)  # 移除非中文字、英文字母和數字
    cut_text = ' '.join(jieba.cut(clean_text))  # 斷詞
    filtered_words = [word for word in cut_text.split() if ((word not in stopwords_set) and (len(word) > 1) and (not word.isdigit()))]
    word_counts = Counter(filtered_words)  # 計算詞頻
    threshold = max(4, len(filtered_words) // 700)
    filtered_counts = {word: count for word, count in word_counts.items() if count >= threshold}
    return df, filtered_counts
