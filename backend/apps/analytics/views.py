from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services


class SummaryView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        days = max(1, min(int(request.query_params.get("days", 30) or 30), 365))
        return Response(services.summary(request.user, days))
