from django.urls import path

from core.views import agent, ai, auth, bookings, machines

urlpatterns = [
    path("auth/login", auth.LoginView.as_view()),
    path("auth/logout", auth.LogoutView.as_view()),
    path("auth/me", auth.MeView.as_view()),
    path("machines", machines.MachineListView.as_view()),
    path("machines/<str:machine_id>/metrics", machines.MachineMetricsView.as_view()),
    path("bookings", bookings.BookingListCreateView.as_view()),
    path("bookings/<uuid:booking_id>", bookings.BookingDetailView.as_view()),
    path("bookings/<uuid:booking_id>/cancel", bookings.BookingCancelView.as_view()),
    path("bookings/<uuid:booking_id>/report", bookings.BookingReportView.as_view()),
    path("agent/heartbeat", agent.HeartbeatView.as_view()),
    path("ai/assist", ai.AIAssistView.as_view()),
]
