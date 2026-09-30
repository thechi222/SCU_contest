// 工作台:建立任務環境後自行進容器操作,另保留交給平台代跑的批次上傳(README §4.10)
import { api, ApiError, element } from "./api.js";

const POLL_INTERVAL = 3000;

const sessionForm = document.getElementById("session-form");
const workspaceSelect = document.getElementById("session-workspace");
const sessionNote = document.getElementById("session-note");
const sessionLimits = document.getElementById("session-limits");
const sessionError = document.getElementById("session-error");
const sessionBox = document.getElementById("session-current");
const minutesInput = document.getElementById("session-minutes");

const form = document.getElementById("submit-form");
const kindSelect = document.getElementById("kind-select");
const kindNote = document.getElementById("kind-note");
const limits = document.getElementById("submit-limits");
const error = document.getElementById("submit-error");
const list = document.getElementById("job-list");

const STATUS_TEXT = {
  queued: "排隊中", loading: "準備中", running: "執行中", retrying: "重新排隊",
  completed: "已完成", failed: "失敗", cancelled: "已取消",
};
const SESSION_STATUS = {
  queued: "等待設備", starting: "準備環境", active: "可以使用", ending: "結束中",
  ended: "已結束", expired: "已到期", failed: "建置失敗", cancelled: "已取消",
};
const OPEN_STATUSES = ["queued", "starting", "active", "ending"];
const ENTRY_TEXT = { jupyter: "JupyterLab", shell: "終端機" };

let tasks = [];
let environments = [];

/* ---------- 任務環境(主要流程) ---------- */

function describeEnvironment() {
  const item = environments.find((env) => env.key === workspaceSelect.value);
  if (!item) {
    sessionNote.textContent = "";
    return;
  }
  const ready = item.ready_nodes
    ? `目前 ${item.ready_nodes} 台設備已備妥此環境,可直接開始`
    : `目前沒有設備預先備妥,平台會在領到的設備上自動建置(需要幾分鐘)`;
  sessionNote.textContent =
    `內含 ${item.includes.join("、")};以${ENTRY_TEXT[item.entry] ?? item.entry}進入。${ready}。`;
}

function fillEnvironments(catalog) {
  // 工作台只列對應任務類型的環境;通用開發環境在「自由租借」頁面
  const taskEnvironments = catalog.filter((item) => item.kind);
  if (environments.length !== taskEnvironments.length) {
    environments = taskEnvironments;
    workspaceSelect.replaceChildren(...taskEnvironments.map((item) => {
      const option = element("option", null,
                             item.status === "available" ? item.label : `${item.label}(準備中)`);
      option.value = item.key;
      option.disabled = item.status !== "available";
      return option;
    }));
    const first = taskEnvironments.find((item) => item.status === "available");
    if (first) workspaceSelect.value = first.key;
  }
  describeEnvironment();
}

workspaceSelect.addEventListener("change", describeEnvironment);

sessionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  sessionError.textContent = "";
  const data = new FormData(sessionForm);
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
    sessionError.textContent = err instanceof ApiError ? err.message : "建立失敗,請稍後再試";
  }
});

async function endSession(session) {
  sessionError.textContent = "";
  try {
    await api(`/api/rentals/${session.id}/cancel`, { method: "POST" });
    await refresh();
  } catch (err) {
    sessionError.textContent = err.message;
  }
}

