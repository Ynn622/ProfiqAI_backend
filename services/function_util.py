import pandas as pd
from stockstats import StockDataFrame as Sdf
import cloudscraper
import requests
from bs4 import BeautifulSoup as bs
from datetime import datetime, timedelta
import yfinance as yf
import numpy as np
import re
import html
import time
from util.logger import printf, Color

def fetchStockInfo(stockName: str) -> str:
    """
    股票代號&名稱查詢。
    toolFetchStockInfo() 會自動調用此函數。
    """
    try:
        url = f"https://tw.stock.yahoo.com/_td-stock/api/resource/WaferAutocompleteService;view=wafer&query={stockName}"
        response = requests.get(url)
        stockID = bs(response.json()["html"], features="lxml").find("a")["href"].split('stock_id=')[1]
        stockName = bs(response.json()["html"], features="lxml").find("span").text
    except Exception as e:
        stockID = None
        stockName = None
    return stockID, stockName


def getStockPrice(symbol: str, start: str, sdf_indicator_list: list[str]=[] ) -> pd.DataFrame:
    """
    取得指定股票的歷史股價資料。
    toolGetStockPrice() 會自動調用此函數。
    """
    data = yf.Ticker(symbol).history(period="2y").round(2)
    del data["Dividends"], data["Stock Splits"]
    if "Capital Gains" in data.columns: del data["Capital Gains"]
    data.index = data.index.strftime("%Y-%m-%d")
    data["Volume"] = data["Volume"]*0.001  # 將成交量轉換為張數
    
    # 爬取現在即時股價資料
    try:
        live_df = get_live_price(symbol)
        data = data.drop(live_df.index[0], errors='ignore') 
        data = pd.concat([data, live_df])
    except Exception as e:
        printf(f"🔴 [Error] 爬取即時股價資料錯誤: {str(e)}", color=Color.RED)
    
    # 指標計算
    if sdf_indicator_list:
        indicator_df = get_technical_indicators(data, sdf_indicator_list)
        try:
            data = pd.concat([data, indicator_df], axis=1)
        except Exception as e:
            printf(f"🔴 [Error] 指標計算錯誤: {str(e)}", color=Color.RED)

    data = data[data.index >= start]  # 確保資料從指定日期開始
    data = data.dropna().round(2)  # 移除包含NaN的行 
    
    # 籌碼面資料
    if symbol not in ("^TWII", "^TWOII"):
        try:
            chip_data = get_chip_data(symbol, data.index[0], data.index[-1]).reindex(data.index)
            data = pd.concat([data, chip_data], axis=1)
        except Exception as e:
            printf(f"🔴 [Error] 籌碼面資料錯誤: {str(e)}", color=Color.RED)

    return data


def FetchStockNews(stock_name: str) -> pd.DataFrame:
    """
    爬取指定股票的最新新聞資料。
    toolFetchStockNews() 會自動調用此函數。
    """
    data = []
    col = ["Date","Title","Content"]
    url = f"https://ess.api.cnyes.com/ess/api/v1/news/keyword?q={stock_name}&limit=10&page=1"
    json_news = requests.get(url).json()['data']['items']
    for item in json_news:
        id = item['newsId']
        title = item['title']
        title = re.sub(r'<.*?>', '', title)
        if "盤中速報" in title:continue
        t = item['publishAt']+28800
        if time.mktime(time.gmtime())-2592000>t:continue
        news_time = time.strftime("%Y/%m/%d", time.gmtime(t))
        news_url = f"https://news.cnyes.com/news/id/{id}"
        news = requests.get(news_url).text
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
        data.append([news_time, title, news_data])
    return pd.DataFrame(data, columns=col)

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

def fetchETFIngredients(ETF_name: str) -> str:
    """
    查詢 ETF 的成分股。
    toolFetchETFIngredients() 會自動調用此函數。
    """
    url = f"https://tw.stock.yahoo.com/quote/{ETF_name}/holding"
    response = requests.get(url)
    soup = bs(response.text, "html.parser")
    table = soup.find_all("ul", class_="Bxz(bb) Bgc($c-light-gray) Bdrs(8px) P(20px)")[1].find_all("li")[1:]
    data = ""
    for i in table:
        data += i.text.strip() + "\n"
    return data

''' 下方為輔助函數 '''

