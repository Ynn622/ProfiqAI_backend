from openai import OpenAI

from util.config import Env

ai = OpenAI(api_key=Env.OPENAI_API_KEY)

def ask_AI(question: str) -> str:
    response = ai.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "你是一名台灣股票分析師。請摘要並簡潔分析。(約100字)"},
            {"role": "user", "content": question}
        ],
        max_completion_tokens=10000,
    )
    text = response.choices[0].message.content
    return text