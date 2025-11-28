from typing import Optional
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs

from util.logger import Log, Color

class StockList:
    """下載並快取台股上市/上櫃清單。"""

    TWSE_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
    TPEX_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
    _cache: Optional[pd.DataFrame] = None

    @staticmethod
    def _strip_suffix(stock_id: str) -> str:
        """移除 .TW / .TWO 等後綴，僅保留純數字代號。"""
        return stock_id.split(".")[0].upper()

    @classmethod
    def _download(cls) -> pd.DataFrame:
        """
        下載股票列表，包含上市和上櫃股票。

        Returns:
            pd.DataFrame: 股票列表，包含 stock_id, stock_name, type 三個欄位
        """
        twse_df = pd.read_csv(cls.TWSE_URL, dtype=str)
        tpex_df = pd.read_csv(cls.TPEX_URL, dtype=str)

        twse_df = twse_df[["公司代號", "公司簡稱"]]
        twse_df["公司代號"] = twse_df["公司代號"]+".TW"
        twse_df["市場別"] = "上市"

        tpex_df = tpex_df[["公司代號", "公司簡稱"]]
        tpex_df["公司代號"] = tpex_df["公司代號"]+".TWO"
        tpex_df["市場別"] = "上櫃"

        df = pd.concat([twse_df, tpex_df], ignore_index=True)
        df.rename(
            columns={
                "公司代號": "stock_id",
                "公司簡稱": "stock_name",
                "市場別": "type",
            },
            inplace=True,
        )
        Log(f"🟢 [StockList] 下載股票清單完成，共 {len(df)} 檔股票。", color=Color.GREEN)
        return df

    @classmethod
    def _ensure_cache(cls) -> pd.DataFrame:
        """第一次呼叫時下載並快取，之後直接使用記憶體中的 DataFrame。"""
        if cls._cache is None:
            cls._cache = cls._download()
        return cls._cache

    @classmethod
    def refresh(cls) -> pd.DataFrame:
        """重新下載並覆寫快取。"""
        cls._cache = cls._download()
        return cls._cache

    @classmethod
    def get_all(cls) -> pd.DataFrame:
        """取得股票清單副本，避免外部修改快取內容。"""
        return cls._ensure_cache().copy()

    @classmethod
    def query(cls, keyword: str) -> tuple[str, str]:
        """
        「查詢」公司代號 or 公司簡稱搜尋，回傳符合的 (stock_id, stock_name)。
        
        ⚠️ 先完全比對，找不到再模糊搜尋。
        Args:
            keyword: 公司代號 or 公司簡稱
        Returns:
            tuple: (stock_id, stock_name)，找不到則回傳 (None, None)
        """
        df = cls._ensure_cache()
        keyword = str(keyword).strip()
        if not keyword: return None, None

        normalized = keyword.upper()
        normalized_base = cls._strip_suffix(normalized)
        result = df.loc[
            (df["stock_id"].str.upper() == normalized)
            | (df["stock_id"].str.split(".").str[0].str.upper() == normalized_base)
            | (df["stock_name"] == keyword)
        ]
        
        # 若完全比對無結果 → fallback 到 fuzzy_query
        if result.empty:
            return cls.fuzzy_query(keyword)
        first = result.iloc[0]
        return str(first["stock_id"]), str(first["stock_name"])
    
    @classmethod
    def fuzzy_query(cls, keyword: str) -> tuple[str, str]:
        """
        「模糊搜尋」公司代號前綴 or 公司簡稱包含關鍵字，回傳符合的第一筆 (stock_id, stock_name)。
        Args:
            keyword: 公司代號前綴 or 公司關鍵字
        Returns:
            tuple: (stock_id, stock_name)，找不到則回傳 (None, None)
        """
        df = cls._ensure_cache()

        # stock_id 前綴搜尋 
        mask_prefix = df["stock_id"].str.startswith(keyword)

        # stock_name 模糊包含搜尋
        mask_name = df["stock_name"].str.contains(keyword, case=False, regex=False)

        result = df.loc[mask_prefix | mask_name]
        
        if result.empty:
            return None, None
                
        first = result.iloc[0]
        return str(first["stock_id"]), str(first["stock_name"])

    @classmethod
    def query_from_yahoo(cls, keyword: str) -> tuple[str, str]:
        """
        透過 Yahoo Finance 的搜尋欄 API 查詢，回傳 (stock_id, stock_name)。
        
        ⚠️ 不使用本地快取，專為補充查詢用。
        """
        stockID, stockName = None, None
        if not keyword:
            return stockID, stockName
        try:
            url = f"https://tw.stock.yahoo.com/_td-stock/api/resource/WaferAutocompleteService;view=wafer&query={keyword}"
            response = requests.get(url)
            stockID = bs(response.json()["html"], features="lxml").find("a")["href"].split('stock_id=')[1]
            stockName = bs(response.json()["html"], features="lxml").find("span").text
        except Exception as e:
            Log(f"🔴 [StockList] Yahoo 查詢失敗: {e}", color=Color.RED)
        return stockID, stockName

StockList._ensure_cache()  # 初始化快取