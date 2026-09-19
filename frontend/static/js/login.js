import { api, ApiError } from "./api.js";

const form = document.getElementById("login-form");
const error = document.getElementById("login-error");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.textContent = "";
  const data = new FormData(form);
  try {
    await api("/api/auth/login", {
      method: "POST",
      body: { email: data.get("email"), password: data.get("password") },
    });
    window.location.assign("/workbench/");
  } catch (err) {
    error.textContent = err instanceof ApiError ? err.message : "登入失敗,請稍後再試";
  }
});
