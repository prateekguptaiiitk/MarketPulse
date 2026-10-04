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

    '''
        perform_create: this method acts as a dedicated bridge that runs right after data validation passes,
        but right before the object is saved to the database. 
        By default, the create() method in a ViewSet handles the entire HTTP request lifecycle: parsing incoming data,
        validating it via a serializer, calling perform_create(), and returning a 201 Created response.
        Instead of overriding the entire create() method—which forces you to manually manage the HTTP responses—you 
        override perform_create() to safely modify how an object is saved or trigger background actions.
    '''
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
