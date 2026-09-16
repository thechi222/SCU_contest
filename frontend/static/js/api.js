// 所有 API 呼叫一律經由本模組(README §4.9)

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
  const headers = { Accept: "application/json" };
  if (body !== undefined) {
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
    body: body === undefined ? undefined : JSON.stringify(body),
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
