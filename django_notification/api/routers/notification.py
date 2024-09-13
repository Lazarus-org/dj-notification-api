from rest_framework import routers

from django_notification.api.views.notification import NotificationViewSet
from django_notification.api.views.activity import ActivityViewSet

router = routers.DefaultRouter()

router.register("notifications", NotificationViewSet, basename="notifications")
router.register("activities", ActivityViewSet, basename="activities")


urlpatterns = router.urls
