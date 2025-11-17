from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from util.logger import log_print

router = APIRouter(prefix="/tech", tags=["技術面 Tech"])

@router.get("/score")
@log_print
def tech_score(stock_id: str):
    """
    取得股票「技術面」指標資訊
    """
    from services.tech_data import calculate_technical_indicators
    data = calculate_technical_indicators(stock_id)
    if data:
        return JSONResponse(content={"technical_data": data})
    else:
        return JSONResponse(content={"message": "無法取得技術面資訊"}, status_code=404)