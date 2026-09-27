"""Input and output serializers for asynchronous backtest runs."""
from decimal import Decimal

from rest_framework import serializers

from instruments.models import Instrument
from strategies.models import Strategy
from .models import BacktestRun


class BacktestCreateSerializer(serializers.ModelSerializer):
    strategy = serializers.PrimaryKeyRelatedField(queryset=Strategy.objects.none())
    instrument = serializers.PrimaryKeyRelatedField(queryset=Instrument.objects.filter(is_active=True))
    start_date = serializers.DateField(write_only=True)
    end_date = serializers.DateField(write_only=True)

    class Meta:
        model = BacktestRun
        fields = ("id", "strategy", "instrument", "start_date", "end_date", "interval", "initial_capital")
        read_only_fields = ("id",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        self.fields["strategy"].queryset = (
            Strategy.objects.filter(user=user, is_active=True) if user and user.is_authenticated else Strategy.objects.none()
        )

    def validate_initial_capital(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("Initial capital must be greater than zero.")
        return value

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "End date must be on or after start date."})
        strategy = attrs["strategy"]
        if not strategy.rules:
            raise serializers.ValidationError({"strategy": "The strategy must define at least one entry rule."})
        return attrs

    def create(self, validated_data):
        start_date = validated_data.pop("start_date")
        end_date = validated_data.pop("end_date")
        return BacktestRun.objects.create(
            requested_by=self.context["request"].user,
            date_range={"start": start_date.isoformat(), "end": end_date.isoformat()},
            status=BacktestRun.Status.PENDING,
            **validated_data,
        )


class BacktestRunSerializer(serializers.ModelSerializer):
    strategy_name = serializers.CharField(source="strategy.name", read_only=True)
    instrument_symbol = serializers.CharField(source="instrument.symbol", read_only=True)

    class Meta:
        model = BacktestRun
        fields = (
            "id", "strategy", "strategy_name", "instrument", "instrument_symbol", "date_range",
            "interval", "initial_capital", "status", "task_id", "results", "created_at", "started_at", "completed_at",
        )
        read_only_fields = fields
