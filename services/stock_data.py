import pandas as pd
import requests
from bs4 import BeautifulSoup as bs
import yfinance as yf

from util.logger import Log, Color
from services.chip_data import get_chip_data
from services.tech_data import get_technical_indicators

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
        Log(f"🔴 [Error] 爬取即時股價資料錯誤: {str(e)}", color=Color.RED)
    
    # 指標計算
    if sdf_indicator_list:
        try:
            indicator_df = get_technical_indicators(data, sdf_indicator_list)
            data = pd.concat([data, indicator_df], axis=1)
        except Exception as e:
            Log(f"🔴 [Error] 指標計算錯誤: {str(e)}", color=Color.RED)
    
    data = data[data.index >= start]  # 確保資料從指定日期開始
    data = data.dropna().round(2)  # 移除包含NaN的行 
    
    # 籌碼面資料
    if chip_enable and symbol not in ("^TWII", "^TWOII"):
        try:
            chip_data = get_chip_data(symbol, data.index[0], data.index[-1]).reindex(data.index)
            data = pd.concat([data, chip_data], axis=1)
        except Exception as e:
            Log(f"🔴 [Error] 籌碼面資料錯誤: {str(e)}", color=Color.RED)

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

    nowtime = soup.find("time").find_all("span")[2].text
    nowtime = pd.to_datetime(nowtime).strftime("%Y-%m-%d")
    info['Date'] = nowtime
    info['StockName'] = soup.find('h1', class_='C($c-link-text) Fw(b) Fz(24px) Mend(8px) Whs(nw)').text

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
