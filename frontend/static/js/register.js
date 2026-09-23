// 註冊:以學號建立帳號(README §4.11)
import { api, ApiError } from "./api.js";

const form = document.getElementById("register-form");
const errorText = document.getElementById("register-error");
const doneText = document.getElementById("register-done");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorText.textContent = "";
  doneText.textContent = "";

  const data = new FormData(form);
  if (data.get("password") !== data.get("password_confirm")) {
    errorText.textContent = "兩次輸入的密碼不一致";
    return;
  }

  try {
    const result = await api("/api/auth/register", {
      method: "POST",
      body: {
        student_id: data.get("student_id"),
        name: data.get("name"),
        role: data.get("role"),
        password: data.get("password"),
        email: data.get("email") ?? "",
      },
    });
    // 需要管理者核可時後端回傳 status=pending,此時不會自動登入
    if (result?.status === "pending") {
      form.reset();
      doneText.textContent = result.detail;
      return;
    }
    window.location.assign("/workbench/");
  } catch (err) {
    errorText.textContent = err instanceof ApiError ? err.message : "註冊失敗,請稍後再試";
  }
});
