from rest_framework.views import APIView


class AIAssistView(APIView):
    def post(self, request):
        """POST /api/ai/assist(AIAssistRequestSerializer)→ AIAssistResponseSerializer"""
        raise NotImplementedError
