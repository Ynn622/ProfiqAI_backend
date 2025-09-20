from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio

from services.function_tools import askAI
from util.logger import log_print

router = APIRouter(prefix="/chat", tags=["Chat"])
class ChatRequest(BaseModel):
    model: str = "gpt-4.1-mini"
    question: str

@router.post("/chatBot")
@log_print
def ask(req: ChatRequest):
    chat_response = asyncio.run(askAI(req.question, model=req.model.lower()))
    return JSONResponse(content={'response': chat_response})