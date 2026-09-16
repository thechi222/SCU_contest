from rest_framework.views import APIView


class BookingListCreateView(APIView):
    def get(self, request):
        """GET /api/bookings → BookingSerializer[](僅目前使用者)"""
        raise NotImplementedError

    def post(self, request):
        """POST /api/bookings(BookingCreateSerializer)→ BookingSerializer"""
        raise NotImplementedError


class BookingDetailView(APIView):
    def get(self, request, booking_id):
        """GET /api/bookings/{id} → BookingSerializer"""
        raise NotImplementedError


class BookingCancelView(APIView):
    def post(self, request, booking_id):
        """POST /api/bookings/{id}/cancel → BookingSerializer"""
        raise NotImplementedError


class BookingReportView(APIView):
    def get(self, request, booking_id):
        """GET /api/bookings/{id}/report → UsageReportSerializer"""
        raise NotImplementedError
