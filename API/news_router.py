from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from util.logger import log_print
from util.nowtime import TaiwanTime

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