/**
 * ヘルプQAチャットボット - Content Script
 * ページに注入されてチャットウィジェットを表示する
 */

(function () {
  "use strict";

  const API_BASE = "http://localhost:8000/api";
  const WIDGET_ID = "hcb-widget";
  const TOGGLE_BTN_ID = "hcb-toggle-btn";

  // 会話履歴（バックエンドに送る形式で蓄積）
  const chatHistory = [];

  // すでに注入済みの場合は何もしない
  if (document.getElementById(WIDGET_ID)) return;

  // ============================================================
  // DOM 構築
  // ============================================================

  function buildWidget() {
    // トグルボタン
    const toggleBtn = document.createElement("button");
    toggleBtn.id = TOGGLE_BTN_ID;
    toggleBtn.setAttribute("aria-label", "ヘルプチャットを開く");
    toggleBtn.setAttribute("title", "ヘルプチャット");
    toggleBtn.innerHTML = "ヘルプチャット";

    // ウィジェット本体
    const widget = document.createElement("div");
    widget.id = WIDGET_ID;
    widget.className = "hcb-hidden";
    widget.setAttribute("role", "dialog");
    widget.setAttribute("aria-label", "ヘルプチャットボット");

    widget.innerHTML = `
      <div class="hcb-header">
        <span>ヘルプチャット</span>
        <button class="hcb-header-close" aria-label="閉じる" title="閉じる">✕</button>
      </div>
      <div class="hcb-messages" id="hcb-messages" role="log" aria-live="polite">
        <div class="hcb-welcome">
          <strong>こんにちは！</strong>
          ご質問をお気軽にどうぞ。よくある質問をもとにお答えします。
        </div>
      </div>
      <div class="hcb-input-area">
        <textarea
          id="hcb-input"
          class="hcb-input"
          placeholder="質問を入力してください..."
          rows="1"
          maxlength="500"
          aria-label="質問入力欄"
        ></textarea>
        <button id="hcb-send-btn" class="hcb-send-btn" aria-label="送信" title="送信">
          ➤
        </button>
      </div>
    `;

    document.body.appendChild(toggleBtn);
    document.body.appendChild(widget);

    return { toggleBtn, widget };
  }

  // ============================================================
  // メッセージ表示ユーティリティ
  // ============================================================

  function getMessagesContainer() {
    return document.getElementById("hcb-messages");
  }

  function scrollToBottom() {
    const container = getMessagesContainer();
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }

  function renderTextWithLinks(el, text) {
    // URLを含む行はリンクに変換、それ以外はテキストノードとして追加
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const lines = text.split("\n");
    lines.forEach((line, i) => {
      if (i > 0) el.appendChild(document.createElement("br"));
      const parts = line.split(urlRegex);
      parts.forEach((part) => {
        if (urlRegex.test(part)) {
          const a = document.createElement("a");
          a.href = part;
          a.textContent = part;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          a.className = "hcb-link";
          el.appendChild(a);
        } else {
          el.appendChild(document.createTextNode(part));
        }
      });
      urlRegex.lastIndex = 0;
    });
  }

  function appendMessage(role, text, extra) {
    const container = getMessagesContainer();
    if (!container) return;

    const msgEl = document.createElement("div");
    msgEl.className = `hcb-message hcb-${role}`;

    const bubble = document.createElement("div");
    bubble.className = "hcb-bubble";
    if (role === "bot") {
      renderTextWithLinks(bubble, text);
    } else {
      bubble.textContent = text;
    }
    msgEl.appendChild(bubble);

    // 関連QAリンク（ボットの回答時のみ）
    if (role === "bot" && extra && extra.matchedQAs) {
      // not_found時はBM25の全候補を関連QAとして表示、通常時は2件目以降を表示
      const relatedQAs = extra.notFound
        ? extra.matchedQAs
        : extra.matchedQAs.slice(1);
      const relatedEl = buildRelatedQAs(relatedQAs);
      if (relatedEl) msgEl.appendChild(relatedEl);
    }

    container.appendChild(msgEl);
    scrollToBottom();
    return msgEl;
  }

  function buildRelatedQAs(qas) {
    if (!qas || qas.length === 0) return null;

    const wrapper = document.createElement("div");
    wrapper.className = "hcb-related";

    const label = document.createElement("div");
    label.className = "hcb-related-label";
    label.textContent = "関連する質問";
    wrapper.appendChild(label);

    qas.forEach((qa) => {
      const item = document.createElement("span");
      item.className = "hcb-related-item";

      item.textContent = qa.question;

      // クリックすると回答を表示
      item.addEventListener("click", () => {
        appendMessage("user", qa.question);
        appendMessage("bot", qa.answer);
      });

      wrapper.appendChild(item);
    });

    return wrapper;
  }

  function showLoading() {
    const container = getMessagesContainer();
    if (!container) return null;

    const loadingEl = document.createElement("div");
    loadingEl.className = "hcb-loading";
    loadingEl.id = "hcb-loading";
    loadingEl.setAttribute("aria-label", "回答を検索中...");
    loadingEl.innerHTML = `
      <div class="hcb-loading-dot"></div>
      <div class="hcb-loading-dot"></div>
      <div class="hcb-loading-dot"></div>
    `;
    container.appendChild(loadingEl);
    scrollToBottom();
    return loadingEl;
  }

  function hideLoading() {
    const loadingEl = document.getElementById("hcb-loading");
    if (loadingEl) loadingEl.remove();
  }

  function showError(message) {
    const container = getMessagesContainer();
    if (!container) return;

    const msgEl = document.createElement("div");
    msgEl.className = "hcb-message hcb-error";

    const bubble = document.createElement("div");
    bubble.className = "hcb-bubble";
    bubble.textContent = message;
    msgEl.appendChild(bubble);

    container.appendChild(msgEl);
    scrollToBottom();
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  // ============================================================
  // API 通信
  // ============================================================

  async function sendMessage(userText) {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userText, history: chatHistory }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `サーバーエラーが発生しました (HTTP ${response.status})`
      );
    }

    return response.json();
  }

  // ============================================================
  // 入力・送信処理
  // ============================================================

  function setInputDisabled(disabled) {
    const input = document.getElementById("hcb-input");
    const sendBtn = document.getElementById("hcb-send-btn");
    if (input) input.disabled = disabled;
    if (sendBtn) sendBtn.disabled = disabled;
  }

  async function handleSend() {
    const input = document.getElementById("hcb-input");
    if (!input) return;

    const userText = input.value.trim();
    if (!userText) return;

    // 入力欄クリア・無効化
    input.value = "";
    input.style.height = "auto";
    setInputDisabled(true);

    // ユーザーメッセージ表示
    appendMessage("user", userText);

    // ローディング表示
    const loadingEl = showLoading();

    try {
      const data = await sendMessage(userText);
      hideLoading();

      // 履歴に追加
      chatHistory.push({ role: "user", content: userText });
      chatHistory.push({ role: "assistant", content: data.answer });

      appendMessage("bot", data.answer, {
        matchedQAs: data.matched_qas || [],
        notFound: data.not_found || false,
      });
    } catch (err) {
      hideLoading();
      console.error("[HCB] チャットエラー:", err);

      const errorMsg =
        err instanceof TypeError
          ? "バックエンドサーバーに接続できません。サーバーが起動しているか確認してください。"
          : err.message || "エラーが発生しました。しばらくしてからお試しください。";

      showError(errorMsg);
    } finally {
      setInputDisabled(false);
      if (input) input.focus();
    }
  }

  // ============================================================
  // テキストエリアの自動リサイズ
  // ============================================================

  function autoResizeTextarea(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 100) + "px";
  }

  // ============================================================
  // ウィジェット開閉
  // ============================================================

  function openWidget(widget, toggleBtn) {
    widget.classList.remove("hcb-hidden");
    toggleBtn.innerHTML = "ヘルプチャット ✕";
    toggleBtn.setAttribute("aria-label", "ヘルプチャットを閉じる");

    // フォーカスをインプットに移動
    setTimeout(() => {
      const input = document.getElementById("hcb-input");
      if (input) input.focus();
    }, 280);
  }

  function closeWidget(widget, toggleBtn) {
    widget.classList.add("hcb-hidden");
    toggleBtn.innerHTML = "ヘルプチャット";
    toggleBtn.setAttribute("aria-label", "ヘルプチャットを開く");
    toggleBtn.focus();
  }

  function toggleWidget(widget, toggleBtn) {
    if (widget.classList.contains("hcb-hidden")) {
      openWidget(widget, toggleBtn);
    } else {
      closeWidget(widget, toggleBtn);
    }
  }

  // ============================================================
  // イベントリスナー登録
  // ============================================================

  function bindEvents(toggleBtn, widget) {
    // トグルボタンクリック
    toggleBtn.addEventListener("click", () => toggleWidget(widget, toggleBtn));

    // 閉じるボタンクリック
    const closeBtn = widget.querySelector(".hcb-header-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => closeWidget(widget, toggleBtn));
    }

    // 送信ボタンクリック
    const sendBtn = document.getElementById("hcb-send-btn");
    if (sendBtn) {
      sendBtn.addEventListener("click", handleSend);
    }

    // テキストエリアキーイベント
    const input = document.getElementById("hcb-input");
    if (input) {
      // Enter で送信（Shift+Enter は改行）
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          handleSend();
        }
      });

      // 自動リサイズ
      input.addEventListener("input", () => autoResizeTextarea(input));
    }

    // Escape でウィジェットを閉じる
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !widget.classList.contains("hcb-hidden")) {
        closeWidget(widget, toggleBtn);
      }
    });

    // ウィジェット外クリックで閉じる（オプション：コメントアウトで無効化可）
    // document.addEventListener("click", (e) => {
    //   if (
    //     !widget.contains(e.target) &&
    //     !toggleBtn.contains(e.target) &&
    //     !widget.classList.contains("hcb-hidden")
    //   ) {
    //     closeWidget(widget, toggleBtn);
    //   }
    // });
  }

  // ============================================================
  // 初期化
  // ============================================================

  function init() {
    const { toggleBtn, widget } = buildWidget();
    bindEvents(toggleBtn, widget);
    // 初期状態のテキストエリアの高さを正しく設定
    const input = document.getElementById("hcb-input");
    if (input) autoResizeTextarea(input);
    console.log("[HCB] ヘルプQAチャットボット ウィジェットを読み込みました");
  }

  // DOM の準備ができてから実行
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
