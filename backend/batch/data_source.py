# QAデータソースの抽象化レイヤー
# 将来的にスクレイピングやAPIからの取得に差し替えやすくするための設計
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# サンプルJSONファイルのパス
SAMPLE_JSON_PATH = Path(__file__).parent / "sample_qa.json"

def load_qa_data() -> list[dict]:
    """
    QAデータを読み込む。
    現在はサンプルJSONから読み込む。
    将来的にはスクレイピングやCMS APIからの取得に差し替え可能。
    """
    return _load_from_json(SAMPLE_JSON_PATH)

def _load_from_json(path: Path) -> list[dict]:
    """JSONファイルからQAデータを読み込む"""
    if not path.exists():
        raise FileNotFoundError(f"QAデータファイルが見つかりません: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"JSONから {len(data)} 件のQAを読み込みました: {path}")
    return data

# 将来のスクレイピング実装のためのプレースホルダー
# def _load_from_scraping(url: str) -> list[dict]:
#     """ヘルプページをスクレイピングしてQAを抽出する（将来実装）"""
#     raise NotImplementedError("スクレイピング機能は未実装です")
