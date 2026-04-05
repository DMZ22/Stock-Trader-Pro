"""Root URL configuration."""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.dashboard.urls")),
    path("api/", include("apps.dashboard.api_urls")),
    path("auth/", include("apps.auth.urls")),
]
