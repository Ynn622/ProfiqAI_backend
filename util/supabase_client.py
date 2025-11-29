"""
Supabase Client 單例模組
提供全域的 Supabase 客戶端實例
"""
from supabase import create_client, Client
from util.config import Env
from util.logger import Log, Color


class SupabaseClient:
    """Supabase 客戶端單例類"""
    _instance: Client = None
    
    @classmethod
    def get_client(cls) -> Client:
        """
        獲取 Supabase 客戶端實例（單例模式）
        
        Returns:
            Client: Supabase 客戶端實例
        """
        if cls._instance is None:
            cls._instance = create_client(Env.SUPABASE_URL, Env.SUPABASE_KEY)
            Log(f"[SupabaseClient] 建立連線完成！", color=Color.GREEN)
        return cls._instance


# 提供便捷的全域實例
supabase = SupabaseClient.get_client()
