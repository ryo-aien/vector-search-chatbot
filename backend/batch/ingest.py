"""
QAデータのEmbedding投入バッチスクリプト
使い方: python -m batch.ingest
"""
import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    from app.vector_store import vector_store
    from batch.data_source import load_qa_data

    logger.info("QAデータのインデックス投入を開始します")
    qa_items = load_qa_data()
    logger.info(f"読み込んだQA件数: {len(qa_items)}")

    count = vector_store.upsert(qa_items)
    logger.info(f"インデックス投入完了: {count} 件")

if __name__ == "__main__":
    main()
