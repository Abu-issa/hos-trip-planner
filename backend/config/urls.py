from django.urls import include, path
from trips.api.views import health

urlpatterns = [
    path("api/health/", health),
    path("api/trips/", include("trips.api.urls")),
]
