# gestion/web_publica/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .services import WebPublicaService
from .serializers import HomeWebSerializer


class HomeWebAPIView(APIView):
    """Endpoint público para obtener la composición completa del home web."""
    permission_classes = [AllowAny]

    def get(self, request):
        data = WebPublicaService.get_home_data()

        serializer = HomeWebSerializer(
            data,
            context={"request": request}
        )

        return Response(serializer.data)
