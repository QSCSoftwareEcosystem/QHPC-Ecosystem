"""Routes for the Django Workbench and its constrained API proxy."""

from django.urls import path

from . import views


urlpatterns = [
    path("", views.index, name="workbench"),
    path("health", views.health, name="health"),
    path("api/v1/<path:api_path>", views.api_proxy, name="api-proxy"),
]
