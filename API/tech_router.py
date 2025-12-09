from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from util.logger import log_print
from util.data_manager import DataManager
from util.stock_list import StockList

router = APIRouter(prefix="/tech", tags=["技術面 Tech"])

@router.get("/score")
@log_print
def tech_score(stock_id: str):
    """
    取得股票「技術面」指標資訊
    """
    from services.tech_data import calculate_technical_indicators
    from services.ai_generate import ask_AI
    from util.score_utils import split_scores_by_sign

    try:
        cached = DataManager.get_score(
            stock_id=stock_id,
            score_type="tech",
        )
        if cached:
            return JSONResponse(content={"data": cached["data"]})

        summary, history_tech_df = calculate_technical_indicators(stock_id)
        
        summary_dict = summary.copy()
        _, stock_name = StockList.query(stock_id)
        # 移除不必要的欄位以簡化輸入給 AI
        for key in ['TotalScore', 'accurate', 'result', 'EMA_Score', 'MACD_Score', 'KD_Score', 'RSI_Score', 'ROC_Score', 'SMA_Score', 'BIAS_Score']:
            summary_dict.pop(key, None)
        history_payload = history_tech_df[:10]
        prompt = f"""以下是{stock_name}的技術面資料，請用繁體中文生成100字內快速摘要，去解釋評級與走勢:{ {'資料摘要': summary_dict, '近期走勢': history_payload} }"""
        summary["score_distribution"] = split_scores_by_sign(summary)
        summary["ai_insight"] = ask_AI(prompt)
        DataManager.save_score(
            stock_id=stock_id,
            data=summary,
            score_type="tech",
            direction=summary.get("direction"),
        )
        return JSONResponse(content={"data": summary})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))