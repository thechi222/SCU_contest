import streamlit as st

st.set_page_config(page_title="PowerShare", layout="wide")

st.title("PowerShare — 校園閒置算力租借平台")

# 對應 README §6.3 的六項工作,各段落由前端負責人依序實作。

st.sidebar.header("身分")
# TODO 6.3 #2 身分切換(student / staff / external),價格隨身分變動

st.header("機台列表")
# TODO 6.3 #1 GET /api/machines,顯示規格、狀態與當前身分價格

st.header("預約")
# TODO 6.3 #3 選擇機台與時段後 POST /api/bookings,顯示 booking 狀態

st.header("即時使用率")
# TODO 6.3 #4 依心跳資料顯示 CPU/RAM/GPU 曲線,以 st.rerun() 每 5 秒輪詢

st.header("AI 助理")
# TODO 6.3 #5 POST /api/ai/assist,顯示回覆與新建立的預約

st.header("使用報告")
# TODO 6.3 #6 GET /api/bookings/{id}/report,顯示 AI 生成的使用摘要
