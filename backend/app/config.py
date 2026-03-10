# 設定管理: pydantic-settings を使用して環境変数を読み込む
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    chroma_collection_name: str = "help_qa"
    chroma_persist_path: str = "./data/chroma"
    similarity_threshold: float = 0.7
    top_k: int = 6
    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"

settings = Settings()
