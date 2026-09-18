import { api } from "./api.js";

// 6.3 AI 助理對話框:POST /api/ai/assist,顯示回覆與(若有)助理代為送出的批次
async function handleChatSubmit(event) {
  event.preventDefault();
  // TODO
}

document.getElementById("chat-form").addEventListener("submit", handleChatSubmit);
