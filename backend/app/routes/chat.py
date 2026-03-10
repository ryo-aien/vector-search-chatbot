import logging
from fastapi import APIRouter, HTTPException
from openai import OpenAI
from ..config import settings
from ..models import ChatRequest, ChatResponse, HistoryMessage, MatchedQA
from ..vector_store import vector_store

logger = logging.getLogger(__name__)
router = APIRouter()

_openai = OpenAI(api_key=settings.openai_api_key)

NOT_FOUND_MESSAGE = "申し訳ありませんが、該当する情報が見つかりませんでした。お問い合わせページからご連絡ください。"

SYSTEM_PROMPT = """あなたはサポートページのヘルプQAアシスタントです。
以下の「参考QA」をもとに、ユーザーの質問に対して回答してください。

ルール:
- 参考QAの情報のみを使って回答すること
- 前置き・補足・説明は不要。答えだけを返すこと
- 参考QAに答えが含まれない場合は「その情報は持ち合わせておりません」とだけ答えること
- 敬語を使うこと
- ユーザーの入力が単語のみ・極端に短い・質問として成立していない場合は「その情報は持ち合わせておりません」とだけ答えること

回答の粒度ルール（最重要）:
- 質問に特定の条件・対象・状況が含まれる場合（具体的な質問）→ その条件に該当する情報だけを答えること。それ以外の情報は含めないこと
- 質問に条件・対象・状況が含まれない場合（抽象的・包括的な質問）→ 参考QAにある関連情報をすべて漏れなく答えること"""

def _build_context(matched: list[dict]) -> str:
    """検索結果のQAをGPTへ渡すコンテキスト文字列に整形する"""
    lines = []
    for i, qa in enumerate(matched, 1):
        lines.append(f"【参考QA {i}】")
        lines.append(f"質問: {qa['question']}")
        lines.append(f"回答: {qa['answer']}")
        if qa.get("url"):
            lines.append(f"詳細URL: {qa['url']}")
        lines.append("")
    return "\n".join(lines)

def _generate_answer(user_message: str, matched: list[dict], history: list[HistoryMessage]) -> str:
    """ベクトル検索結果をコンテキストにGPTで回答を生成する（会話履歴付き）"""
    context = _build_context(matched)

    # システムプロンプト + 参考QAコンテキスト
    system_content = f"{SYSTEM_PROMPT}\n\n参考QA:\n{context}"

    # 会話履歴をOpenAI形式に変換（直近10件まで）
    history_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in history[-10:]
    ]

    response = _openai.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": system_content},
            *history_messages,
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # ベクトル検索
    try:
        matched = vector_store.search(req.message)
    except Exception as e:
        logger.error(f"ベクトル検索エラー: {e}")
        raise HTTPException(status_code=500, detail="検索処理中にエラーが発生しました")

    if not matched:
        # キーワードマッチで関連候補を探して「関連する質問」として返す
        keyword_matched = vector_store.keyword_search(req.message)
        matched_qas = [MatchedQA(**m) for m in keyword_matched]
        return ChatResponse(answer=NOT_FOUND_MESSAGE, matched_qas=matched_qas, not_found=True)

    # GPTで自然な回答を生成
    try:
        answer = _generate_answer(req.message, matched, req.history)
    except Exception as e:
        logger.error(f"LLM回答生成エラー: {e}")
        # LLM失敗時はベクトル検索の最上位回答にフォールバック
        answer = matched[0]["answer"]

    # GPTが「情報なし」と判断した場合はNOT_FOUND_MESSAGEに差し替え＋BM25で関連候補を取得
    if "その情報は持ち合わせておりません" in answer:
        answer = NOT_FOUND_MESSAGE
        keyword_matched = vector_store.keyword_search(req.message)
        matched_qas = [MatchedQA(**m) for m in keyword_matched]
        return ChatResponse(answer=answer, matched_qas=matched_qas, not_found=True)

    matched_qas = [MatchedQA(**m) for m in matched]
    return ChatResponse(answer=answer, matched_qas=matched_qas)
