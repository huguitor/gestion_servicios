# gestion/web_publica/urls.py

from django.urls import path
from .views import HomeWebAPIView

urlpatterns = [
    path("home/", HomeWebAPIView.as_view(), name="web-home"),
]