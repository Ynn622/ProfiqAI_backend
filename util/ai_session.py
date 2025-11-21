import asyncio
from agents import SQLiteSession

from util.config import env

async def trim_session(session_id: str) -> SQLiteSession:
    """
    修剪對話紀錄至最近的 N 項。
    Args:
        session_id (str): 對話會話的唯一識別碼。
        max_items (int): 保留的最大對話項目數量。
    Returns:
        SQLiteSession: 修剪後的對話會話物件。
    """
    MAX_ITEMS = env.SESSION_MAX_ITEMS   # 從環境變數中取得最大項目數量
    
    session = SQLiteSession(session_id, "data/conversations.db")
    items = await session.get_items()
    if len(items) > MAX_ITEMS:
        trimmed = items[-MAX_ITEMS:]
        await session.clear_session()
        await session.add_items(trimmed)
    return session