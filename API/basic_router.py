from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from util.logger import log_print
from services.basic_data import get_PE_Ratio, get_revenue, get_EPS, get_profile, get_dividend

router = APIRouter(prefix="/basic", tags=["基本面 Basic"])

@router.get("/basicInfo")
@log_print
def basic_info(stock_id: str):
    """
    取得指定股票「基本面」資訊。
    """
    try:
        pe = get_PE_Ratio(stock_id)
        r = get_revenue(stock_id)
        eps = get_EPS(stock_id)
        pro = get_profile(stock_id)
        dividend = get_dividend(stock_id)

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