from rest_framework.views import APIView


class AIAssistView(APIView):
    def post(self, request):
        """POST /api/ai/assist(AIAssistRequestSerializer)→ AIAssistResponseSerializer

        以 core.ai_assistant.handle_ai_request() 處理,回傳自然語言回覆,
        以及(若有)新建立的批次或使用報告摘要。
        """
        raise NotImplementedError
