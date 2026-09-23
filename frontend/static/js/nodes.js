import { api, element, pollState } from "./api.js";

const codeButton = document.getElementById("pairing-code-button");
const codeOutput = document.getElementById("pairing-code");
const list = document.getElementById("node-list");

codeButton.addEventListener("click", async () => {
  const result = await api("/api/pairing-codes", { method: "POST" });
  const expires = new Date(result.expires_at).toLocaleTimeString("zh-TW");
  codeOutput.textContent = `配對碼:${result.code}(${expires} 前有效,只顯示這一次)`;
});

async function patchNode(nodeId, body) {
  await api(`/api/nodes/${nodeId}`, { method: "PATCH", body });
}

function nodeRow(node) {
  const row = element("div", "node-row");
  const online = node.last_seen && Date.now() - new Date(node.last_seen).getTime() < 30000;
  row.append(
    element("span", "node-name", node.name),
    element("span", "node-gpu", node.gpu_name),
    element("span", "node-kinds", node.kinds.join(" / ") || "尚未回報能力"),
    element("span", online ? "status status-online" : "status status-offline", online ? "在線" : "離線"),
  );

  if (node.telemetry?.gpu_utilization !== undefined && node.telemetry.gpu_utilization !== null) {
    row.append(element("span", "node-usage", `GPU ${Math.round(node.telemetry.gpu_utilization)}%`));
  }

  if (!node.is_mine) {
    row.append(element("span", "node-owner", `提供者:${node.owner_name}`));
    return row;
  }

  const toggle = element("button", "link-button", node.sharing ? "關閉分享" : "開啟分享");
  toggle.addEventListener("click", () => patchNode(node.id, { sharing: !node.sharing }));

  const rental = element("button", "link-button", node.allow_rental ? "停止接受租借" : "接受租借");
  rental.title = "互動式租借期間,租借者可自行進入容器操作";
  rental.addEventListener("click", () => patchNode(node.id, { allow_rental: !node.allow_rental }));

  row.append(toggle, rental,
             element("span", "node-local", node.local_enabled ? "機台已允許接單" : "機台尚未 enable"));
  return row;
}

function render(state) {
  list.replaceChildren();
  for (const node of state.nodes) {
    list.append(nodeRow(node));
  }
  if (!state.nodes.length) {
    list.append(element("p", "empty", "尚未有任何設備完成配對。"));
  }
}

pollState(render);
