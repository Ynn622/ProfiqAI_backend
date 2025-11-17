from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
from datetime import date, timedelta

from util.numpy_extension import nan_to_none
from util.logger import log_print

from services.function_util import get_margin_data, get_chip_data
from services.main_force_data import main_force_all_days

router = APIRouter(prefix="/chip", tags=["籌碼面 Chip"])

@router.get("/chipInfo")
@log_print
def chip_info(stock_id: str):
    """
    取得指定股票60天內「籌碼面」資料。 （三大法人、融資、融券）
    """
    today = date.today().strftime("%Y-%m-%d")
    sixty_days_ago = (date.today() - timedelta(days=60)).strftime("%Y-%m-%d")
    
    margin_data = get_margin_data(stock_id, start=sixty_days_ago, end=today)
    chip_data = get_chip_data(stock_id, start=sixty_days_ago, end=today)
    main_force_data = main_force_all_days(stock_id, margin_data.index.tolist())
    all_data = pd.concat([margin_data, chip_data, main_force_data], axis=1)
    all_data.sort_index(ascending=True, inplace=True)
    result = {
            "Date": all_data.index.tolist(),
            "MarginBuy": all_data["融資增減"].tolist(),
            "MarginSell": all_data["融券增減"].tolist(),
            "MarginRatio": all_data["融券券資比%"].tolist(),
            "Foreign": all_data["外資"].tolist(),
            "Dealer": all_data["投信"].tolist(),
            "Investor": all_data["自營商"].tolist(),
            "MainForce": all_data["主力買賣超"].tolist(),
        }
    result = nan_to_none(result)
    return result

@router.get("/score")
@log_print
def chip_score(stock_id: str):
    """
    取得股票「籌碼面」指標資訊
    """
    from services.chip_data import calculate_chip_indicators
    data = calculate_chip_indicators(stock_id)
    if data:
        return JSONResponse(content={"chip_data": data})
    else:
        return JSONResponse(content={"message": "無法取得籌碼面資訊"}, status_code=404)