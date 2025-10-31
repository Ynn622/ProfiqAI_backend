from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from util.numpy_extension import nan_to_none
from util.logger import log_print

from services.function_util import fetchStockInfo, getStockPrice, get_live_stock_info

router = APIRouter(prefix="/stock", tags=["股價資料 Stock"])

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

@router.get("/checkStockExist")
@log_print
def check_stock_exist(stock_id: str):
    """
    檢查指定股票 是否存在。
    """
    try:
        stockID, stockName = fetchStockInfo(stock_id)
        return JSONResponse(content={'stockID': stockID, 'stockName': stockName})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
