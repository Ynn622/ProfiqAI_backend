from zoneinfo import ZoneInfo
from datetime import datetime

def getTaiwanTime() -> str:
    """
    取得目前的時間。
    Returns: 
        str: 當前時間的字串，格式為 "YYYY-MM-DD HH:MM:SS"。
    """
    return datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M:%S")