// 管理台:帳號審核與全平台使用情形(README §4.12)
import { api, ApiError, element } from "./api.js";

const POLL_INTERVAL = 10000;

const summaryBox = document.getElementById("manage-summary");
const pendingBox = document.getElementById("pending-users");
const usersBody = document.getElementById("manage-users");
const jobsBody = document.getElementById("manage-jobs");
const rentalsBody = document.getElementById("manage-rentals");
const eventsBox = document.getElementById("manage-events");
const errorText = document.getElementById("manage-error");

const ROLE_TEXT = { student: "學生", staff: "教職員" };
const JOB_STATUS = {
  queued: "排隊中", loading: "準備中", running: "執行中", retrying: "重新排隊",
  completed: "已完成", failed: "失敗", cancelled: "已取消",
};
const RENTAL_STATUS = {
  queued: "排隊中", starting: "啟動中", active: "使用中", ending: "結束中",
  ended: "已結束", expired: "已到期", failed: "啟動失敗", cancelled: "已取消",
};

function metric(label, value, hint) {
  const card = element("div", "metric");
  card.append(element("p", "metric-label", label), element("p", "metric-value", String(value)));
  if (hint) card.append(element("p", "metric-hint", hint));
  return card;
}

function when(value) {
  return value ? new Date(value).toLocaleString("zh-TW") : "—";
}

async function patchUser(userId, body) {
  errorText.textContent = "";
  try {
    await api(`/api/admin/users/${userId}`, { method: "PATCH", body });
    await refresh();
  } catch (err) {
    errorText.textContent = err.message;
  }
}

function actionButton(label, userId, body) {
  const button = element("button", "link-button", label);
  button.addEventListener("click", () => patchUser(userId, body));
  return button;
}

function userRow(user) {
  const row = element("tr");
  const id = element("th", null, user.student_id);
  id.setAttribute("scope", "row");
  if (user.is_admin) id.append(element("span", "tag", "管理員"));

  const status = element("td");
  status.append(element("span", user.is_active ? "status status-idle" : "status status-offline",
                        user.is_active ? "已啟用" : "待核可"));

  const actions = element("td");
  actions.append(user.is_active
    ? actionButton("停用", user.id, { is_active: false })
    : actionButton("核可", user.id, { is_active: true }));
  actions.append(user.is_admin
    ? actionButton("取消管理員", user.id, { is_admin: false })
    : actionButton("設為管理員", user.id, { is_admin: true }));

  row.append(
    id,
    element("td", "cell-muted", user.name),
    element("td", "cell-muted", ROLE_TEXT[user.role] ?? user.role),
    status,
    element("td", "cell-muted", `${user.jobs_today} / ${user.jobs_total}`),
    element("td", "cell-muted", String(user.nodes_total)),
    element("td", "cell-muted", `${user.max_running} / ${user.daily_limit}`),
    element("td", "cell-muted", when(user.date_joined)),
    actions,
  );
  return row;
}

function render(data) {
  const s = data.summary;
  summaryBox.replaceChildren(
    metric("註冊帳號", s.users_total, `管理員 ${s.users_admin} 人`),
    metric("待核可", s.users_pending, s.users_pending ? "需要處理" : "目前沒有"),
    metric("今日工作", s.jobs_today, `排隊 ${s.jobs_queued},執行中 ${s.jobs_running}`),
    metric("登錄設備", s.nodes_total, `線上 ${data.usage.nodes_online},閒置 ${data.usage.nodes_idle}`),
    metric("互動式租借", s.rentals_open, "排隊與使用中合計"),
  );

  pendingBox.replaceChildren(...(data.pending_users.length
    ? [(() => {
        const list = element("div");
        for (const user of data.pending_users) {
          const line = element("div", "node-row");
          line.append(
            element("span", "node-name", `${user.student_id} ${user.name}`),
            element("span", "cell-muted", ROLE_TEXT[user.role] ?? user.role),
            element("span", "cell-muted", when(user.date_joined)),
            actionButton("核可", user.id, { is_active: true }),
          );
          list.append(line);
        }
        return list;
      })()]
    : [element("p", "empty", "目前沒有待核可的帳號。")]));

  usersBody.replaceChildren(...data.users.map(userRow));

  jobsBody.replaceChildren(...data.jobs.map((job) => {
    const row = element("tr");
    const time = element("th", null, when(job.created_at));
    time.setAttribute("scope", "row");
    const status = element("td");
    status.append(element("span", `status status-${job.status}`, JOB_STATUS[job.status] ?? job.status));
    row.append(
      time,
      element("td", "cell-muted", `${job.user}(${job.user_name})`),
      element("td", "cell-muted", job.filename),
      element("td", "cell-muted", job.kind),
      status,
      element("td", "cell-muted", String(job.attempt_count)),
    );
    return row;
  }));

  rentalsBody.replaceChildren(...data.rentals.map((rental) => {
    const row = element("tr");
    const time = element("th", null, when(rental.created_at));
    time.setAttribute("scope", "row");
    const status = element("td");
    status.append(element("span", `status status-${rental.status}`,
                          RENTAL_STATUS[rental.status] ?? rental.status));
    row.append(
      time,
      element("td", "cell-muted", rental.workspace_label),
      element("td", "cell-muted", `${rental.minutes} 分鐘`),
      element("td", "cell-muted", rental.node_name ?? "—"),
      status,
    );
    return row;
  }));

  eventsBox.replaceChildren(...(data.events.length
    ? data.events.map((event) => element(
        "p", "cell-muted", `${when(event.created_at)}｜${event.user ?? "—"}｜${event.message}`))
    : [element("p", "empty", "尚無事件紀錄。")]));
}

async function refresh() {
  try {
    render(await api("/api/admin/overview"));
    return true;
  } catch (err) {
    if (err instanceof ApiError && err.code === "NOT_AUTHENTICATED") {
      window.location.assign("/login/");
      return false;
    }
    if (err instanceof ApiError && err.code === "PERMISSION_DENIED") {
      errorText.textContent = "這個頁面僅限管理員使用。";
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
