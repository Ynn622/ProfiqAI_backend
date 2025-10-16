import requests
import pandas as pd
import time
from bs4 import BeautifulSoup as bs
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

def get_udn_news(stock_id, page_limit=1) -> pd.DataFrame:
    """
    爬取 udn 指定股票的新聞資料，並返回包含新聞標題、網址、內容的 DataFrame。
    """
    data = []
    col = ["Date", "URL", "Title", "Content"]
    _, stock_name = fetchStockInfo(stock_id)
    stock_name = re.sub(r'[-*].*$', '', stock_name)  # 去除股票名稱中的特殊字符
    page = 1
    while 1:
        if page > page_limit:
            print(f"已達設定的頁數上限：{page-1}{' '*50}", end="\r")
            break
        url = f"https://udn.com/api/more?page={page}&id=search:{stock_name}%20{stock_id}&channelId=2&type=searchword&last_page=100"
        json_news = requests.get(url).json()['lists']
        if len(json_news) == 0:
            print(f"已經抓取到最後一頁：{page-1}{' '*50}", end="\r")
            break
        for i in range(len(json_news)):
            # print(f"抓取新聞中：{stock_name} - Page: {page} - {i+1}/{len(json_news)+1} ", end="")
            item = json_news[i]
            try:
                title = item['title']
                t = item['time']['date']
                news_time = datetime.strptime(t, "%Y-%m-%d %H:%M")
                # print(f"日期: {news_time}{' '*30}", end="\r")
                if time.mktime(time.gmtime())-30*24*3600>news_time.timestamp(): break  # 只抓最近30天的新聞
                news_url = item['titleLink']
                if not news_url.startswith("https://udn.com/news/story"): continue   # 非新聞頁面
                news = requests.get(news_url).text
                news_find = bs(news,'html.parser').find("section",class_="article-content__editor").find_all("p")[:-1]
                news_data = "\n".join(x.text.strip() for x in news_find)
                news_data = news_data.replace("\n\n","\n").strip()
                data.append([news_time, news_url, title, news_data])
            except Exception as e:
                print(f"抓取新聞錯誤：{e}", end="\r")
                continue
        page += 1
            
    df = pd.DataFrame(data, columns=col).set_index("Date")
    print(f"\rDone: 新聞資料-載入完畢！{' '*40}")
    return df

def stock_news_split_word(stock_id: str):
    """
    對指定股票的新聞內容 進行斷詞處理。
    """
    df = get_udn_news(stock_id, page_limit=1)  # 取得新聞資料
    text = ' '.join(df['Content'].dropna())
    clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', '', text)  # 移除非中文字、英文字母和數字
    cut_text = ' '.join(jieba.cut(clean_text))  # 斷詞
    filtered_words = [word for word in cut_text.split() if ((word not in stopwords_set) and (len(word) > 1))]
    word_counts = Counter(filtered_words)  # 計算詞頻
    threshold = max(4, len(filtered_words) // 700)
    filtered_counts = {word: count for word, count in word_counts.items() if count >= threshold}
    return df, filtered_counts
