import { api, ApiError, element } from "./api.js";

const container = document.getElementById("current-user");

async function renderCurrentUser() {
  try {
    const user = await api("/api/auth/me");
    container.replaceChildren(element("span", "user-name", `${user.name}(${user.role}）`));

    const logout = element("button", "link-button", "登出");
    logout.addEventListener("click", async () => {
      await api("/api/auth/logout", { method: "POST" });
      window.location.assign("/login/");
    });
    container.append(logout);
  } catch (err) {
    if (err instanceof ApiError && err.code === "NOT_AUTHENTICATED") {
      window.location.assign("/login/");
      return;
    }
    throw err;
  }
}

renderCurrentUser();
