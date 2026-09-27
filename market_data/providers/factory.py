"""Provider selection based on runtime configuration."""
from django.conf import settings

from .alpha_vantage import AlphaVantageProvider
from .base import MarketDataProvider, MarketDataProviderError
from .yfinance import YFinanceProvider


def get_market_data_provider(name=None) -> MarketDataProvider:
    """Construct the selected provider without coupling consumers to vendors."""
    provider_name = (name or settings.MARKET_DATA_PROVIDER).strip().lower()
    providers = {"yfinance": YFinanceProvider, "alpha_vantage": AlphaVantageProvider}
    try:
        return providers[provider_name]()
    except KeyError as exc:
        raise MarketDataProviderError(
            f"Unknown market data provider '{provider_name}'. Choose from: {', '.join(providers)}."
        ) from exc
