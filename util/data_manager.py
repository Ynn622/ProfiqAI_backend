from datetime import timedelta
from typing import Any, Dict, Optional, Iterable

from util.logger import Log, Color
from util.nowtime import TaiwanTime
from util.supabase_client import supabase


class DataManager:
    """
    依照 stock_id / date / data / type(面向) 存放於 Supabase，並在本地記憶體以陣列/字典快取。
    亦可透過 key_fields/table_name 自訂主鍵欄位（例如新聞情緒以 url 為主鍵）。

    - basic_data 每日 17:00 後更新
    - chip_data  每日 21:00 後更新
    """

    STOCK_SCORE_TABLE = "stockScores"
    NEWS_TABLE = "newsScores"
    BASIC_UPDATE_HOUR = 17
    CHIP_UPDATE_HOUR = 21
    _local_cache: Dict[str, Dict[str, Any]] = {}
    # 結構: {table: {cache_key: payload}}

    @staticmethod
    def _normalize_stock_id(stock_id: Optional[str]) -> str:
        """統一移除 .TW 之類的後綴。"""
        if not stock_id:
            return ""
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
    def _make_cache_key(cls, key_fields: Dict[str, Any]) -> str:
        return "|".join(f"{k}:{key_fields[k]}" for k in sorted(key_fields))

    @classmethod
    def _cache_get(cls, table: str, key_fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cache_key = cls._make_cache_key(key_fields)
        return cls._local_cache.get(table, {}).get(cache_key)

    @classmethod
    def _cache_set(cls, table: str, key_fields: Dict[str, Any], payload: Dict[str, Any]) -> None:
        cache_key = cls._make_cache_key(key_fields)
        cls._local_cache.setdefault(table, {})[cache_key] = payload

    @classmethod
    def save_score(
        cls,
        stock_id: Optional[str],
        data: Dict[str, Any],
        score_type: str,
        score_date: Optional[str] = None,
        direction: Optional[Any] = None,
        table_name: Optional[str] = None,
        key_fields: Optional[Dict[str, Any]] = None,
        conflict_keys: Optional[Iterable[str]] = None,
        flatten_data: bool = False,
        include_data: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        以 upsert 方式存入 Supabase，避免重複插入，同步寫入本地快取。
        可透過 key_fields/table_name 自訂主鍵欄位。若 include_data=False，則不存 data json。
        """
        table = table_name or cls.STOCK_SCORE_TABLE
        if key_fields is None:
            record_date = cls._resolve_score_date(score_type, score_date)
            key_fields = {
                "stock_id": cls._normalize_stock_id(stock_id),
                "date": record_date,
                "type": score_type,
            }
            conflict_keys = conflict_keys or ("stock_id", "date", "type")
        else:
            conflict_keys = conflict_keys or tuple(key_fields.keys())

        payload: Dict[str, Any] = dict(key_fields)
        if include_data:
            payload["data"] = data
        if flatten_data:
            payload.update(data)
        if direction is not None:
            payload["direction"] = direction

        # local cache first
        cls._cache_set(table, key_fields, payload)

        try:
            response = (
                supabase.table(table)
                .upsert(payload, on_conflict=",".join(conflict_keys))
                .execute()
            )
            return getattr(response, "data", None)
        except Exception as exc:
            Log(f"🔴 [DataManager] 儲存失敗: {exc}", color=Color.RED)
            return None

    @classmethod
    def get_score(
        cls,
        stock_id: Optional[str],
        score_type: str,
        score_date: Optional[str] = None,
        table_name: Optional[str] = None,
        key_fields: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        取回指定日期與面向的紀錄；若未指定日期則套用時間邏輯。
        先查本地快取，無資料再查 Supabase。可透過 key_fields/table_name 自訂主鍵欄位。
        """
        table = table_name or cls.STOCK_SCORE_TABLE
        if key_fields is None:
            record_date = cls._resolve_score_date(score_type, score_date)
            key_fields = {
                "stock_id": cls._normalize_stock_id(stock_id),
                "type": score_type,
                "date": record_date,
            }
        else:
            record_date = key_fields.get("date")

        cached = cls._cache_get(table, key_fields)
        if cached:
            return cached

        try:
            query = supabase.table(table).select("*")
            for key, value in key_fields.items():
                query = query.eq(key, value)
            response = query.execute()
            if getattr(response, "data", None):
                payload = response.data[0]
                cls._cache_set(table, key_fields, payload)
                return payload
            return None
        except Exception as exc:
            Log(f"🔴 [DataManager] 讀取失敗: {exc}", color=Color.RED)
            return None
