import { api, ApiError, element, pollState } from "./api.js";

const form = document.getElementById("submit-form");
const limits = document.getElementById("submit-limits");
const error = document.getElementById("submit-error");
const list = document.getElementById("job-list");

const STATUS_TEXT = {
  queued: "排隊中", loading: "準備中", running: "執行中", retrying: "重新排隊",
  completed: "已完成", failed: "失敗", cancelled: "已取消",
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.textContent = "";
  const data = new FormData(form);
  try {
    await api("/api/batches", { method: "POST", body: data });
    form.reset();
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

function render(state) {
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
    list.append(element("p", "empty", "目前沒有工作。上傳檔案後會依序派給可用的 GPU。"));
  }
}

pollState(render);
