from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from util.logger import log_print
from util.nowtime import TaiwanTime
from util.data_manager import DataManager

from services.news_data import stock_news_split_word, news_summary

router = APIRouter(prefix="/news", tags=["新聞資料 News"])

@router.get("/wordCloud")
@log_print
def news_word_cloud(stock_id: str):
    """
    取得指定股票「新聞」資料的詞雲。
    """
    all_data, filtered_counts = stock_news_split_word(stock_id)
    return JSONResponse(content={'wordCounts': filtered_counts, 'updateTime': TaiwanTime.string()})

@router.get("/summary")
@log_print
def get_all_news_summary(stock_id: str, page: int = 1):
    """
    取得指定股票「新聞」資料的摘要。
    """
    news_summary_df = news_summary(stock_id, page=page)
    result = news_summary_df.to_dict(orient='records')
    return JSONResponse(content={'news': result, 'updateTime': TaiwanTime.string()})

@router.get("/score")
@log_print
def news_score(stock_id: str):
    """
    取得指定股票「新聞」資料的情感分數。
    """
    from services.news_sentiment import total_news_sentiment
    from services.ai_generate import ask_AI
    from services.stock_data import fetchStockInfo
    try:
        _, stock_name = fetchStockInfo(stock_id)
        sentiment_scores = total_news_sentiment(stock_id, page=1)
        contents = sentiment_scores.get("contents", [])
        sentiment_scores.pop("contents", None)
        ai_insight = None
        if contents:
            prompt = f"以下是{stock_name}近期新聞內文，請用繁體中文生成100字內快速摘要，不要重述原文，不描述基本面資訊，聚焦重點：\n{contents}"
            ai_insight = ask_AI(prompt)
            sentiment_scores["ai_insight"] = ai_insight

        DataManager.save_score(
            stock_id=stock_id,
            data=sentiment_scores,
            score_type="news",
            direction=sentiment_scores.get("direction"),
        )
        return JSONResponse(sentiment_scores)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
