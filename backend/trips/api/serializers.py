import math

from rest_framework import serializers


class LocationField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class CycleHoursField(serializers.FloatField):
    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            self.fail("invalid")
        value = super().to_internal_value(data)
        if not math.isfinite(value):
            raise serializers.ValidationError("Enter a finite number.")
        return value


class TripPlanSerializer(serializers.Serializer):
    current_location = LocationField(max_length=255, trim_whitespace=True)
    pickup_location = LocationField(max_length=255, trim_whitespace=True)
    dropoff_location = LocationField(max_length=255, trim_whitespace=True)
    current_cycle_used = CycleHoursField(min_value=0, max_value=70)

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({
                    key: ["Unknown field."] for key in sorted(unknown)
                })
        return super().to_internal_value(data)
