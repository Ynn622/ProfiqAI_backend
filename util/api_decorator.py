from functools import wraps
import inspect
import time
import json

from util.logger import Color
from util.nowtime import TaiwanTime


def add_runtime(func):
    """
    為 API 端點添加執行時間的裝飾器。
    自動在 response 中加入 runtime 字段。
    """
    
    def _add_time_to_response(result, elapsed_ms):
        """將執行時間添加到 response 中"""
        from fastapi.responses import JSONResponse
        
        if isinstance(result, JSONResponse):
            # 如果是 JSONResponse，修改其 content
            content = result.body.decode('utf-8')
            content_dict = json.loads(content)
            content_dict['runtime'] = f"{elapsed_ms:.2f}ms"
            return JSONResponse(content=content_dict, status_code=result.status_code)
        elif isinstance(result, dict):
            # 如果是字典，直接添加
            result['runtime'] = f"{elapsed_ms:.2f}ms"
            return result
        else:
            # 其他類型保持不變
            return result
    
    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = func.__name__
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.GREEN.value}⏱️  [Timer] {func_name} ({elapsed_ms:.2f}ms){Color.RESET.value}")
                return _add_time_to_response(result, elapsed_ms)
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.YELLOW.value}⏱️  [Timer] {func_name} ({elapsed_ms:.2f}ms) - Error{Color.RESET.value}")
                raise
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = func.__name__
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.GREEN.value}⏱️  [Timer] {func_name} ({elapsed_ms:.2f}ms){Color.RESET.value}")
                return _add_time_to_response(result, elapsed_ms)
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.YELLOW.value}⏱️  [Timer] {func_name} ({elapsed_ms:.2f}ms) - Error{Color.RESET.value}")
                raise
        return sync_wrapper
