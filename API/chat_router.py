from typing import Optional
import json
import time

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from services.function_tools import ask_AI_Agent, stream_AI_Agent
from services.chat_history import (
    build_title,
    create_conversation,
    delete_conversation,
    get_conversations,
    get_messages,
    get_recent_agent_messages,
    get_user_from_token,
    save_message,
    update_default_title,
)
from util.logger import log_print
from util.api_decorator import add_runtime

router = APIRouter(prefix="/chat", tags=["AI 聊天 (Chat)"])

class ChatRequest(BaseModel):
    model: str = "gpt-4.1-mini"
    question: str
    uuid: str

def _auth_user(authorization: Optional[str]):
    """解析 Authorization header，沒有登入時回傳 None。"""
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    try:
        return get_user_from_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _require_user(authorization: Optional[str]):
    """要求使用者必須登入，否則回傳 401。"""
    user = _auth_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _sse(event: str, payload: dict) -> str:
    """將事件名稱與資料包成 SSE 格式字串。"""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/conversations")
async def list_conversations(authorization: Optional[str] = Header(None)):
    """取得目前登入使用者的聊天室清單。"""
    user = _require_user(authorization)
    return JSONResponse(content={"conversations": get_conversations(user.id)})


@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id: str, authorization: Optional[str] = Header(None)):
    """取得指定聊天室的歷史訊息。"""
    user = _require_user(authorization)
    return JSONResponse(content={"messages": get_messages(user.id, conversation_id)})


@router.delete("/conversations/{conversation_id}")
async def remove_conversation(conversation_id: str, authorization: Optional[str] = Header(None)):
    """刪除目前登入使用者指定的一個聊天室。"""
    user = _require_user(authorization)
    deleted = delete_conversation(user.id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return JSONResponse(content={"deleted": True})


@router.post("/chatBot")
@log_print
@add_runtime
async def ask(req: ChatRequest, authorization: Optional[str] = Header(None)):
    """非串流聊天 API；登入時會讀取上下文並儲存 user/assistant 訊息。"""
    user = _auth_user(authorization)
    history_messages = None

    if user:
        create_conversation(user.id, req.uuid, req.question)
        update_default_title(user.id, req.uuid, req.question)
        save_message(user.id, req.uuid, "user", req.question, req.model.lower())
        history_messages = get_recent_agent_messages(user.id, req.uuid)

    chat_response = await ask_AI_Agent(
        req.question,
        model=req.model.lower(),
        session_id=req.uuid,
        history_messages=history_messages,
    )

    if user:
        save_message(user.id, req.uuid, "assistant", chat_response, req.model.lower())

    return JSONResponse(content={'response': chat_response})


@router.post("/chatBot/stream")
@log_print
async def ask_stream(req: ChatRequest, authorization: Optional[str] = Header(None)):
    """串流聊天 API；登入時先存 user，串流完成後再存 assistant。"""
    user = _auth_user(authorization)
    user_id = getattr(user, "id", None) if user else None
    model = req.model.lower()
    history_messages = None

    if user_id:
        create_conversation(user_id, req.uuid, req.question)
        update_default_title(user_id, req.uuid, req.question)
        save_message(user_id, req.uuid, "user", req.question, model)
        history_messages = get_recent_agent_messages(user_id, req.uuid)

    async def event_generator():
        """逐步轉送 AI delta/status，最後輸出 done 或 error 事件。"""
        answer = ""
        start_time = time.perf_counter()

        try:
            async for stream_event in stream_AI_Agent(
                req.question,
                model=model,
                session_id=req.uuid,
                history_messages=history_messages,
            ):
                if not stream_event:
                    continue

                if stream_event["type"] == "status":
                    yield _sse("status", {
                        "message": stream_event["message"],
                        "tool": stream_event.get("tool"),
                        "phase": stream_event.get("phase"),
                    })
                    continue

                delta = stream_event.get("delta", "")
                if delta:
                    answer += delta
                    yield _sse("delta", {"delta": delta})

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            if user_id and answer:
                save_message(user_id, req.uuid, "assistant", answer, model, duration_ms)

            yield _sse("done", {
                "response": answer,
                "duration_ms": duration_ms,
                "title": build_title(req.question),
            })
        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
