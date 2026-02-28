from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio

from services.function_tools import ask_AI_Agent
from util.logger import log_print
from util.api_decorator import add_runtime

router = APIRouter(prefix="/chat", tags=["AI 聊天 (Chat)"])

class ChatRequest(BaseModel):
    model: str = "gpt-4.1-mini"
    question: str
    uuid: str

@router.post("/chatBot")
@log_print
@add_runtime
def ask(req: ChatRequest):
    chat_response = asyncio.run(ask_AI_Agent(req.question, model=req.model.lower(), session_id=req.uuid))
    return JSONResponse(content={'response': chat_response})