import { api, ApiError, element } from "./api.js";

const container = document.getElementById("current-user");
// 服務說明與註冊為公開頁面,未登入時只在頁首顯示登入連結,不強制導向
const PUBLIC_PAGES = ["home", "register"];
const optional = PUBLIC_PAGES.includes(document.body.dataset.page);

function showLoginLink() {
  const link = element("a", "login-link", "登入");
  link.href = "/login/";
  container.replaceChildren(link);
}

function showAdminLinks(isAdmin) {
  for (const link of document.querySelectorAll("[data-admin-only]")) {
    link.hidden = !isAdmin;
  }
}

async function renderCurrentUser() {
  try {
    const user = await api("/api/auth/me");
    showAdminLinks(user.is_admin);
    container.replaceChildren(element("span", "user-name", `${user.name}`));

    const logout = element("button", "link-button", "登出");
    logout.addEventListener("click", async () => {
      await api("/api/auth/logout", { method: "POST" });
      window.location.assign("/");
    });
    container.append(logout);
  } catch (err) {
    if (err instanceof ApiError && err.code === "NOT_AUTHENTICATED") {
      if (optional) {
        showLoginLink();
        return;
      }
      window.location.assign("/login/");
      return;
    }
    throw err;
  }
}

renderCurrentUser();
