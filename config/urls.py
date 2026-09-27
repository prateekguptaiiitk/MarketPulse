"""Top-level URL routing."""
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.api.views import LogoutView, RegisterView
from instruments.api.views import InstrumentViewSet, PriceBarListView
from indicators.api import InstrumentIndicatorsView
from watchlists.api.views import WatchlistItemViewSet, WatchlistViewSet
from strategies.api.views import StrategyViewSet
from backtesting.api.views import BacktestRunViewSet

router = DefaultRouter()
router.register("instruments", InstrumentViewSet, basename="instrument")
router.register("watchlists", WatchlistViewSet, basename="watchlist")
router.register("strategies", StrategyViewSet, basename="strategy")
router.register("backtests", BacktestRunViewSet, basename="backtest")
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/<str:version>/auth/register/", RegisterView.as_view(), name="register"),
    path("api/<str:version>/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/<str:version>/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/<str:version>/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/<str:version>/", include(router.urls)),
    path("api/<str:version>/instruments/<int:instrument_id>/prices/", PriceBarListView.as_view(), name="pricebar-list"),
    path("api/<str:version>/instruments/<int:instrument_id>/indicators/", InstrumentIndicatorsView.as_view(), name="instrument-indicators"),
    path("api/<str:version>/watchlists/<int:watchlist_pk>/items/", WatchlistItemViewSet.as_view({"get": "list", "post": "create"}), name="watchlist-item-list"),
    path("api/<str:version>/watchlists/<int:watchlist_pk>/items/<int:pk>/", WatchlistItemViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="watchlist-item-detail"),
]
