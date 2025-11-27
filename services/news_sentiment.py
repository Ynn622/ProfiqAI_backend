import pandas as pd
import time
from transformers import BertTokenizer, BertForSequenceClassification
import torch
import gc

from util.config import Env  # 確保環境變數被載入
from util.data_manager import DataManager
from services.news_data import get_udn_news_summary, parse_article

# 模型 (HuggingFace 路徑)
model_name = "Ynn22/news_model"
tokenizer = BertTokenizer.from_pretrained(model_name)
model = BertForSequenceClassification.from_pretrained(model_name)

@torch.no_grad()
def predict_sentiment(text: str) -> torch.Tensor:
    """
    預測新聞的情感分數
    Args:
        text (str): 新聞文本
    Returns:
        torch.Tensor: 三分類的機率分數 (正向, 中立, 負向)
    """
    tokens = tokenizer(text, return_tensors="pt", truncation=False, padding=False)
    input_ids = tokens['input_ids'][0]
    num_tokens = len(input_ids)  #文本tokens數量
    max_length = 512

    parts = []
    if num_tokens <= max_length:  #小於token不用分割，大於token要
        parts.append(text)
        num_parts = 1
    else:
        num_parts = (num_tokens + max_length - 1) // max_length  #切成幾段
        part_word = len(text) // num_parts  #每一段的字數
        parts = [text[i * part_word : (i + 1) * part_word] for i in range(num_parts)]
        parts[-1] = text[(num_parts - 1) * part_word:]  #最後一段

    total_probs = torch.zeros(3, device=model.device)

    for part in parts:
        inputs = tokenizer(part, return_tensors="pt", truncation=True, padding=True, max_length=max_length).to(model.device)
        outputs = model(**inputs)
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1).squeeze()
        total_probs += probs

    avg_probs = total_probs / num_parts
    return avg_probs


def cal_news_sentiment(stock_id: str, page: int=1) -> pd.DataFrame:
    """
    計算個股的新聞情感分數
    """
    news_summary_df = get_udn_news_summary(stock_id, page=page).iloc[:10]
    
    scores = []
    contents = []
    for i in range(len(news_summary_df)):
        url = news_summary_df['Url'].iloc[i]
        source = news_summary_df['Source'].iloc[i]

        cached = None
        if url:
            cached = DataManager.get_score(
                stock_id=None,
                score_type="news",
                table_name=DataManager.NEWS_TABLE,
                key_fields={"url": url},
            )
        if cached:
            cached_data = cached.get("data", cached)
            cached_score = [
                cached_data.get("positive"),
                cached_data.get("neutral"),
                cached_data.get("negative"),
            ]
            cached_content = cached_data.get("content")
            if cached_content and all(v is not None for v in cached_score):
                scores.append(cached_score)
                contents.append(cached_content)
                continue

        if Env.RELOAD: print(f"計算情感分數中：{i+1}/{len(news_summary_df)}   ", end="\r")
        text = parse_article(url, source=source)

        try:
            score = predict_sentiment(text)
            score_list = score.cpu().tolist()  # 從GPU搬回CPU，避免堆積
            scores.append(score_list)
            contents.append(text)

            if url:
                DataManager.save_score(
                    stock_id=None,
                    data={
                        "positive": score_list[0],
                        "neutral": score_list[1],
                        "negative": score_list[2],
                        "content": text,
                    },
                    score_type="news",
                    table_name=DataManager.NEWS_TABLE,
                    key_fields={"url": url},
                    conflict_keys=("url",),
                    flatten_data=True,
                    include_data=False,
                )
        except Exception as e:
            print(f"🔴 [Error] At {i}: {e}")
            scores.append([None, None, None])
            contents.append(None)
        torch.cuda.empty_cache()  # 清理記憶體
        gc.collect()
    score_df = pd.DataFrame(scores, columns=['positive', 'neutral', 'negative'])
    score_df["content"] = contents
    score_df.index = news_summary_df.index
    score_df.index.name = "日期"
    if Env.RELOAD: print(f"\r Done: 新聞情感分數計算完畢！{' '*40}")
    data = pd.concat([news_summary_df, score_df], axis=1)[['Url', 'content', 'positive', 'neutral', 'negative']]
    return data

def classify_sentiment(pos, neu, neg):
    """依平均分數判斷整體情緒"""
    if pos > 0.5:
        return "極正", 2
    if neg > 0.5:
        return "極負", -2
    if neu > 0.5:
        return "中立", 0

    # 無類別 >0.5 → 取最大者
    max_cat = max([("positive", pos), ("neutral", neu), ("negative", neg)], key=lambda x: x[1])[0]
    return {
        "positive": ("偏多", 1),
        "negative": ("偏空", -1),
        "neutral": ("中立", 0)
    }[max_cat]


def total_news_sentiment(stock_id: str, page: int = 1) -> dict:
    """
    計算個股的總體新聞情感分數
    """
    sentiment_df = cal_news_sentiment(stock_id, page=page)
    contents = sentiment_df['content'].dropna().tolist() if not sentiment_df.empty else []

    if sentiment_df.empty:
        return {
            "direction_label": "無資料",
            "direction": 0,
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "contents": []
        }

    avg_pos = sentiment_df['positive'].mean()
    avg_neu = sentiment_df['neutral'].mean()
    avg_neg = sentiment_df['negative'].mean()
    overall, score = classify_sentiment(avg_pos, avg_neu, avg_neg)

    return {
        "direction": score,
        "direction_label": overall,
        "positive": avg_pos,
        "neutral": avg_neu,
        "negative": avg_neg,
        "contents": contents,
    }
