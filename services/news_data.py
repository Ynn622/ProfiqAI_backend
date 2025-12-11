import requests
import pandas as pd
import re
from datetime import datetime, timedelta
import jieba
from collections import Counter
from bs4 import BeautifulSoup as bs
import html
import time

from util.nowtime import TaiwanTime
from util.logger import Log, Color
from util.stock_list import StockList

stopwords_set = set()       # 停用詞集合

with open("data/stopWords_TW.txt", 'r', encoding='utf-8') as f:
    stopwords_set = { line.strip() for line in f if line.strip() }

with open("data/stockName.txt", "r", encoding="utf-8") as f:
    for line in f: 
        jieba.add_word(line.strip())  # 將公司名稱加入 jieba 詞庫


def FetchStockNews(stock_name: str, num: int = 10, include_url: bool=False) -> pd.DataFrame:
    """
    爬取指定股票的最新新聞資料。
    toolFetchStockNews() 會自動調用此函數。
    """
    from services.news_data import get_udn_news_summary
    
    stock_id, stockName = StockList.query(stock_name)
    stock_id = stock_id.split('.')[0]
    stockName = re.sub(r'[-*].*$', '', stockName)  # 去除股票名稱中的特殊字符
    
    udn_df = get_udn_news_summary(f'{stockName} {stock_id}')[:num]
    
    two_months_ago = time.time() - 60 * 24 * 3600
    udn_df = udn_df[udn_df['TimeStamp'] >= two_months_ago]
    urls = udn_df['Url'].tolist()[:num]

    # 先批次取得所有 URL 的快取資料
    from util.data_manager import DataManager
    cached_news = {}
    for url in urls:
        cached = DataManager.get_news_score(url=url)
        if cached and cached.get("content"):
            cached_news[url] = cached.get("content")

    news_content = []
    for i, url in enumerate(urls):
        Log(f"[新聞爬取] 進度 - {i+1}/{len(urls)} ", end="\r", reload_only=True)  # debug 時 顯示進度
        
        # 檢查是否有快取
        if url in cached_news:
            article = cached_news[url]
        else:
            # 沒有快取才去爬取
            article = parse_article(url, source='udn')
        
        news_content.append(article)
    Log(f"[新聞爬取] 抓取完成！{' '*20}", end="\r", color=Color.GREEN, reload_only=True)
    udn_df['Content'] = news_content
    udn_df['Date'] = udn_df['TimeStamp'].apply(lambda x: datetime.fromtimestamp(x).strftime("%Y-%m-%d %H:%M"))  # 轉換 時間戳->日期
    col = ['Date', 'Title', 'Content']
    if include_url: col.append('Url')
    return udn_df[col]

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
    _, stockName = StockList.query(stock_id)

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
        if not url.startswith('https://udn.com/news'): continue  # 跳過專欄文章
        title = item['title']
        summary = item['paragraph']
        time_str = item['time']['dateTime']
        timestamp = int(datetime.strptime(time_str, "%Y-%m-%d %H:%M").replace(tzinfo=TaiwanTime.TIMEZONE).timestamp())   # 轉成時間戳（單位：秒）
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


def parse_article(url: str, source: str='udn') -> str:
    """
    爬取指定新聞網址的完整內容。
    Args:
        url (str): 新聞網址
        source (str): 新聞來源，預設為 'udn'。可選擇 'udn' 或 'cnyes'。
    Returns:
        str: 新聞內容文字
    """
    
    try:
        if source == 'udn':
            news = requests.get(url).text
            news_find = bs(news,'html.parser').find("section",class_="article-content__editor").find_all("p")[:-1]
            news_data = "\n".join(x.text.strip() for x in news_find)
            news_data = news_data.replace("\n\n","\n").strip()
            return news_data
        elif source == 'cnyes':
            news = requests.get(url).text
            news_bs = bs(news,'html.parser')
            news_find = news_bs.find("main",class_="c1tt5pk2")
            news_data = "\n".join(x.text.strip() for x in news_find)
            news_data = news_data.replace("　　　","").replace("\n\n","")
            delete_strings = ["歡迎免費訂閱", "精彩影片","粉絲團", "Line ID","Line@","來源："]
            for delete_str in delete_strings:
                index = news_data.find(delete_str)
                if index != -1:
                    news_data = news_data[:index]  # 只保留不包含該字串的部分
                    break
            return news_data
    except Exception as e:
        Log(f"[新聞爬取] 錯誤：{e}", color=Color.RED)
    return ""


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
