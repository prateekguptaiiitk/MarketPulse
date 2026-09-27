"""Factory Boy fixtures for watchlist tests."""
import factory

from accounts.factories import UserFactory
from instruments.factories import InstrumentFactory
from watchlists.models import Watchlist, WatchlistItem


class WatchlistFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda number: f"Watchlist {number}")

    class Meta:
        model = Watchlist


class WatchlistItemFactory(factory.django.DjangoModelFactory):
    watchlist = factory.SubFactory(WatchlistFactory)
    instrument = factory.SubFactory(InstrumentFactory)

    class Meta:
        model = WatchlistItem
