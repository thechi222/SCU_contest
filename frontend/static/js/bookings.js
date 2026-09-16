import { api, ApiError } from "./api.js";

// 6.3 #5 開放時段:GET /api/machines/{id}/availability,於選擇機台後顯示可預約時段
async function renderAvailability(machineId) {
  // TODO
}

// 6.3 #5 預約表單:POST /api/bookings;BOOKING_CONFLICT、OUTSIDE_AVAILABILITY、
// MACHINE_UNAVAILABLE 等錯誤於 #booking-error 顯示
async function handleBookingSubmit(event) {
  event.preventDefault();
  // TODO
}

// 6.3 #6 我的預約:GET /api/bookings,顯示狀態、連線網址、剩餘時間,結束前 10 分鐘提醒
async function renderBookingList() {
  // TODO
}

// 6.3 #8 使用報告:GET /api/bookings/{id}/report,顯示 AI 生成的使用摘要
async function renderUsageReport(bookingId) {
  // TODO
}

document.getElementById("booking-form").addEventListener("submit", handleBookingSubmit);
renderBookingList();
