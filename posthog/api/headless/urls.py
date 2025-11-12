"""
URL Configuration for Headless API

These endpoints are designed for programmatic/headless access to PostHog data.
"""

from rest_framework import routers

from .views import HeadlessQueryViewSet, HeadlessDataViewSet

router = routers.DefaultRouter()
router.register(r"query", HeadlessQueryViewSet, basename="headless_query")
router.register(r"data", HeadlessDataViewSet, basename="headless_data")

urlpatterns = router.urls
