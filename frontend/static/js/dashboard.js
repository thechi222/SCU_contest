// 閒置算力儀表板:輪詢 /api/usage/summary,繪製各機台狀態與每日用量(README §4.9)
import { api, ApiError, element } from "./api.js";

const POLL_INTERVAL = 5000;

const totalsBox = document.getElementById("usage-totals");
const nodesBody = document.getElementById("usage-nodes");
const daysBody = document.getElementById("usage-days");
const nodesEmpty = document.getElementById("usage-empty");
const daysEmpty = document.getElementById("days-empty");
const updatedAt = document.getElementById("usage-updated");

const STATE_TEXT = {
  busy: "執行工作", rented: "租借中", idle: "閒置可用", paused: "未開放", offline: "離線",
};

function hours(seconds) {
  return `${(Number(seconds ?? 0) / 3600).toFixed(1)} 小時`;
}

function metric(label, value, hint) {
  const card = element("div", "metric");
  card.append(element("p", "metric-label", label), element("p", "metric-value", value));
  if (hint) card.append(element("p", "metric-hint", hint));
  return card;
}

/** 以 SVG 折線呈現單一機台的使用率,不依賴外部圖表套件。 */
function sparkline(series) {
  const width = 140;
  const height = 32;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("class", "sparkline");
  svg.setAttribute("role", "img");

  const points = series.filter((point) => typeof point.u === "number");
  if (points.length < 2) {
    svg.setAttribute("aria-label", "尚無足夠的取樣資料");
    return svg;
  }

  const step = width / (points.length - 1);
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${(index * step).toFixed(1)},${(height - (point.u / 100) * height).toFixed(1)}`)
    .join(" ");
  const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
  line.setAttribute("d", path);
  svg.append(line);

  const peak = Math.max(...points.map((point) => point.u));
  svg.setAttribute("aria-label", `最近 ${points.length} 筆取樣,尖峰 ${Math.round(peak)}%`);
  return svg;
}

function usageBar(value) {
  const wrap = element("div", "bar");
  const fill = element("span", "bar-fill");
  fill.style.width = `${Math.max(0, Math.min(100, value ?? 0))}%`;
  wrap.append(fill);
  const box = element("div", "bar-box");
  box.append(wrap, element("span", "bar-text", value === null ? "—" : `${Math.round(value)}%`));
  return box;
}

function nodeRow(node) {
  const row = element("tr");
  const name = element("th", null, node.name);
  name.setAttribute("scope", "row");
  if (node.is_mine) name.append(element("span", "tag", "我的設備"));

  const memory = node.memory_used_mb === null
    ? "—"
    : `${Math.round(node.memory_used_mb / 1024 * 10) / 10} / ${Math.round(node.memory_mb / 1024)} GB`;
  const health = [
    node.temperature_c === null ? null : `${Math.round(node.temperature_c)}°C`,
    node.power_w === null ? null : `${Math.round(node.power_w)} W`,
  ].filter(Boolean).join(" / ") || "—";

  const state = element("td");
  state.append(element("span", `status status-${node.state}`, STATE_TEXT[node.state] ?? node.state));

  const usage = element("td");
  usage.append(usageBar(node.gpu_utilization));

  const chart = element("td");
  chart.append(sparkline(node.series ?? []));

  row.append(
    name,
    element("td", "cell-muted", node.gpu_name),
    state,
    usage,
    element("td", "cell-muted", memory),
    element("td", "cell-muted", health),
    element("td", "cell-muted",
            `${node.today.jobs_completed} 件 / ${hours(node.today.busy_seconds + node.today.rented_seconds)}`),
    chart,
  );
  return row;
}

function render(data) {
  const totals = data.totals;
  totalsBox.replaceChildren(
    metric("閒置可用設備", `${totals.nodes_idle} / ${totals.nodes_online}`,
           `閒置顯示記憶體合計 ${Math.round(totals.idle_vram_mb / 1024)} GB`),
    metric("執行中設備", String(totals.nodes_working), `已登錄 ${totals.nodes_total} 台`),
    metric("平均 GPU 使用率",
           totals.avg_utilization === null ? "—" : `${totals.avg_utilization}%`, "線上設備平均"),
    metric("佇列", `${totals.jobs_queued} 件`, `執行中 ${totals.jobs_running} 件`),
    metric("互動式租借", `${totals.rentals_open} 段`, "排隊與使用中合計"),
  );

  nodesBody.replaceChildren(...data.nodes.map(nodeRow));
  nodesEmpty.textContent = data.nodes.length ? "" : "尚未有任何設備完成配對。";

  daysBody.replaceChildren(...data.days.map((day) => {
    const row = element("tr");
    const date = element("th", null, day.day);
    date.setAttribute("scope", "row");
    row.append(
      date,
      element("td", "cell-muted", hours(day.busy_seconds)),
      element("td", "cell-muted", hours(day.rented_seconds)),
      element("td", "cell-muted", hours(day.idle_seconds)),
      element("td", "cell-muted", hours(day.gpu_seconds)),
      element("td", "cell-muted", `${day.jobs_completed ?? 0} 件`),
    );
    return row;
  }));
  daysEmpty.textContent = data.days.length ? "" : "尚未累積每日用量。排程器每 5 分鐘彙整一次。";

  document.getElementById("sample-seconds").textContent = data.settings.sample_seconds;
  document.getElementById("retention-days").textContent = data.settings.retention_days;
  document.getElementById("series-hours").textContent = data.settings.series_hours;
  updatedAt.textContent = `更新時間:${new Date(data.generated_at).toLocaleTimeString("zh-TW")}`;
}

async function tick() {
  try {
    render(await api("/api/usage/summary"));
  } catch (err) {
    if (err instanceof ApiError && err.code === "NOT_AUTHENTICATED") {
      window.location.assign("/login/");
      return;
    }
    console.error(err);
  }
  window.setTimeout(tick, POLL_INTERVAL);
}

tick();
