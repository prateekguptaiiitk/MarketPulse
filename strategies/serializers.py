"""Validated JSON serializers for strategy definitions."""
from rest_framework import serializers

from .engine import SUPPORTED_CONDITIONS, SUPPORTED_INDICATORS
from .models import Strategy

'''
    `StrategyRuleSerializer` validates **one condition**, such as “RSI is less than 30.”
    
    `StrategyRuleSerializer` requires an `indicator` and a `condition`. It uppercases the indicator, so `rsi` becomes
    `RSI`, then checks that it’s supported by the strategy engine. It also restricts `condition` to supported
    comparisons, such as `less_than`, `equals`, or `is_true`.

    For comparison conditions, `value` is required and must be numeric. For boolean conditions (`is_true` or `is_false`),
    `value` must be omitted. This prevents requests like `{"indicator":"RSI","condition":"less_than"}` or 
    `{"indicator":"RSI","condition":"is_true","value":30}` from being accepted.
'''
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

'''
    `StrategySerializer` validates a **whole strategy** and its fields, including a list of entry rules and a list of
     exit rules
     
    `StrategySerializer` uses `StrategyRuleSerializer(many=True)` for both `rules` and `exit_rules`, so DRF validates
     every condition in each list. The fields `logic` and `exit_logic` tell the evaluator how to combine each list:
    `AND` means every rule must match; `OR` means any one can match.

    The serializer is a `ModelSerializer`, so once validation passes, DRF creates or updates the `Strategy` model. 
    The view adds `user=self.request.user` on creation, keeping ownership tied to the authenticated user rather than
    trusting a user ID from the request body. The ID and timestamps are read-only.

    The handoff to evaluation happens later: MarketPulse/strategies/engine.py reads the saved rules and compares them
    against indicator values. The serializer checks that a rule is well-formed; it doesn’t evaluate whether the market
    currently meets that rule.
'''
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
