from functools import wraps
import inspect
from enum import Enum

from util.nowtime import getTaiwanTime

# === 顏色設定 ===
class Color(Enum):
    RESET = "\033[0m"
    PURPLE = "\033[95m"   # 紫色
    RED = "\033[91m"      # 紅色
    BLUE = "\033[94m"     # 藍色
    GREEN = "\033[92m"    # 綠色
    YELLOW = "\033[93m"   # 黃色

def log_print(func):
    if inspect.iscoroutinefunction(func):  # 如果是 async function
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = func.__name__
            try:
                arg_str = f"{', '.join(map(str, args))}" if args else ""
                kwarg_str = f"{kwargs}" if kwargs else ""
                print(f"{getTaiwanTime(ms=True)} | {Color.PURPLE.value}🟣 [FunctionCall] {func_name}({arg_str}{kwarg_str}){Color.RESET.value}")
                return await func(*args, **kwargs)
            except Exception as e:
                main_arg = args[0] if args else None
                print(f"{getTaiwanTime(ms=True)} | {Color.RED.value}🔴 [Error] {func_name}({main_arg}): {str(e)}{Color.RESET.value}")
                raise
        return async_wrapper
    else:  # 如果是普通 def
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = func.__name__
            try:
                arg_str = f"{', '.join(map(str, args))}" if args else ""
                kwarg_str = f"{kwargs}" if kwargs else ""
                print(f"{getTaiwanTime(ms=True)} | {Color.BLUE.value}🔵 [Function] {func_name}({arg_str}{kwarg_str}){Color.RESET.value}")
                return func(*args, **kwargs)
            except Exception as e:
                main_arg = args[0] if args else None
                print(f"{getTaiwanTime(ms=True)} | {Color.RED.value}🔴 [Error] {func_name}({main_arg}): {str(e)}{Color.RESET.value}")
                raise
        return sync_wrapper

def printf(*args, color: Color = Color.BLUE, sep=" ", end="\n"):
    message = sep.join(str(arg) for arg in args)
    print(f"{getTaiwanTime(ms=True)} | {color.value}{message}{Color.RESET.value}", end=end)