def get_technical_indicators(data, sdf_indicator_list):
    """
    計算技術指標
    Args:
        data(DataFrame): 股價歷史資料
        sdf_indicator_list (list): 欲計算的技術指標清單
    """
    indicator_dict = {
        'close_5_sma':'SMA_5',
        'close_10_sma':'SMA_10',
        'close_20_sma':'SMA_20',
        'close_60_sma':'SMA_60',
        'close_5_ema':'EMA_5',
        'close_10_ema':'EMA_10',
        'close_20_ema':'EMA_20',
        'macd': 'MACD',
        'macds': 'Signal Line',
        'macdh': 'Histogram',
        'kdjk': '%K',
        'kdjd': '%D',
        'rsi_5': 'RSI_5',
        'rsi_10': 'RSI_10',
        'close_5_roc': 'ROC',
        'boll_ub': 'BOLL_UPPER',
        'boll': 'BOLL_MIDDLE',
        'boll_lb': 'BOLL_LOWER',
        'change': 'PCT'
    }

    # 計算技術指標
    stock_df = Sdf.retype(data)
    indicator_data = stock_df[sdf_indicator_list].copy()
    indicator_data.rename(columns=indicator_dict, inplace=True)  # 將指標名稱轉換
    indicator_data = indicator_data.round(2)
    
    return indicator_data


def get_live_price(symbol: str) -> pd.DataFrame:
    """
    用於取得最新即時股價資料。
    get_stock_price() 會自動調用此函數。
    """
    header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
    url = f"https://tw.stock.yahoo.com/quote/{symbol}"
    web = requests.get(url,headers=header,timeout=5)
    bs_web = bs(web.text,"html.parser")
    table = bs_web.find("ul",class_="D(f) Fld(c) Flw(w) H(192px) Mx(-16px)").find_all("li")
    name = ["Close","Open","High","Low","Volume"]
    dic = {}
    s_list = [0,1,2,3,5 if symbol in ("^TWII", "^TWOII") else 9]  # 大盤&櫃買 抓取欄位不同
    for i in range(5):
        search = s_list[i]
        row = float(table[search].find_all("span")[1].text.replace(",",""))
        dic[name[i]]=[row]
    nowtime = bs_web.find("time").find_all("span")[2].text
    nowtime = pd.to_datetime(nowtime).strftime("%Y-%m-%d")
    return pd.DataFrame(dic, index=[nowtime])

 
def get_chip_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    用於取得最新籌碼面資料。
    get_stock_price() 會自動調用此函數。
    """
    if symbol in ("^TWII", "^TWOII"):
        printf(f"[function] get_chip_data(): 不提供籌碼面資料: {symbol}", color=Color.PURPLE)
        return pd.DataFrame()
    symbol = symbol.split(".")[0]  # 去除後綴
    url = f"https://fubon-ebrokerdj.fbs.com.tw/z/zc/zcl/zcl.djhtm?a={symbol}&c={start}&d={end}"
    scraper = cloudscraper.create_scraper()  # 使用 cloudscraper 爬取
    web = scraper.get(url).text
    bs_table = bs(web, "html.parser").find("table", class_="t01").find_all("tr")[7:-1]  # 跳過前7行和最後一行
    col = ["外資", "投信", "自營商", "三大法人合計"]
    data = []
    date_index = []
    for i in bs_table[::-1]: # 反向遍歷，因為最新的資料在最後一行
        tds = i.find_all("td")[:5]
        date = tds.pop(0).text.split('/')   # 取出日期

        texts = [td.text.strip() for td in tds]
        # 偵測是否有 '--'
        if any(text == '--' for text in texts):
            continue  # 不繼續處理這筆資料
        # 正常處理數字
        row = [int(text.replace(",", "")) for text in texts]
        data.append(row)
        # 處理日期
        date_str = f"{int(date[0])+1911}-{date[1]}-{date[2]}"
        date_index.append(date_str)
    df = pd.DataFrame(data, columns=col, index=date_index)
    return df


def get_live_stock_info(stockID: str) -> dict:
    """
    用於取得最新即時股價資料與相關資訊。
    """
    quoteWeb = requests.get(f'https://tw.stock.yahoo.com/quote/{stockID}')
    soup = bs(quoteWeb.text, "html.parser")

    info = {}

    nowtime = soup.find("time").find_all("span")[2].text
    nowtime = pd.to_datetime(nowtime).strftime("%Y-%m-%d")
    info['Date'] = nowtime
    info['StockName'] = soup.find('h1', class_='C($c-link-text) Fw(b) Fz(24px) Mend(8px)').text

    priceTable = soup.find("ul",class_="D(f) Fld(c) Flw(w) H(192px) Mx(-16px)").find_all("li")
    dic = {'Close': 0,
        'Open': 1,
        'High': 2,
        'Low': 3,
        'Volume': 5 if stockID in ("^TWII", "^TWOII") else 9,
        'Change': 8,
        'ChangePct': 7,
        'PreClose': 6}

    for key, value in dic.items():
        row = float(priceTable[value].find_all("span")[1].text.replace(",","").replace("%",""))
        dic[key] = row

    info.update(dic)

    info['Trend'] = True if info['PreClose']<info['Close'] else False
    return info
