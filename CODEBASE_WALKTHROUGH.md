# MarketPulse Codebase Walkthrough

Think of MarketPulse as a Django backend with several feature apps. Each app owns a part of the domain: users, instruments, watchlists, strategies, alerts, and backtests. Django and DRF expose that functionality as a versioned API. Celery handles work that runs in the background, and Channels serves WebSocket connections.

## Table of Contents

* [1. Start at the Project Package](#1-start-at-the-project-package)
* [2. How an API Request Moves Through the Code](#2-how-an-api-request-moves-through-the-code)
* [3. Feature Apps and Their Responsibilities](#3-feature-apps-and-their-responsibilities)

  * [Accounts](#accounts)
  * [Instruments and Price Bars](#instruments-and-price-bars)
  * [Market Data Providers](#market-data-providers)
  * [Watchlists](#watchlists)
  * [Indicators](#indicators)
  * [Strategies](#strategies)
  * [Backtesting](#backtesting)
  * [Alerts](#alerts)
  * [Realtime](#realtime)
* [4. Running Pieces of the System](#4-running-pieces-of-the-system)
* [5. Settings, Docs, and Tests](#5-settings-docs-and-tests)

---

## 1. Start at the Project Package

The `config` directory is the Django project package: the site-wide wiring and runtime entry points live there.

* `MarketPulse/config/urls.py` maps HTTP routes to admin, API views, Swagger, and the WebSocket test page.
* `MarketPulse/config/settings` contains shared, development, production, and test settings. The settings module is selected with `DJANGO_SETTINGS_MODULE`.
* `MarketPulse/config/asgi.py` routes HTTP requests to Django and WebSocket connections through Channels.
* `MarketPulse/config/wsgi.py` is the WSGI entry point.
* `MarketPulse/config/celery.py` configures Celery and discovers tasks across apps.
* `MarketPulse/config/exceptions.py` formats DRF errors into the project’s common JSON error shape.
* `MarketPulse/config/pagination.py` defines the shared API pagination behavior.

Django doesn’t require the project package to have the same name as the repository. Here, `config` serves that role; feature code lives in the apps.

## 2. How an API Request Moves Through the Code

For an ordinary API request, the route in `config/urls.py` selects a view. The view checks permissions and scopes the data, the serializer validates input or shapes output, and the model layer reads or writes PostgreSQL.

```text
HTTP request
    → config/urls.py
    → DRF view or viewset
    → permission checks + serializer validation
    → model/database
    → serialized HTTP response
```

Most endpoints are under `/api/v1/`. DRF’s router registers the standard CRUD routes for instruments, watchlists, strategies, backtests, and alerts. Some endpoints—price history, indicators, auth, and watchlist items—are wired explicitly in the URL configuration.

## 3. Feature Apps and Their Responsibilities

### Accounts

`MarketPulse/accounts/models.py` defines the custom `User`. Users log in with a unique email instead of a username. The custom manager handles email normalization and superuser creation.

`MarketPulse/accounts/serializers.py` and `MarketPulse/accounts/api/views.py` handle registration and logout. SimpleJWT supplies the login and refresh endpoints. Logout blacklists the refresh token.

### Instruments and Price Bars

`MarketPulse/instruments/models.py` contains:

* `Instrument`: a listed symbol and related metadata.
* `PriceBar`: OHLCV data for an instrument at a timestamp and interval.

Price bars have a uniqueness constraint on instrument, timestamp, and interval, plus indexes to support time-series queries. `MarketPulse/instruments/api/views.py` exposes the instrument catalogue and historical bars. Instrument edits are restricted to staff; price history uses cursor pagination.

Management commands under `instruments/management/commands/` seed instruments and deterministic demo bars. Demo seeding doesn’t require a live data provider.

### Market Data Providers

The `market_data/providers` package isolates external vendors from the rest of the application:

* `MarketPulse/market_data/providers/base.py` defines the provider contract and normalized OHLCV type.
* `yfinance.py` and `alpha_vantage.py` implement that contract.
* `factory.py` picks the provider using `MARKET_DATA_PROVIDER`.

The backfill command and polling task use this interface. That way, business logic consumes normalized bars instead of knowing vendor-specific response formats.

### Watchlists

`MarketPulse/watchlists/models.py` models a user-owned watchlist and its instrument membership. Database constraints prevent duplicate watchlist names per user and duplicate instruments in one list.

`MarketPulse/watchlists/api/views.py` scopes queries to the logged-in user. That scoping is important: permissions are enforced when fetching records, not just by hiding fields in a response.

### Indicators

`MarketPulse/indicators/services.py` computes SMA, EMA, RSI, MACD, Bollinger Bands, and volume-spike series from pandas data. It keeps warm-up timestamps in the output and represents values that can’t yet be computed as `null`.

`MarketPulse/indicators/cache.py` caches calculated output. The API endpoint is in `indicators/api.py`. This is a calculation service rather than a database model: indicators are derived from price bars.

### Strategies

`MarketPulse/strategies/models.py` stores a user-owned strategy and its JSON entry and exit rules. Each rule refers to an indicator, a comparison, and optionally a value.

`MarketPulse/strategies/engine.py` is the pure evaluation layer. Given rules and an indicator snapshot, it returns whether the rules matched and the result of each condition. `AND` requires every condition to match; `OR` requires at least one.

### Backtesting

`MarketPulse/backtesting/models.py` stores each requested run, its status, and its results. The API creates a run and enqueues a Celery task; the response is accepted while the task is pending.

`MarketPulse/backtesting/engine.py` simulates a long-only strategy over stored bars and calculates metrics. `MarketPulse/backtesting/tasks.py` updates the run’s status and persists either results or an error. The API only shows a user their own runs.

The worker must be running for a submitted backtest to execute. The API stores results on `BacktestRun`, so clients can poll the run endpoint for completion.

### Alerts

`MarketPulse/alerts/models.py` stores alert definitions and a durable trigger history. An alert can use a strategy or its own rule set.

`MarketPulse/alerts/services.py` loads recent bars, builds an indicator snapshot, evaluates the rules, applies the cooldown, records a trigger, and dispatches the notification. `alerts/notifications.py` sends email or a webhook. `MarketPulse/alerts/tasks.py` evaluates active alerts on the Celery Beat schedule.

### Realtime

`MarketPulse/realtime/consumers.py` contains the WebSocket consumers for instrument and watchlist feeds. `MarketPulse/realtime/middleware.py` authenticates WebSocket connections with a JWT. The watchlist consumer checks that the connecting user owns the list.

`MarketPulse/realtime/tasks.py` polls active instruments through the provider interface. When it sees a newer bar, it saves it and publishes an event to the Channels layer in Redis. Connected clients receive that event.

```text
Celery Beat
    → poll_latest_prices task
    → MarketDataProvider
    → save newer PriceBar
    → Redis Channels group
    → WebSocket clients
```

This is simulated live data from periodic provider polling, not a direct exchange feed. `/realtime/test/` is a basic developer page for checking the WebSocket connection.

## 4. Running Pieces of the System

`MarketPulse/docker-compose.yml` runs the web service, PostgreSQL, Redis, Celery worker, and Celery Beat. The web service uses Daphne, which supports both HTTP and WebSockets.

* **PostgreSQL** stores users, instruments, bars, strategies, alerts, and backtest runs.
* **Redis** is used by the cache, Celery broker, and Channels layer.
* **Celery worker** runs queued tasks such as backtests.
* **Celery Beat** periodically queues alert evaluation and price polling.
* **Daphne** serves the Django ASGI application.

The `seed_demo_data` command creates sample instruments and deterministic bars so you can explore APIs without fetching external market data.

## 5. Settings, Docs, and Tests

* `MarketPulse/.env.example` documents the environment variables; `.env` provides local values.
* `config.settings.dev`, `.prod`, and `.test` adjust settings for each environment.
* `config/settings/prod.py` adds production security requirements.
* drf-spectacular serves the schema at `/api/schema/` and Swagger UI at `/api/schema/swagger-ui/`.
* Each app’s `tests.py` covers its behavior. Factories in the `factories.py` files create reusable test objects. Market provider tests mock the provider boundary so the test suite doesn’t call external services.
* `.github/workflows/ci.yml` runs linting and checks/tests in CI.

A typical feature change usually touches a few layers: its **model** if persisted data changes, a **serializer** if API input/output changes, a **view** if request behavior or access rules change, and **tests** for the affected behavior. Keep calculations and domain rules in service or engine modules where possible, instead of putting them directly into views.
