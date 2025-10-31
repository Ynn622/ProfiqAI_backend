from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from util.logger import log_print

from services.predict import predict_future

router = APIRouter(prefix="/predict", tags=["預測相關 Predict"])

@router.get("/futureUpProb")
@log_print
def predict_future_up_prob(stock_id: str):
    """
    預測指定股票未來1天上漲機率。
    """
    prob_up = predict_future(stock_id)
    return JSONResponse(content={'stockID': stock_id, 'futureUpProb': prob_up})