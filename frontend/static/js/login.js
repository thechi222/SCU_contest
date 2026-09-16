import { api, ApiError } from "./api.js";

// 6.3 #1 登入:POST /api/auth/login,成功後導向首頁;失敗時於 #login-error 顯示原因
async function handleLoginSubmit(event) {
  event.preventDefault();
  // TODO
}

document.getElementById("login-form").addEventListener("submit", handleLoginSubmit);
