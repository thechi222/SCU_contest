// 自由租借:申請、查看連線資訊與結束租借(README §4.10)
import { api, ApiError, element } from "./api.js";

const POLL_INTERVAL = 5000;

const form = document.getElementById("rental-form");
const workspaceSelect = document.getElementById("rental-workspace");
const workspaceNote = document.getElementById("rental-workspace-note");
const minutesInput = document.getElementById("rental-minutes");
const limitsText = document.getElementById("rental-limits");
const errorText = document.getElementById("rental-error");
const currentBox = document.getElementById("rental-current");
const historyBody = document.getElementById("rental-history");
const emptyText = document.getElementById("rental-empty");

const STATUS_TEXT = {
  queued: "排隊中", starting: "啟動中", active: "使用中", ending: "結束中",
  ended: "已結束", expired: "已到期", failed: "啟動失敗", cancelled: "已取消",
};
const OPEN_STATUSES = ["queued", "starting", "active", "ending"];

let workspaces = [];

function describeWorkspace(key) {
  const workspace = workspaces.find((item) => item.key === key);
  if (!workspace) return "";
  const planned = workspace.status === "planned" ? "(映像尚未建置完成)" : "";
  return `${workspace.note}${planned} 最低顯示記憶體 ${Math.round(workspace.min_vram_mb / 1024)} GB。`;
}

function fillWorkspaces(list) {
  if (workspaces.length === list.length) return;
  workspaces = list;
  workspaceSelect.replaceChildren(...list.map((workspace) => {
    const option = element("option", null, workspace.label);
    option.value = workspace.key;
    return option;
  }));
  workspaceNote.textContent = describeWorkspace(workspaceSelect.value);
}

workspaceSelect.addEventListener("change", () => {
  workspaceNote.textContent = describeWorkspace(workspaceSelect.value);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorText.textContent = "";
  const data = new FormData(form);
  try {
    await api("/api/rentals", {
      method: "POST",
      body: {
        workspace: data.get("workspace"),
        minutes: Number(data.get("minutes")),
        purpose: data.get("purpose") ?? "",
      },
    });
    await refresh();
  } catch (err) {
    errorText.textContent = err instanceof ApiError ? err.message : "送出失敗,請稍後再試";
  }
});

async function endRental(rental) {
  errorText.textContent = "";
  try {
    await api(`/api/rentals/${rental.id}/cancel`, { method: "POST" });
    await refresh();
  } catch (err) {
    errorText.textContent = err.message;
  }
}

function countdown(seconds) {
  const total = Math.max(0, Math.round(seconds));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function currentCard(rental) {
  const card = element("article", "card rental-card");
  card.append(element("h3", null, `${rental.workspace_label}(${rental.minutes} 分鐘)`));

  const meta = element("p", null);
  meta.append(element("span", `status status-${rental.status}`, STATUS_TEXT[rental.status] ?? rental.status));
  if (rental.node_name) meta.append(element("span", "cell-muted", ` 設備:${rental.node_name}`));
  if (rental.seconds_left !== null) {
    meta.append(element("span", "rental-countdown", ` 剩餘 ${countdown(rental.seconds_left)}`));
  }
  card.append(meta);

  if (rental.status === "queued") {
    card.append(element("p", "note", "排隊中,等待開放互動式租借的設備空出來。"));
  }
  if (rental.status === "starting") {
    card.append(element("p", "note", "設備正在啟動容器,請稍候。時數自可以連線時才開始計算。"));
  }
  if (rental.status === "active" && rental.connect_url) {
    const link = element("a", "rental-link", rental.connect_url);
    link.href = rental.connect_url;
    link.rel = "noreferrer";
    card.append(element("p", null, "連線位址:"), link);
    if (rental.connect_token) {
      card.append(element("p", "pairing-code", `存取權杖:${rental.connect_token}`));
    }
    card.append(element("p", "note", "權杖僅於租借期間顯示,結束後立即失效。"));
  }

  const button = element("button", "link-button", rental.status === "queued" ? "取消申請" : "結束租借");
  button.addEventListener("click", () => endRental(rental));
  card.append(button);
  return card;
}

function render(data) {
  fillWorkspaces(data.workspaces);
  minutesInput.max = data.limits.max_minutes;
  limitsText.textContent =
    `單次最長 ${data.limits.max_minutes} 分鐘,每日合計 ${data.limits.daily_minutes} 分鐘;` +
    `目前開放互動式租借的設備 ${data.nodes_open_to_rental} 台,排隊中 ${data.queue_length} 段。`;

  const open = data.rentals.filter((rental) => OPEN_STATUSES.includes(rental.status));
  currentBox.replaceChildren(
    ...(open.length ? open.map(currentCard) : [element("p", "empty", "目前沒有進行中的租借。")]),
  );

  historyBody.replaceChildren(...data.rentals.map((rental) => {
    const row = element("tr");
    const when = element("th", null, new Date(rental.created_at).toLocaleString("zh-TW"));
    when.setAttribute("scope", "row");
    const status = element("td");
    status.append(element("span", `status status-${rental.status}`,
                          STATUS_TEXT[rental.status] ?? rental.status));
    row.append(
      when,
      element("td", "cell-muted", rental.workspace_label),
      element("td", "cell-muted", `${rental.minutes} 分鐘`),
      element("td", "cell-muted", rental.node_name ?? "—"),
      status,
      element("td", "cell-muted", rental.end_reason || "—"),
    );
    return row;
  }));
  emptyText.textContent = data.rentals.length ? "" : "尚未申請過租借。";
}

async function refresh() {
  try {
    render(await api("/api/rentals"));
  } catch (err) {
    if (err instanceof ApiError && err.code === "NOT_AUTHENTICATED") {
      window.location.assign("/login/");
      return false;
    }
    console.error(err);
  }
  return true;
}

async function tick() {
  if (await refresh()) {
    window.setTimeout(tick, POLL_INTERVAL);
  }
}

tick();
