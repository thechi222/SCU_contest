import { api, ApiError } from "./api.js";

// 6.3 #3 預約表單:POST /api/bookings,時段衝突時顯示 BOOKING_CONFLICT 訊息
async function handleBookingSubmit(event) {
  event.preventDefault();
  // TODO
}

// 6.3 #3 我的預約:GET /api/bookings,顯示各筆預約狀態
async function renderBookingList() {
  // TODO
}

// 6.3 #6 使用報告:GET /api/bookings/{id}/report,顯示 AI 生成的使用摘要
async function renderUsageReport(bookingId) {
  // TODO
}

document.getElementById("booking-form").addEventListener("submit", handleBookingSubmit);
renderBookingList();
