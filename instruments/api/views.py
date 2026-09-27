"""Instrument catalog and read-only price history API."""
from rest_framework import generics, permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from instruments.models import Instrument, PriceBar
from instruments.pagination import PriceBarCursorPagination
from instruments.serializers import InstrumentSerializer, PriceBarSerializer


class InstrumentViewSet(viewsets.ModelViewSet):
    """Expose the catalog to signed-in users; reserve catalog edits for staff."""

    queryset = Instrument.objects.all()
    serializer_class = InstrumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["symbol", "name", "exchange", "sector"]
    ordering_fields = ["symbol", "name", "exchange"]
    filterset_fields = ["exchange", "sector", "is_active"]

    def get_queryset(self):
        queryset = super().get_queryset()
        for field in ("exchange", "sector", "is_active"):
            value = self.request.query_params.get(field)
            if value is not None:
                queryset = queryset.filter(**{field: value})
        return queryset

    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionDenied("Only staff can create instruments.")
        serializer.save()

    def perform_update(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionDenied("Only staff can update instruments.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise PermissionDenied("Only staff can delete instruments.")
        instance.delete()


class PriceBarListView(generics.ListAPIView):
    """Return cursor-paginated historical bars for one instrument."""

    serializer_class = PriceBarSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PriceBarCursorPagination

    def get_queryset(self):
        return PriceBar.objects.filter(
            instrument_id=self.kwargs["instrument_id"], instrument__is_active=True
        ).order_by("-timestamp", "-id")
