from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("notification/", include("django_notification.api.routers.notification")),
]