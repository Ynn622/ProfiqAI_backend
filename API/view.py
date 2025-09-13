from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np

from services.function_util import fetchStockInfo, getStockPrice, get_live_stock_info
from util.numpy_extension import nan_to_none
from util.logger import log_print

router = APIRouter(prefix="/View", tags=["View"])

@router.get("/stockData")
@log_print
def stock_data(stock_id: str, start_date: str = "2024-05-10"):
    """
    取得指定股票的歷史股價與籌碼面資料。
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
    取得指定股票的即時股價與相關資訊。
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
    檢查指定股票的基本資訊。
    """
    try:
        stockID, stockName = fetchStockInfo(stock)
        return JSONResponse(content={'stockID': stockID, 'stockName': stockName})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))