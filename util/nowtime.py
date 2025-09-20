from zoneinfo import ZoneInfo
from datetime import datetime

def getTaiwanTime(ms: bool = False) -> str:
    """
    取得台灣目前時間。
    Args:
        ms (bool): 是否包含毫秒 (預設 False)。
    Returns: 
        str: "YYYY-MM-DD HH:MM:SS" 或 "YYYY-MM-DD HH:MM:SS:SSS"
    """
    taiwan_now = datetime.now(ZoneInfo("Asia/Taipei"))
    base_time = taiwan_now.strftime("%Y-%m-%d %H:%M:%S")

    if ms:
        # YYYY-MM-DD HH:MM:SS:SSS
        return base_time + f":{taiwan_now.microsecond // 1000:03d}"
    else:
        # YYYY-MM-DD HH:MM:SS
        return base_time