from functools import wraps
import inspect
from enum import Enum

from util.config import Env
from util.nowtime import TaiwanTime

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - pydantic is available in the API runtime.
    BaseModel = None

# === 顏色設定 ===
class Color(Enum):
    RESET = "\033[0m"
    PURPLE = "\033[95m"   # 紫色
    RED = "\033[91m"      # 紅色
    BLUE = "\033[94m"     # 藍色
    GREEN = "\033[92m"    # 綠色
    YELLOW = "\033[93m"   # 黃色
    ORANGE = "\033[38;5;208m"   # 橙色

# 顏色對應 icon
ICON_BY_COLOR = {
    Color.PURPLE: "🟣",
    Color.RED: "🔴",
    Color.BLUE: "🔵",
    Color.GREEN: "🟢",
    Color.YELLOW: "🟡",
    Color.ORANGE: "🟠",
}

SUMMARY_ARG_NAMES = {
    "authorization",
    "auth",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "password",
    "secret",
}

def _should_summarize_arg(name: str) -> bool:
    lower_name = name.lower()
    return (
        lower_name in SUMMARY_ARG_NAMES
        or lower_name.endswith("_token")
        or "authorization" in lower_name
        or "api_key" in lower_name
        or "password" in lower_name
        or "secret" in lower_name
    )


def _summarize_value(value) -> str:
    if value is None:
        return "None"
    if isinstance(value, str):
        return f"<{len(value)} chars>"
    if isinstance(value, dict):
        return f"<{len(value)} keys>"
    if isinstance(value, (list, tuple, set)):
        return f"<{len(value)} items>"
    return f"<{value.__class__.__name__}>"


def _format_log_value(name: str, value, max_length: int = 120) -> str:
    if _should_summarize_arg(name):
        return _summarize_value(value)

    if BaseModel is not None and isinstance(value, BaseModel):
        if hasattr(value, "model_dump"):
            data = value.model_dump()
        else:
            data = value.dict()
        fields = ", ".join(
            f"{key}={_format_log_value(key, field_value)}"
            for key, field_value in data.items()
        )
        return f"{value.__class__.__name__}({fields})"

    if isinstance(value, dict):
        items = list(value.items())
        formatted = ", ".join(
            f"{key}={_format_log_value(str(key), item_value)}"
            for key, item_value in items[:6]
        )
        if len(items) > 6:
            formatted += ", ..."
        return "{" + formatted + "}"

    if isinstance(value, (list, tuple, set)):
        values = list(value)
        formatted = ", ".join(_format_log_value(name, item) for item in values[:6])
        if len(values) > 6:
            formatted += ", ..."
        opener, closer = ("[", "]") if not isinstance(value, tuple) else ("(", ")")
        return f"{opener}{formatted}{closer}"

    value_repr = repr(value)
    if len(value_repr) > max_length:
        return f"{value_repr[:max_length]}...<{len(value_repr)} chars>"
    return value_repr


def _event_color(label: str) -> Color:
    if label in {"ToolCall", "FunctionCall"}:
        return Color.PURPLE
    return Color.BLUE


# === 日誌裝飾器 ===
def log_print(func=None, *, label: str = "Function", color: Color | None = None):
    def decorator(target):
        signature = inspect.signature(target)
        event_color = color or _event_color(label)
        icon = ICON_BY_COLOR.get(event_color, "")

        def build_arg_string(args, kwargs):
            try:
                bound = signature.bind_partial(*args, **kwargs)
                items = bound.arguments.items()
            except TypeError:
                items = [(f"arg{index}", value) for index, value in enumerate(args)]
                items.extend(kwargs.items())

            return ", ".join(
                f"{name}={_format_log_value(name, value)}"
                for name, value in items
            )

        if inspect.iscoroutinefunction(target):
            @wraps(target)
            async def async_wrapper(*args, **kwargs):
                func_name = target.__name__
                arg_str = build_arg_string(args, kwargs)
                try:
                    print(f"{TaiwanTime.string(ms=True)} | "
                          f"{event_color.value}{icon} [{label}] {func_name}({arg_str}){Color.RESET.value}")

                    return await target(*args, **kwargs)
                except Exception as e:
                    print(f"{TaiwanTime.string(ms=True)} | "
                          f"{Color.RED.value}🔴 [Error] {func_name}: {e}{Color.RESET.value}")
                    raise
            return async_wrapper

        @wraps(target)
        def sync_wrapper(*args, **kwargs):
            func_name = target.__name__
            arg_str = build_arg_string(args, kwargs)
            try:
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{event_color.value}{icon} [{label}] {func_name}({arg_str}){Color.RESET.value}")
                return target(*args, **kwargs)
            except Exception as e:
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.RED.value}🔴 [Error] {func_name}: {e}{Color.RESET.value}")
                raise
        return sync_wrapper

    if func is None:
        return decorator
    return decorator(func)

def Log(*args, color: Color = Color.BLUE, sep=" ", end="\n", reload_only: bool = False):
    """
    印出帶有時間戳記與顏色的日誌訊息。
    Args:
        *args: 要印出的訊息內容。
        color (Color): 訊息顏色，預設為藍色。
        sep (str): 訊息間的分隔符號，預設為空格。
        end (str): 訊息結尾的字元，預設為換行符號。
        reload_only (bool): 是否僅在 Env.RELOAD=True 時印出訊息，預設為 False。
    """
    if reload_only and not Env.RELOAD:
        return
    icon = ICON_BY_COLOR.get(color, "")
    message = sep.join(str(arg) for arg in args)
    print(f"{TaiwanTime.string(ms=True)} | {icon} {color.value}{message}{Color.RESET.value}", end=end)