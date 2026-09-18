// 所有 API 呼叫一律經由本模組(README §4.7)

export class ApiError extends Error {
  constructor(status, detail, code) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

function getCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export async function api(path, { method = "GET", body } = {}) {
  const isForm = body instanceof FormData;
  const headers = { Accept: "application/json" };
  if (body !== undefined && !isForm) {
    headers["Content-Type"] = "application/json";
  }
  const csrfToken = getCookie("csrftoken");
  if (method !== "GET" && csrfToken) {
    headers["X-CSRFToken"] = csrfToken;
  }

  const response = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  });

  if (response.status === 204) {
    return null;
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      response.status,
      data?.detail ?? response.statusText,
      data?.code ?? "UNKNOWN_ERROR",
    );
  }
  return data;
}

export function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/** 每 interval 毫秒輪詢 /api/state,未登入時導向登入頁。 */
export function pollState(render, interval = 2000) {
  async function tick() {
    try {
      render(await api("/api/state"));
    } catch (err) {
      if (err instanceof ApiError && err.code === "NOT_AUTHENTICATED") {
        window.location.assign("/login/");
        return;
      }
      console.error(err);
    }
    window.setTimeout(tick, interval);
  }
  tick();
}
