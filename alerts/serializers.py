"""Validated alert configuration and read-only trigger history serializers."""
from rest_framework import serializers

from alerts.models import Alert, AlertTriggerLog
from alerts.notifications import _validate_webhook_url
from instruments.models import Instrument
from strategies.models import Strategy
from strategies.serializers import StrategyRuleSerializer


class AlertConditionSerializer(serializers.Serializer):
    rules = StrategyRuleSerializer(many=True, required=False)
    logic = serializers.ChoiceField(choices=Strategy.Logic.choices, default=Strategy.Logic.AND)

    def to_representation(self, instance):
        if not instance:
            instance = {"rules": [], "logic": "AND"}
        return super().to_representation(instance)


class AlertSerializer(serializers.ModelSerializer):
    instrument = serializers.PrimaryKeyRelatedField(queryset=Instrument.objects.filter(is_active=True))
    strategy = serializers.PrimaryKeyRelatedField(queryset=Strategy.objects.none(), required=False, allow_null=True)
    condition = AlertConditionSerializer(required=False)

    class Meta:
        model = Alert
        fields = (
            "id", "name", "instrument", "strategy", "condition", "interval", "is_active",
            "notification_channel", "webhook_url", "cooldown_minutes", "last_triggered_at", "created_at", "updated_at",
        )
        read_only_fields = ("id", "last_triggered_at", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        self.fields["strategy"].queryset = Strategy.objects.filter(user=user) if user and user.is_authenticated else Strategy.objects.none()

    def validate(self, attrs):
        strategy = attrs.get("strategy", getattr(self.instance, "strategy", None))
        condition = attrs.get("condition", getattr(self.instance, "condition", {})) or {}
        if strategy is None and not condition.get("rules"):
            raise serializers.ValidationError({"condition": "Provide at least one rule or select a strategy."})
        if attrs.get("notification_channel", getattr(self.instance, "notification_channel", Alert.NotificationChannel.EMAIL)) == Alert.NotificationChannel.WEBHOOK:
            url = attrs.get("webhook_url", getattr(self.instance, "webhook_url", ""))
            if not url:
                raise serializers.ValidationError({"webhook_url": "A webhook URL is required for webhook notifications."})
            try:
                _validate_webhook_url(url)
            except ValueError as exc:
                raise serializers.ValidationError({"webhook_url": str(exc)}) from exc
        cooldown = attrs.get("cooldown_minutes", getattr(self.instance, "cooldown_minutes", 5))
        if not 1 <= cooldown <= 1440:
            raise serializers.ValidationError({"cooldown_minutes": "Cooldown must be between 1 and 1440 minutes."})
        return attrs


class AlertTriggerLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertTriggerLog
        fields = ("id", "triggered_at", "price", "condition_results", "delivery_status", "delivery_error")
        read_only_fields = fields
