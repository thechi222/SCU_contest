import { element, pollState } from "./api.js";

const nodes = document.getElementById("display-nodes");
const queue = document.getElementById("display-queue");

function render(state) {
  nodes.replaceChildren();
  for (const node of state.nodes) {
    const card = element("div", "display-card");
    const usage = node.telemetry?.gpu_utilization;
    card.append(
      element("h2", null, node.name),
      element("p", "display-gpu", node.gpu_name),
      element("p", "display-usage", usage === undefined || usage === null ? "—" : `GPU ${Math.round(usage)}%`),
      element("p", node.sharing ? "status status-online" : "status status-offline",
              node.sharing ? "分享中" : "未分享"),
    );
    nodes.append(card);
  }

  const jobs = state.batches.flatMap((batch) => batch.jobs);
  const counts = jobs.reduce((totals, job) => ({ ...totals, [job.status]: (totals[job.status] ?? 0) + 1 }), {});
  queue.replaceChildren(element(
    "p", "display-queue-text",
    `排隊 ${counts.queued ?? 0} 件,執行中 ${(counts.running ?? 0) + (counts.loading ?? 0)} 件,已完成 ${counts.completed ?? 0} 件`,
  ));
}

pollState(render);
