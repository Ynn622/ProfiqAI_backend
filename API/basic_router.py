from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from util.logger import log_print
from services.basic_data import basic_info

router = APIRouter(prefix="/basic", tags=["基本面 Basic"])

@router.get("/score")
@log_print
def basic_score(stock_id: str):
    """
    取得指定股票「基本面」資訊。
    """
    try:
        data = basic_info(stock_id)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))