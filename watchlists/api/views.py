"""User-scoped watchlist and item endpoints."""
from rest_framework import permissions, viewsets
from rest_framework.exceptions import NotFound

from watchlists.models import Watchlist, WatchlistItem
from watchlists.serializers import WatchlistItemSerializer, WatchlistSerializer


class WatchlistViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return Watchlist.objects.none()
        return Watchlist.objects.filter(user=user).prefetch_related("items__instrument")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WatchlistItemViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_watchlist(self) -> Watchlist:
        try:
            return Watchlist.objects.get(pk=self.kwargs["watchlist_pk"], user=self.request.user)
        except Watchlist.DoesNotExist as exc:
            raise NotFound("Watchlist not found.") from exc

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return WatchlistItem.objects.none()
        return WatchlistItem.objects.filter(watchlist=self.get_watchlist()).select_related("instrument")

    def perform_create(self, serializer):
        serializer.save(watchlist=self.get_watchlist())
