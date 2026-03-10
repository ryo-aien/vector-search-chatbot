/**
 * ヘルプQAチャットボット - Background Service Worker
 * 拡張機能のバックグラウンド処理を担う
 */

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    console.log("[HCB] ヘルプQAチャットボット拡張機能がインストールされました");
  } else if (details.reason === "update") {
    console.log(
      `[HCB] ヘルプQAチャットボット拡張機能がバージョン ${chrome.runtime.getManifest().version} に更新されました`
    );
  }
});
