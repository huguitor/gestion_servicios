# gestion/remitos/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RemitoViewSet, ItemRemitoViewSet

router = DefaultRouter()
router.register(r'', RemitoViewSet, basename='remito')
router.register(r'items', ItemRemitoViewSet, basename='itemremito')

urlpatterns = [
    path('', include(router.urls)),
]