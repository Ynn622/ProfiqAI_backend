from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from util.logger import log_print
from util.data_manager import DataManager

router = APIRouter(prefix="/tech", tags=["技術面 Tech"])

@router.get("/score")
@log_print
def tech_score(stock_id: str):
    """
    取得股票「技術面」指標資訊
    """
    from services.tech_data import calculate_technical_indicators
    from services.ai_generate import ask_AI

    cached = DataManager.get_score(
        stock_id=stock_id,
        score_type="tech",
    )
    if cached:
        return JSONResponse(content=cached["data"])

    summary, history_tech_df = calculate_technical_indicators(stock_id)
    
    if summary:
        summary_dict = summary.copy()
        # 移除不必要的欄位以簡化輸入給 AI
        for key in ['TotalScore', 'accurate', 'result', 'EMA_Score', 'MACD_Score', 'KD_Score', 'RSI_Score', 'ROC_Score', 'SMA_Score', 'BIAS_Score']:
            summary_dict.pop(key, None)
        history_payload = history_tech_df.reset_index().to_dict(orient="records")
        prompt = f"""這是個股技術面資料，請你依據資料去簡單解釋最後的評級，字數100內:{ {'資料摘要': summary_dict, '近期走勢': history_payload[:5]} }"""
        summary["ai_insight"] = ask_AI(prompt)
        DataManager.save_score(
            stock_id=stock_id,
            data={"technical_data": summary},
            score_type="tech",
            direction=summary.get("direction"),
        )
        return JSONResponse(content={"technical_data": summary})
    else:
        return JSONResponse(content={"message": "無法取得技術面資訊"}, status_code=404)
