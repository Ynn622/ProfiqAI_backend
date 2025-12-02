import pandas as pd
import requests
from bs4 import BeautifulSoup as bs
import yfinance as yf

from util.logger import Log, Color
from util.nowtime import TaiwanTime
from util.stock_list import StockList
from services.chip_data import get_chip_data
from services.tech_data import get_technical_indicators


def getStockPrice(symbol: str, start: str, sdf_indicator_list: list[str]=[], chip_enable: bool = True) -> pd.DataFrame:
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
        Log(f"[StockData] 爬取即時股價資料錯誤: {str(e)}", color=Color.RED)
    
    # 指標計算
    if sdf_indicator_list:
        try:
            indicator_df = get_technical_indicators(data, sdf_indicator_list)
            data = pd.concat([data, indicator_df], axis=1)
        except Exception as e:
            Log(f"[StockData] 指標計算錯誤: {str(e)}", color=Color.RED)
    
    data = data[data.index >= start]  # 確保資料從指定日期開始
    data = data.dropna().round(2)  # 移除包含NaN的行 
    
    # 籌碼面資料
    if chip_enable and symbol not in ("^TWII", "^TWOII"):
        try:
            chip_data = get_chip_data(symbol, data.index[0], data.index[-1]).reindex(data.index)
            data = pd.concat([data, chip_data], axis=1)
        except Exception as e:
            Log(f"[StockData] 籌碼面資料錯誤: {str(e)}", color=Color.RED)

    return data


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

 
def get_live_stock_info(stockID: str) -> dict:
    """
    用於取得最新即時股價資料與相關資訊。
    """
    quoteWeb = requests.get(f'https://tw.stock.yahoo.com/quote/{stockID}')
    soup = bs(quoteWeb.text, "html.parser")

    info = {}
    try:
        nowtime = soup.find("time").find_all("span")[2].text
        nowtime = pd.to_datetime(nowtime).strftime("%Y-%m-%d")
    except Exception as e:
        Log(f"[StockData] 無更新時間: {str(e)}", color=Color.YELLOW)
        nowtime = TaiwanTime().now().strftime("%Y-%m-%d")
    info['date'] = nowtime
    info['stockName'] = soup.find('h1', class_='C($c-link-text) Fw(b) Fz(24px) Mend(8px) Whs(nw)').text
    info['stockID'] = stockID

    priceTable = soup.find("ul",class_="D(f) Fld(c) Flw(w) H(192px) Mx(-16px)").find_all("li")
    dic = {'close': 0,
        'open': 1,
        'high': 2,
        'low': 3,
        'volume': 5 if stockID in ("^TWII", "^TWOII") else 9,
        'change': 8,
        'pct': 7,
        'preClose': 6}

    for key, value in dic.items():
        row = priceTable[value].find_all("span")[1].text.replace(",", "").replace("%", "")
        dic[key] = float(row) if row != '-' else None

    info.update(dic)
    # 判斷漲跌趨勢（先檢查有值）
    if info['close'] is None or info['preClose'] is None:
        info['trend'] = 0
    else:
        diff = info['close'] - info['preClose']
        info['trend'] = 1 if diff > 0 else -1 if diff < 0 else 0

    return info

def calculate_cumulative_return(symbol: str, target_month: int, price_mode: bool = False) -> pd.DataFrame:
    """
    計算指定股票 在特定月份的累計報酬率。
    Args:
        symbol (str): 股票代號或名稱。
        target_month (int): 目標月份（1-12）。
        price_mode (bool): 是否回傳價格資料（True）或報酬率（False）。
    Returns:
        pd.DataFrame: 包含指定月份價格或累計報酬率的 Data
    """
    stock_id, stock_name = StockList.query(symbol)
    df = yf.Ticker(stock_id).history(period="5y").round(2)
    df_same_month = df[(df.index.month == target_month) & (df.index.year>TaiwanTime.now().year-5)][['Close']]

    # 取 年份＆月份
    df_same_month['Year'] = df_same_month.index.year
    df_same_month['Month'] = df_same_month.index.month

    # 交易日序號
    df_same_month['TradeDay'] = df_same_month.groupby('Year').cumcount() + 1

    # pivot 成折線圖格式（不會有 NaN → 不會斷線）
    pivot = df_same_month.pivot(index='TradeDay', columns='Year', values='Close')
    
    if price_mode: return pivot.round(4)

    # 與第一天相比的累計報酬率
    base = pivot.iloc[0]           # 第一行（第 1 天）
    cumulative = pivot / base - 1  # 計算相對第一天的報酬率

    return cumulative.round(4)
