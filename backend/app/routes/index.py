import logging
from fastapi import APIRouter, HTTPException
from ..models import IndexResponse
from ..vector_store import vector_store
from batch.data_source import load_qa_data

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/index", response_model=IndexResponse)
async def reindex():
    """QAデータを再投入するエンドポイント"""
    try:
        qa_items = load_qa_data()
        count = vector_store.upsert(qa_items)
        return IndexResponse(status="ok", indexed_count=count)
    except Exception as e:
        logger.error(f"インデックス投入エラー: {e}")
        raise HTTPException(status_code=500, detail="インデックス処理中にエラーが発生しました")
