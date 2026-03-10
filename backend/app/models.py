# APIリクエスト・レスポンスのPydanticモデル定義
from pydantic import BaseModel, Field
from typing import Optional

class HistoryMessage(BaseModel):
    role: str = Field(..., description="'user' または 'assistant'")
    content: str = Field(..., description="メッセージ内容")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="ユーザーの質問文")
    history: list[HistoryMessage] = Field(default=[], description="過去の会話履歴")

class MatchedQA(BaseModel):
    question: str
    answer: str
    score: float
    category: Optional[str] = None
    url: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    matched_qas: list[MatchedQA]
    not_found: bool = False

class HealthResponse(BaseModel):
    status: str

class IndexResponse(BaseModel):
    status: str
    indexed_count: int
