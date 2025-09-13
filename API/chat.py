from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio

from services.function_tools import askAI

router = APIRouter(prefix="/chat", tags=["Chat"])
class ChatRequest(BaseModel):
    question: str

@router.post("/chatBot")
def ask(req: ChatRequest):
    chat_response = asyncio.run(askAI(req.question))
    return JSONResponse(content={'response': chat_response})