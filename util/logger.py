from functools import wraps
import inspect
from enum import Enum

from util.nowtime import TaiwanTime

# === 顏色設定 ===
class Color(Enum):
    RESET = "\033[0m"
    PURPLE = "\033[95m"   # 紫色
    RED = "\033[91m"      # 紅色
    BLUE = "\033[94m"     # 藍色
    GREEN = "\033[92m"    # 綠色
    YELLOW = "\033[93m"   # 黃色

# === 日誌裝飾器 ===
def log_print(func):
    def build_arg_string(args, kwargs):
        parts = []
        if args:
            parts.append(", ".join(map(str, args)))
        if kwargs:
            parts.append(", ".join(f"{k}={v}" for k, v in kwargs.items()))
        return ", ".join(parts)

    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = func.__name__
            arg_str = build_arg_string(args, kwargs)
            try:
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.PURPLE.value}🟣 [FunctionCall] {func_name}({arg_str}){Color.RESET.value}")

                return await func(*args, **kwargs)
            except Exception as e:
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.RED.value}🔴 [Error] {func_name}: {e}{Color.RESET.value}")
                raise
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = func.__name__
            arg_str = build_arg_string(args, kwargs)
            try:
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.BLUE.value}🔵 [Function] {func_name}({arg_str}){Color.RESET.value}")
                return func(*args, **kwargs)
            except Exception as e:
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.RED.value}🔴 [Error] {func_name}: {e}{Color.RESET.value}")
                raise
        return sync_wrapper

def Log(*args, color: Color = Color.BLUE, sep=" ", end="\n"):
    message = sep.join(str(arg) for arg in args)
    print(f"{TaiwanTime.string(ms=True)} | {color.value}{message}{Color.RESET.value}", end=end)