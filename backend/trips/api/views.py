from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import TripPlanSerializer
from trips.services.trip_planner import plan_trip as build_trip_plan
from trips.services.providers import ProviderError


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def plan_trip(request):
    serializer = TripPlanSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        result = build_trip_plan(data)
    except ProviderError as exc:
        return Response(exc.payload, status=exc.status)
    return Response(result)
