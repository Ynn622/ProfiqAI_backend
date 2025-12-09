from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from util.logger import log_print
from util.data_manager import DataManager
from util.stock_list import StockList
from services.basic_data import basic_info

router = APIRouter(prefix="/basic", tags=["基本面 Basic"])

@router.get("/score")
@log_print
def basic_score(stock_id: str):
    """
    取得指定股票「基本面」資訊。
    """
    from services.ai_generate import ask_AI
    
    try:
        cached = DataManager.get_score(stock_id, score_type="basic")
        if cached:
            return JSONResponse(content={"data": cached["data"]})

        _, stock_name = StockList.query(stock_id)
        data = basic_info(stock_id)
        
        payload_data = data.copy()
        # 移除不必要的欄位以簡化輸入給 AI
        for key in ['TotalScore']:
            data.pop(key, None)
        prompt = f"""以下是{stock_name}的基本面資料，請用繁體中文生成100字內快速摘要，去解釋評級:{data}"""
        data['ai_insight'] = ask_AI(prompt)
        payload_data['ai_insight'] = data['ai_insight']
        DataManager.save_score(
            stock_id=stock_id,
            data=payload_data,
            score_type="basic",
            direction=payload_data.get("direction"),
        )
        return JSONResponse(content={"data": payload_data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
