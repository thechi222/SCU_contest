// 註冊:以學號建立帳號(README §4.11)
import { api, ApiError } from "./api.js";

const form = document.getElementById("register-form");
const errorText = document.getElementById("register-error");
const doneText = document.getElementById("register-done");
const hint = document.getElementById("student-id-hint");

const ID_RULES = {
  student: { text: "學生為 8 碼數字,例如 13173207", test: (value) => /^\d{8}$/.test(value) },
  staff: { text: "教職員為 4–20 碼英數字的員工編號", test: (value) => /^[A-Za-z0-9]{4,20}$/.test(value) },
};

form.role.addEventListener("change", () => {
  hint.textContent = ID_RULES[form.role.value].text;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorText.textContent = "";
  doneText.textContent = "";

  const data = new FormData(form);
  const studentId = String(data.get("student_id") ?? "").replace(/[\s-]/g, "").toUpperCase();
  if (!ID_RULES[data.get("role")].test(studentId)) {
    errorText.textContent = ID_RULES[data.get("role")].text;
    return;
  }
  if (data.get("password") !== data.get("password_confirm")) {
    errorText.textContent = "兩次輸入的密碼不一致";
    return;
  }

  try {
    const result = await api("/api/auth/register", {
      method: "POST",
      body: {
        student_id: studentId,
        name: data.get("name"),
        role: data.get("role"),
        password: data.get("password"),
        email: data.get("email") ?? "",
        invite_code: data.get("invite_code") ?? "",
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
