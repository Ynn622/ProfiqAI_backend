from datetime import timedelta
from typing import Any, Dict, Optional

from util.logger import Log, Color
from util.nowtime import TaiwanTime
from util.supabase_client import supabase


class DataManager:
    """
    依照 stock_id / date / data / type(面向) 存放於 Supabase，並在本地記憶體
    以陣列/字典快取，減少重複請求。

    - basic_data 每日 17:00 後更新
    - chip_data  每日 21:00 後更新
    """

    TABLE_NAME = "stockScores"
    BASIC_UPDATE_HOUR = 17
    CHIP_UPDATE_HOUR = 21
    _local_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
    # 結構: {stock_id: {date: {type: payload}}}

    @staticmethod
    def _normalize_stock_id(stock_id: str) -> str:
        """統一移除 .TW 之類的後綴。"""
        return stock_id.split(".")[0]

    @classmethod
    def _resolve_score_date(cls, score_type: str, score_date: Optional[str] = None) -> str:
        """
        決定該筆資料的紀錄日期。
        若在更新時點前呼叫，會自動回填到前一日，避免日期與實際更新時間不一致。
        """
        if score_date:
            return score_date

        now = TaiwanTime.now()
        cutoff = cls.CHIP_UPDATE_HOUR if score_type == "chip" else cls.BASIC_UPDATE_HOUR
        record_date = now.date()
        if now.hour < cutoff:
            record_date -= timedelta(days=1)
        return record_date.strftime("%Y-%m-%d")

    @classmethod
    def _cache_get(cls, stock_id: str, record_date: str, score_type: str) -> Optional[Dict[str, Any]]:
        stock_key = cls._normalize_stock_id(stock_id)
        return cls._local_cache.get(stock_key, {}).get(record_date, {}).get(score_type)

    @classmethod
    def _cache_set(cls, stock_id: str, record_date: str, score_type: str, payload: Dict[str, Any]) -> None:
        stock_key = cls._normalize_stock_id(stock_id)
        cls._local_cache.setdefault(stock_key, {}).setdefault(record_date, {})[score_type] = payload

    @classmethod
    def save_score(
        cls,
        stock_id: str,
        data: Dict[str, Any],
        score_type: str,
        score_date: Optional[str] = None,
        direction: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        以 upsert 方式存入 Supabase，避免重複插入，同步寫入本地快取。
        """
        record_date = cls._resolve_score_date(score_type, score_date)
        payload = {
            "stock_id": cls._normalize_stock_id(stock_id),
            "date": record_date,
            "type": score_type,
            "data": data,
        }
        if direction is not None:
            payload["direction"] = direction

        # local cache first
        cls._cache_set(stock_id, record_date, score_type, payload)

        try:
            response = (
                supabase.table(cls.TABLE_NAME)
                .upsert(payload, on_conflict="stock_id,date,type")
                .execute()
            )
            return getattr(response, "data", None)
        except Exception as exc:
            Log(f"🔴 [DataManager] 儲存失敗: {exc}", color=Color.RED)
            return None

    @classmethod
    def get_score(
        cls,
        stock_id: str,
        score_type: str,
        score_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        取回指定日期與面向的紀錄；若未指定日期則套用時間邏輯。
        先查本地快取，無資料再查 Supabase。
        """
        record_date = cls._resolve_score_date(score_type, score_date)

        cached = cls._cache_get(stock_id, record_date, score_type)
        if cached:
            return cached

        try:
            response = (
                supabase.table(cls.TABLE_NAME)
                .select("*")
                .eq("stock_id", cls._normalize_stock_id(stock_id))
                .eq("type", score_type)
                .eq("date", record_date)
                .execute()
            )
            if getattr(response, "data", None):
                payload = response.data[0]
                cls._cache_set(stock_id, record_date, score_type, payload)
                return payload
            return None
        except Exception as exc:
            Log(f"🔴 [DataManager] 讀取失敗: {exc}", color=Color.RED)
            return None
