from dotenv import load_dotenv, find_dotenv
import os

# 自動尋找專案根目錄的 .env
load_dotenv(find_dotenv(), override=False)

# 統一管理環境變數
class Env:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    DOCS_PASSWORD: str = os.getenv("DOCS_PASSWORD", "")
    DOCS_USERNAME: str = os.getenv("DOCS_USERNAME", "")
    RELOAD: bool = os.getenv("RELOAD", "").lower() == "true"
    PORT: int = int(os.getenv("PORT", 7860))    # Hugging Face Spaces 預設使用 7860 port
    
env = Env()