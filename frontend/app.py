import streamlit as st

st.set_page_config(page_title="PowerShare", layout="wide")

st.title("PowerShare — 校園閒置算力租借平台")

st.header("機台列表")
# TODO: 串接 GET /api/machines,顯示規格/狀態/身分定價

st.header("預約")
# TODO: 選機台+時段送出 POST /api/bookings

st.header("即時使用率")
# TODO: 依 AgentHeartbeat 輪詢顯示 CPU/RAM/GPU 曲線

st.header("AI 助理")
# TODO: 呼叫 POST /api/ai/assist,顯示回覆與新建立的預約
