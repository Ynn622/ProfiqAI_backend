from datetime import timedelta, datetime, date
from typing import Any, Dict, Optional

from services.stock_data import getStockPrice

from util.logger import Log, Color
from util.nowtime import TaiwanTime
from util.supabase_client import supabase


class DataManager:
    """
    依照 stock_id / date / data / type(面向) 存放於 Supabase，並在本地記憶體以陣列/字典快取。
    
    - stockScores: 股票各面向分數 (basic/chip/tech/news)
    - newsScores: 個別新聞情感分數 (以 url 為主鍵)
    
    更新時間:
    - basic_data 每日 17:00 後更新
    - chip_data  每日 21:00 後更新
    - tech_data  每日 14:00 後更新
    """

    STOCK_SCORE_TABLE = "stockScores"
    NEWS_TABLE = "newsScores"
    BASIC_UPDATE_HOUR = 17
    CHIP_UPDATE_HOUR = 21
    TECH_UPDATE_HOUR = 14
    _local_cache: Dict[str, Dict[str, Any]] = {}
    # 結構: {table: {cache_key: payload}}
    _last_trading_day_cache: Optional[date] = None
    _trading_day_cache_date: Optional[date] = None

    @staticmethod
    def _normalize_stock_id(stock_id: Optional[str]) -> str:
        """統一移除 .TW 之類的後綴。"""
        if not stock_id:
            return ""
        return stock_id.split(".")[0]

    @classmethod
    def _get_last_trading_day(cls, target_date: date) -> date:
        """
        取得最近的交易日，透過查詢 ^TWII (台灣加權指數) 取得實際交易日。
        每天第一次查詢會透過 getStockPrice 取得，之後使用快取。
        
        Args:
            target_date: 目標日期
            
        Returns:
            最近的交易日日期
        """
        today = TaiwanTime.now().date()
        
        # 如果快取是今天的且目標日期在今天或之後，直接返回快取
        if (cls._trading_day_cache_date == today and 
            cls._last_trading_day_cache is not None and 
            target_date >= today):
            return cls._last_trading_day_cache
        
        try:
            # 查詢近 30 天的交易資料
            start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
            hist = getStockPrice(symbol="^TWII", start=start_date, chip_enable=False)
            
            if hist is not None and not hist.empty:
                # 過濾 <= target_date 的交易日 (index 已是字串 YYYY-MM-DD)
                target_str = target_date.strftime("%Y-%m-%d")
                valid_hist = hist[hist.index <= target_str]
                
                if not valid_hist.empty:
                    last_trading_day_str = valid_hist.index[-1]
                    last_trading_day = datetime.strptime(last_trading_day_str, "%Y-%m-%d").date()
                    
                    # 如果查詢的是今天,更新快取
                    if target_date >= today:
                        cls._last_trading_day_cache = last_trading_day
                        cls._trading_day_cache_date = today
                    
                    Log(f"[DataManager] 取得最近交易日: {last_trading_day}", color=Color.GREEN, reload_only=True)
                    return last_trading_day
            
            Log(f"[DataManager] getStockPrice 查無交易日，使用 fallback 週末過濾", color=Color.YELLOW)
        except Exception as exc:
            Log(f"[DataManager] getStockPrice 查詢失敗: {exc}，使用 fallback", color=Color.YELLOW)
        
        # Fallback: 簡單排除週末
        while target_date.weekday() >= 5:  # 5=週六, 6=週日
            target_date -= timedelta(days=1)
        return target_date

    @classmethod
    def _resolve_score_date(cls, score_type: str, score_date: Optional[str] = None) -> str:
        """
        決定該筆資料的紀錄日期。
        若在更新時點前呼叫，會自動回填到前一交易日，避免日期與實際更新時間不一致。
        """
        if score_date:
            return score_date

        now = TaiwanTime.now()
        cutoff = (
            cls.CHIP_UPDATE_HOUR if score_type == "chip"
            else cls.BASIC_UPDATE_HOUR if score_type == "basic"
            else cls.TECH_UPDATE_HOUR if score_type == "tech"
            else cls.BASIC_UPDATE_HOUR
        )
        record_date = now.date()
        if now.hour < cutoff:
            record_date -= timedelta(days=1)
        
        # 確保是交易日
        record_date = cls._get_last_trading_day(record_date)
        
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

    # ==================== stockScores 相關方法 ====================

    @classmethod
    def save_stock_score(
        cls,
        stock_id: str,
        data: Dict[str, Any],
        score_type: str,
        score_date: Optional[str] = None,
        direction: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        儲存股票分數到 stockScores 表。
        
        Args:
            stock_id: 股票代號
            data: 分數資料
            score_type: 分數類型 (basic/chip/tech/news)
            score_date: 指定日期，若無則自動判斷
            direction: 方向性 (正負分數)
        """
        record_date = cls._resolve_score_date(score_type, score_date)
        key_fields = {
            "stock_id": cls._normalize_stock_id(stock_id),
            "date": record_date,
            "type": score_type,
        }
        conflict_keys = ("stock_id", "date", "type")

        payload: Dict[str, Any] = dict(key_fields)
        payload["data"] = data
        if direction is not None:
            payload["direction"] = direction

        cls._cache_set(cls.STOCK_SCORE_TABLE, key_fields, payload)

        try:
            response = (
                supabase.table(cls.STOCK_SCORE_TABLE)
                .upsert(payload, on_conflict=",".join(conflict_keys))
                .execute()
            )
            return getattr(response, "data", None)
        except Exception as exc:
            Log(f"[DataManager] stockScores 儲存失敗: {exc}", color=Color.RED)
            return None

    @classmethod
    def get_stock_score(
        cls,
        stock_id: str,
        score_type: str,
        score_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        取得股票分數從 stockScores 表。
        
        Args:
            stock_id: 股票代號
            score_type: 分數類型 (basic/chip/tech/news)
            score_date: 指定日期，若無則自動判斷
        """
        record_date = cls._resolve_score_date(score_type, score_date)
        key_fields = {
            "stock_id": cls._normalize_stock_id(stock_id),
            "type": score_type,
            "date": record_date,
        }

        cached = cls._cache_get(cls.STOCK_SCORE_TABLE, key_fields)
        if cached:
            return cached

        try:
            query = supabase.table(cls.STOCK_SCORE_TABLE).select("*")
            for key, value in key_fields.items():
                query = query.eq(key, value)
            response = query.execute()
            if getattr(response, "data", None):
                payload = response.data[0]
                cls._cache_set(cls.STOCK_SCORE_TABLE, key_fields, payload)
                return payload
            return None
        except Exception as exc:
            Log(f"[DataManager] stockScores 讀取失敗: {exc}", color=Color.RED)
            return None

    # ==================== newsScores 相關方法 ====================

    @classmethod
    def save_news_score(
        cls,
        url: str,
        positive: float,
        neutral: float,
        negative: float,
        content: str,
        title: Optional[str] = None,
        publish_time: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        儲存新聞情感分數到 newsScores 表。
        
        Args:
            url: 新聞網址 (主鍵)
            positive: 正面分數
            neutral: 中立分數
            negative: 負面分數
            content: 新聞內容
            title: 新聞標題
            publish_time: 發布時間戳記
        """
        key_fields = {"url": url}
        conflict_keys = ("url",)

        payload: Dict[str, Any] = {
            "url": url,
            "positive": positive,
            "neutral": neutral,
            "negative": negative,
            "content": content,
        }
        if title is not None:
            payload["title"] = title
        if publish_time is not None:
            payload["publishTime"] = datetime.fromtimestamp(publish_time, tz=TaiwanTime.TIMEZONE).isoformat()

        cls._cache_set(cls.NEWS_TABLE, key_fields, payload)

        try:
            response = (
                supabase.table(cls.NEWS_TABLE)
                .upsert(payload, on_conflict=",".join(conflict_keys))
                .execute()
            )
            return getattr(response, "data", None)
        except Exception as exc:
            Log(f"[DataManager] newsScores 儲存失敗: {exc}", color=Color.RED)
            return None

    @classmethod
    def get_news_score(cls, url: str) -> Optional[Dict[str, Any]]:
        """
        取得新聞情感分數從 newsScores 表。
        
        Args:
            url: 新聞網址 (主鍵)
        """
        key_fields = {"url": url}

        cached = cls._cache_get(cls.NEWS_TABLE, key_fields)
        if cached:
            return cached

        try:
            response = (
                supabase.table(cls.NEWS_TABLE)
                .select("*")
                .eq("url", url)
                .execute()
            )
            if getattr(response, "data", None):
                payload = response.data[0]
                cls._cache_set(cls.NEWS_TABLE, key_fields, payload)
                return payload
            return None
        except Exception as exc:
            Log(f"[DataManager] newsScores 讀取失敗: {exc}", color=Color.RED)
            return None
