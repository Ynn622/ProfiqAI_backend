from datetime import datetime, timezone
from typing import Optional

from util.config import env
from util.supabase_client import supabase


CONVERSATIONS_TABLE = "chatConversations"
MESSAGES_TABLE = "chatMessages"


def _single_row(response):
    """從 Supabase 回應中取出第一筆資料。"""
    data = getattr(response, "data", None) or []
    return data[0] if data else None


def _conversation_payload(row: dict) -> dict:
    """將聊天室資料轉成前端使用的欄位格式。"""
    return {
        "id": row["id"],
        "title": row.get("title") or "智聊 AI",
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def _message_payload(row: dict) -> dict:
    """將訊息資料轉成前端使用的欄位格式。"""
    return {
        "id": row.get("id"),
        "role": "bot" if row.get("role") == "assistant" else row.get("role"),
        "text": row.get("content") or "",
        "model": row.get("model"),
        "duration": row.get("duration_ms"),
        "createdAt": row.get("created_at"),
    }


def get_user_from_token(access_token: str):
    """用 Supabase access token 取得目前登入使用者。"""
    response = supabase.auth.get_user(access_token)
    return getattr(response, "user", None)


def get_conversations(user_id: str) -> list[dict]:
    """取得使用者所有聊天室，依最近更新時間排序。"""
    response = (
        supabase.table(CONVERSATIONS_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return [_conversation_payload(row) for row in (response.data or [])]


def create_conversation(user_id: str, conversation_id: str, first_message: str = "") -> dict:
    """確保聊天室存在；不存在時用第一則訊息產生標題並建立。"""
    existing = get_conversation(user_id, conversation_id)
    if existing:
        return _conversation_payload(existing)

    title = build_title(first_message)
    response = (
        supabase.table(CONVERSATIONS_TABLE)
        .insert({"id": conversation_id, "user_id": user_id, "title": title})
        .execute()
    )
    return _conversation_payload(_single_row(response))


def get_conversation(user_id: str, conversation_id: str) -> Optional[dict]:
    """取得使用者指定的一個聊天室。"""
    response = (
        supabase.table(CONVERSATIONS_TABLE)
        .select("*")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return _single_row(response)


def delete_conversation(user_id: str, conversation_id: str) -> bool:
    """刪除使用者指定聊天室；訊息會依資料庫 cascade 一起刪除。"""
    existing = get_conversation(user_id, conversation_id)
    if not existing:
        return False

    supabase.table(CONVERSATIONS_TABLE).delete().eq("id", conversation_id).eq("user_id", user_id).execute()
    return True


def update_default_title(user_id: str, conversation_id: str, text: str) -> None:
    """當聊天室仍是預設標題時，用使用者訊息更新標題。"""
    title = build_title(text)
    if title == "智聊 AI":
        return

    supabase.table(CONVERSATIONS_TABLE).update(
        {"title": title, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", conversation_id).eq("user_id", user_id).eq("title", "智聊 AI").execute()


def get_messages(user_id: str, conversation_id: str) -> list[dict]:
    """取得指定聊天室的所有歷史訊息。"""
    if not get_conversation(user_id, conversation_id):
        return []

    response = (
        supabase.table(MESSAGES_TABLE)
        .select("*")
        .eq("conversation_id", conversation_id)
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return [_message_payload(row) for row in (response.data or [])]


def get_recent_agent_messages(user_id: str, conversation_id: str) -> list[dict]:
    """取得最近幾輪對話，整理成 OpenAI Agents SDK 可接受的上下文格式。"""
    max_items = max(env.SESSION_MAX_ITEMS * 2, 2)
    response = (
        supabase.table(MESSAGES_TABLE)
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(max_items)
        .execute()
    )
    rows = list(reversed(response.data or []))
    return [
        {"role": row["role"], "content": row.get("content") or ""}
        for row in rows
        if row.get("role") in {"user", "assistant"}
    ]


def save_message(
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    model: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> dict:
    """儲存一則訊息，並同步更新聊天室的 updated_at。"""
    response = (
        supabase.table(MESSAGES_TABLE)
        .insert(
            {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "model": model,
                "duration_ms": duration_ms,
            }
        )
        .execute()
    )

    supabase.table(CONVERSATIONS_TABLE).update(
        {"updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", conversation_id).eq("user_id", user_id).execute()

    return _message_payload(_single_row(response))


def build_title(text: str) -> str:
    """用訊息內容產生聊天室標題，最多保留 24 個字。"""
    compact = " ".join((text or "").split())
    if not compact:
        return "智聊 AI"
    return compact[:24]
