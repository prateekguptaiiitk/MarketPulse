"""Validated JSON serializers for strategy definitions."""
from rest_framework import serializers

from .engine import SUPPORTED_CONDITIONS, SUPPORTED_INDICATORS
from .models import Strategy


class StrategyRuleSerializer(serializers.Serializer):
    indicator = serializers.CharField(max_length=32)
    condition = serializers.ChoiceField(choices=sorted(SUPPORTED_CONDITIONS))
    value = serializers.JSONField(required=False)

    def validate(self, attrs):
        attrs["indicator"] = attrs["indicator"].upper()
        if attrs["indicator"] not in SUPPORTED_INDICATORS:
            raise serializers.ValidationError({"indicator": "Unsupported indicator."})
        condition = attrs["condition"]
        has_value = "value" in attrs
        if condition in ("is_true", "is_false"):
            if has_value:
                raise serializers.ValidationError({"value": "Do not provide value for boolean conditions."})
        elif not has_value:
            raise serializers.ValidationError({"value": "This field is required for comparison conditions."})
        elif isinstance(attrs["value"], bool) or not isinstance(attrs["value"], (int, float)):
            raise serializers.ValidationError({"value": "A numeric value is required for comparison conditions."})
        return attrs


class StrategySerializer(serializers.ModelSerializer):
    rules = StrategyRuleSerializer(many=True, required=False)
    exit_rules = StrategyRuleSerializer(many=True, required=False)

    class Meta:
        model = Strategy
        fields = ("id", "name", "rules", "logic", "exit_rules", "exit_logic", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_logic(self, value):
        return value.upper()

    def validate_exit_logic(self, value):
        return value.upper()
