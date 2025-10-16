from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
from datetime import date, timedelta

from util.numpy_extension import nan_to_none
from util.logger import log_print
from util.nowtime import getTaiwanTime

from services.function_util import fetchStockInfo, getStockPrice, get_live_stock_info, get_margin_data, get_chip_data
from services.basic_data import get_PE_Ratio, get_revenue, get_EPS, get_profile, get_dividend
from services.news_data import stock_news_split_word

router = APIRouter(prefix="/View", tags=["View"])

@router.get("/stockData")
@log_print
def stock_data(stock_id: str, start_date: str = "2024-05-10"):
    """
    取得指定股票 股價資料表。
    """
    try:
        stockID, stockName = fetchStockInfo(stock_id)
        stock_data = getStockPrice(stockID, start_date)
        result = {
            "Date": stock_data.index.tolist(),
            "OHLC": stock_data[["Open", "High", "Low", "Close"]].values.tolist(),
            "Volume": stock_data["Volume"].tolist(),
            "Foreign": stock_data["外資"].tolist(),
            "Dealer": stock_data["投信"].tolist(),
            "Investor": stock_data["自營商"].tolist(),
            "MainForce": [0] * len(stock_data),
        }
        result = nan_to_none(result)
        return JSONResponse(content={'stockID': stockID, 'stockName': stockName, 'data': result})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/liveStockInfo")
@log_print
def stock_info(stock_id: str):
    """
    取得指定股票 即時股價OHLC＆漲跌幅。
    """
    try:
        info = get_live_stock_info(stock_id)
        return JSONResponse(content={'stockID': stock_id, 'info': info})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/checkStockInfo")
@log_print
def check_stock_info(stock: str):
    """
    檢查指定股票 是否存在。
    """
    try:
        stockID, stockName = fetchStockInfo(stock)
        return JSONResponse(content={'stockID': stockID, 'stockName': stockName})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/section/basicInfo")
@log_print
def basic_info(stockID: str):
    """
    取得指定股票「基本面」資訊。
    """
    try:
        pe = get_PE_Ratio(stockID)
        r = get_revenue(stockID)
        eps = get_EPS(stockID)
        pro = get_profile(stockID)
        dividend = get_dividend(stockID)

        basic_data = {**pe, **pro}

        basic_data["eps"] = eps["eps"][0]
        basic_data["epsGap"] = round(eps["eps"][0]-eps["eps"][1],2)
        basic_data["MoM"] = r["mom"][0]
        basic_data["YoY"] = r["yoy"][0]
        basic_data["stockSplits"] = dividend["capitalGains"][0]
        basic_data["dateDividend"] = dividend["date"][0]

        json_data = {
            "basicData": basic_data,
            "revenue": r,
            "eps": eps,
            "dividend": dividend,
        }
        return JSONResponse(content=json_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/section/chipInfo")
@log_print
def chip_info(stockID: str):
    """
    取得指定股票「籌碼面」資料。 （三大法人、融資、融券）
    """
    today = date.today().strftime("%Y-%m-%d")
    sixty_days_ago = (date.today() - timedelta(days=60)).strftime("%Y-%m-%d")
    
    margin_data = get_margin_data(stockID, start=sixty_days_ago, end=today)
    chip_data = get_chip_data(stockID, start=sixty_days_ago, end=today)
    all_data = pd.concat([margin_data, chip_data], axis=1)
    all_data.sort_index(ascending=True, inplace=True)
    result = {
            "Date": all_data.index.tolist(),
            "MarginBuy": all_data["融資增減"].tolist(),
            "MarginSell": all_data["融券增減"].tolist(),
            "MarginRatio": all_data["融券券資比%"].tolist(),
            "Foreign": all_data["外資"].tolist(),
            "Dealer": all_data["投信"].tolist(),
            "Investor": all_data["自營商"].tolist(),
        }
    result = nan_to_none(result)
    return result

@router.get("/news/wordCloud")
@log_print
def news_word_cloud(stockID: str):
    """
    取得指定股票「新聞」資料的詞雲。
    """
    all_data, filtered_counts = stock_news_split_word(stockID)
    return JSONResponse(content={'wordCounts': filtered_counts, 'updateTime': getTaiwanTime()})