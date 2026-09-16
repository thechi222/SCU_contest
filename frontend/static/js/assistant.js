import { api } from "./api.js";

// 6.3 #7 AI 助理對話框:POST /api/ai/assist,顯示回覆與新建立的預約
async function handleChatSubmit(event) {
  event.preventDefault();
  // TODO
}

document.getElementById("chat-form").addEventListener("submit", handleChatSubmit);