function countdown(seconds) {
  const total = Math.max(0, Math.round(seconds));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function progressBar(value) {
  const wrap = element("div", "bar");
  const fill = element("span", "bar-fill");
  fill.style.width = `${Math.round((value ?? 0) * 100)}%`;
  wrap.append(fill);
  const box = element("div", "bar-box");
  box.append(wrap, element("span", "bar-text", value === null ? "—" : `${Math.round(value * 100)}%`));
  return box;
}

function sessionCard(session) {
  const card = element("article", "card rental-card");
  card.append(element("h3", null, `${session.workspace_label}(${session.minutes} 分鐘)`));

  const meta = element("p", null);
  meta.append(element("span", `status status-${session.status}`,
                      SESSION_STATUS[session.status] ?? session.status));
  if (session.node_name) meta.append(element("span", "cell-muted", ` 設備:${session.node_name}`));
  if (session.seconds_left !== null) {
    meta.append(element("span", "rental-countdown", ` 剩餘 ${countdown(session.seconds_left)}`));
  }
  card.append(meta);

  if (session.status === "queued") {
    card.append(element("p", "note", "等待開放接受租借的閒置設備;輪到時會自動開始建置。"));
  }
  if (session.status === "starting") {
    card.append(
      element("p", "note", session.prepared
        ? `這台設備已備妥環境,正在${session.stage}。`
        : `設備正在自動建置環境:${session.stage}。首次建置需要下載映像與模型,請稍候。`),
      progressBar(session.progress),
    );
  }
  if (session.status === "active") {
    if (session.connect_url) {
      const link = element("a", "rental-link", session.connect_url);
      link.href = session.connect_url;
      link.rel = "noreferrer";
      link.target = "_blank";
      card.append(
        element("p", null, `以${ENTRY_TEXT[session.entry] ?? session.entry}進入:`),
        link,
      );
      if (session.connect_token) {
        card.append(element("p", "pairing-code", `存取權杖:${session.connect_token}`));
      }
    }
    card.append(element("p", "note",
                        `環境內含 ${session.includes.join("、")};結束後容器與其中的資料會一併清除。`));
  }
  if (["failed", "expired", "ended"].includes(session.status) && session.end_reason) {
    card.append(element("p", "note", session.end_reason));
  }

  if (OPEN_STATUSES.includes(session.status)) {
    const button = element("button", "link-button",
                           session.status === "queued" ? "取消" : "結束環境");
    button.addEventListener("click", () => endSession(session));
    card.append(button);
  }
  return card;
}

function renderSessions(data) {
  fillEnvironments(data.workspaces);
  minutesInput.max = data.limits.max_minutes;
  sessionLimits.textContent =
    `單次最長 ${data.limits.max_minutes} 分鐘,每日合計 ${data.limits.daily_minutes} 分鐘;` +
    `目前開放的設備 ${data.nodes_open_to_rental} 台,排隊中 ${data.queue_length} 件。`;

  const open = data.rentals.filter((item) => OPEN_STATUSES.includes(item.status));
  sessionBox.replaceChildren(...(open.length
    ? open.map(sessionCard)
    : [element("p", "empty", "目前沒有進行中的工作環境。")]));
}

/* ---------- 交給平台代跑(既有批次流程) ---------- */

function fillKinds(catalog) {
  if (tasks.length === catalog.length) return;
  tasks = catalog;
  kindSelect.replaceChildren(...catalog.map((task) => {
    const option = element("option", null,
                           task.status === "available" ? task.label : `${task.label}(準備中)`);
    option.value = task.kind;
    option.disabled = task.status !== "available";
    return option;
  }));
  const first = catalog.find((task) => task.status === "available");
  if (first) kindSelect.value = first.kind;
  describeKind();
}

function describeKind() {
  const task = tasks.find((item) => item.kind === kindSelect.value);
  kindNote.textContent = task
    ? `輸入:${task.inputs};成果:${task.artifacts.join("、")}。${task.note}`
    : "";
}

kindSelect.addEventListener("change", describeKind);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.textContent = "";
  const data = new FormData(form);
  try {
    await api("/api/batches", { method: "POST", body: data });
    form.reset();
    await refresh();
  } catch (err) {
    error.textContent = err instanceof ApiError ? err.message : "送出失敗,請稍後再試";
  }
});

function jobRow(job) {
  const row = element("div", "job-row");
  row.append(
    element("span", "job-name", job.filename),
    element("span", `status status-${job.status}`, STATUS_TEXT[job.status] ?? job.status),
    element("span", "job-stage", job.status === "completed" ? "" : job.stage),
  );

  for (const artifact of job.artifacts) {
    const link = element("a", "artifact", artifact.name);
    link.href = `/api/artifacts/${artifact.id}`;
    row.append(link);
  }
  if (job.error) {
    row.append(element("span", "job-error", job.error));
  }

  const action = ["completed", "failed", "cancelled"].includes(job.status) ? "retry" : "cancel";
  if (!(action === "retry" && job.status === "completed")) {
    const button = element("button", "link-button", action === "retry" ? "重送" : "取消");
    button.addEventListener("click", async () => {
      try {
        await api(`/api/jobs/${job.id}/${action}`, { method: "POST" });
      } catch (err) {
        error.textContent = err.message;
      }
    });
    row.append(button);
  }
  return row;
}

function renderState(state) {
  fillKinds(state.tasks);
  const megabytes = Math.round(state.limits.max_file_bytes / 1024 / 1024);
  limits.textContent =
    `每批最多 ${state.limits.max_batch_files} 個檔案,單檔 ${megabytes} MB;` +
    `同時執行上限 ${state.limits.max_running} 件,每日 ${state.limits.daily_limit} 個檔案。`;

  list.replaceChildren();
  for (const batch of state.batches) {
    const section = element("article", "batch");
    const heading = element("h3", null, `${batch.name}(${batch.kind})`);
    section.append(heading);

    const download = element("a", "link-button", "下載整批成果");
    download.href = `/api/batches/${batch.id}/download`;
    heading.append(" ", download);

    for (const job of batch.jobs) {
      section.append(jobRow(job));
    }
    list.append(section);
  }
  if (!state.batches.length) {
    list.append(element("p", "empty", "目前沒有代跑的工作。"));
  }
}

async function refresh() {
  try {
    const [state, sessions] = await Promise.all([api("/api/state"), api("/api/rentals")]);
    renderState(state);
    renderSessions(sessions);
    return true;
  } catch (err) {
    if (err instanceof ApiError && err.code === "NOT_AUTHENTICATED") {
      window.location.assign("/login/");
      return false;
    }
    console.error(err);
    return true;
  }
}

async function tick() {
  if (await refresh()) {
    window.setTimeout(tick, POLL_INTERVAL);
  }
}

tick();
