from functools import wraps
import inspect
from datetime import datetime
import pytz

# === 顏色設定 ===
RESET = "\033[0m"
PURPLE = "\033[95m"   # 紫色
RED = "\033[91m"      # 紅色

def current_time():
    # 取得台灣時區
    taiwan_tz = pytz.timezone("Asia/Taipei")
    taiwan_now = datetime.now(taiwan_tz)

    # 格式化：%f 是微秒，取前 3 位數當毫秒
    formatted_time = taiwan_now.strftime("%Y-%m-%d %H:%M:%S:") + f"{taiwan_now.microsecond // 1000:03d}"
    return formatted_time

def log_print(func):
    if inspect.iscoroutinefunction(func):  # 如果是 async function
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = func.__name__
            try:
                arg_str = f"{', '.join(map(str, args))}" if args else ""
                kwarg_str = f"{kwargs}" if kwargs else ""
                print(f"{current_time()} | {PURPLE}🟣 [FunctionCall] {func_name}({arg_str}{kwarg_str}){RESET}")
                return await func(*args, **kwargs)
            except Exception as e:
                main_arg = args[0] if args else None
                print(f"{current_time()} | {RED}🔴 [Error] {func_name}({main_arg}): {str(e)}{RESET}")
                raise
        return async_wrapper
    else:  # 如果是普通 def
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = func.__name__
            try:
                arg_str = f"{', '.join(map(str, args))}" if args else ""
                kwarg_str = f"{kwargs}" if kwargs else ""
                print(f"{current_time()} | {PURPLE}🟣 [Function] {func_name}({arg_str}{kwarg_str}){RESET}")
                return func(*args, **kwargs)
            except Exception as e:
                main_arg = args[0] if args else None
                print(f"{current_time()} | {RED}🔴 [Error] {func_name}({main_arg}): {str(e)}{RESET}")
                raise
        return sync_wrapper