# ChromaDB のラッパー: Embedding生成・保存・近傍検索を担う
import logging
from typing import Optional
import fugashi
from rank_bm25 import BM25Okapi
import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI
from .config import settings

# unidic-lite の辞書パスを明示して初期化
import unidic_lite
_tagger = fugashi.Tagger(f'-d {unidic_lite.DICDIR}')

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        self.openai = OpenAI(api_key=settings.openai_api_key)

    def embed(self, text: str) -> list[float]:
        """テキストをEmbeddingベクトルに変換する"""
        response = self.openai.embeddings.create(
            input=text,
            model=settings.openai_embedding_model
        )
        return response.data[0].embedding

    def upsert(self, qa_items: list[dict]) -> int:
        """QAデータをEmbeddingしてベクトルDBに保存する（冪等）"""
        ids, embeddings, documents, metadatas = [], [], [], []

        for item in qa_items:
            # 質問と回答を連結してEmbeddingすることで両方を検索対象にする
            combined_text = f"質問: {item['question']}\n回答: {item['answer']}"
            vector = self.embed(combined_text)

            qa_id = item.get("id", item["question"][:50])
            ids.append(qa_id)
            embeddings.append(vector)
            documents.append(combined_text)
            metadatas.append({
                "question": item["question"],
                "answer": item["answer"],
                "category": item.get("category", ""),
                "url": item.get("url", ""),
            })

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(f"{len(ids)} 件のQAをインデックスに登録しました")
        return len(ids)

    def search(self, query: str, top_k: int = None, threshold: float = None) -> list[dict]:
        """クエリに近いQAを検索する"""
        top_k = top_k or settings.top_k
        threshold = threshold if threshold is not None else settings.similarity_threshold

        query_vector = self.embed(query)
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["metadatas", "distances"]
        )

        matched = []
        for meta, distance in zip(results["metadatas"][0], results["distances"][0]):
            # ChromaDB cosine space の距離は 0〜2 の範囲
            # → (2 - distance) / 2 で 0〜1 の類似度スコアに変換
            score = (2.0 - distance) / 2.0
            logger.info(f"distance={distance:.4f} score={score:.4f} question={meta['question'][:30]}")
            if score >= threshold:
                matched.append({
                    "question": meta["question"],
                    "answer": meta["answer"],
                    "score": round(score, 4),
                    "category": meta.get("category") or None,
                    "url": meta.get("url") or None,
                })
        return matched

    def keyword_search(self, query: str, top_k: int = None) -> list[dict]:
        """BM25 によるキーワード検索（ベクトル検索がヒットしなかった場合のフォールバック）

        MeCab で名詞・動詞の基本形を抽出してトークナイズするため、
        「パスワードの再設定」→「パスワード」「再設定」のように
        表現ゆれに汎用的に対応できる。
        """
        top_k = top_k or settings.top_k

        all_results = self.collection.get(include=["metadatas", "documents"])
        metadatas = all_results["metadatas"]
        documents = all_results["documents"]

        if not documents:
            return []

        def tokenize(text: str) -> list[str]:
            tokens = []
            for word in _tagger(text):
                # unidic-lite では word.feature が UnidicFeatures26 オブジェクト
                pos = word.feature.pos1  # 品詞大分類
                # 名詞・動詞・形容詞のみ対象
                if pos not in ("名詞", "動詞", "形容詞"):
                    continue
                # lemma（見出し語）を使用、なければ表層形
                lemma = word.feature.lemma
                token = lemma if lemma and lemma != "*" else word.surface
                if token.strip():
                    tokens.append(token)
            return tokens

        tokenized_corpus = [tokenize(doc) for doc in documents]
        bm25 = BM25Okapi(tokenized_corpus)

        tokenized_query = tokenize(query)
        logger.info(f"BM25クエリトークン: {tokenized_query}")
        scores = bm25.get_scores(tokenized_query)

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        matched = []
        for idx, score in ranked:
            if score <= 0:
                break
            meta = metadatas[idx]
            matched.append({
                "question": meta["question"],
                "answer": meta["answer"],
                "score": round(float(score), 4),
                "category": meta.get("category") or None,
                "url": meta.get("url") or None,
            })
            if len(matched) >= top_k:
                break

        logger.info(f"BM25検索: {len(matched)} 件ヒット")
        return matched

# アプリ全体で使う共有インスタンス
vector_store = VectorStore()
