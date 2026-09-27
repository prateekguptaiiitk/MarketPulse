# MarketPulse

MarketPulse is a Django REST Framework service for stock market data, technical indicators, watchlists, strategy evaluation, asynchronous backtests, alerts, and live price updates. It targets Python 3.11+, Django 5.x, PostgreSQL, and Redis.

## Architecture

```text
                    ┌───────────────────────┐
REST clients ──────▶│ Django + DRF (v1 API) │──────▶ PostgreSQL
WebSocket clients ─▶│ Daphne + Channels    │          │
                    └───────────┬───────────┘          ├─ instruments / OHLCV
                                │                      ├─ accounts / watchlists
                                ▼                      ├─ strategies / backtests
                         Redis cache +                 └─ alerts / trigger history
                         Channels layer
                                ▲
                  ┌─────────────┴─────────────┐
                  │ Celery worker + Beat      │
                  ├─ poll provider every 60s  │
                  ├─ evaluate alerts every 2m │
                  └─ execute backtests        │
                  └─────────────┬─────────────┘
                                ▼
                    MarketDataProvider interface
                     ├─ yfinance (default)
                     └─ Alpha Vantage (optional)
```

PostgreSQL uses ordinary B-tree indexes on `(instrument, timestamp)` and `(instrument, interval, timestamp)`; the schema can be moved to TimescaleDB later without changing the provider or API contracts. WebSocket access uses short-lived JWT access tokens, and watchlist feeds are restricted to their owner.

## Quick start with Docker

1. Copy `.env.example` to `.env` and set a unique `SECRET_KEY`.
2. Run `docker compose up --build` from this directory.
3. In another terminal, seed local sample data:

   ```sh
   docker compose exec web python manage.py seed_demo_data
   ```

The demo command creates 12 NSE and US instruments plus deterministic daily bars for the most recent 10 calendar days. It does not contact a market data API. The app listens at `http://localhost:8000`; Swagger UI is at `http://localhost:8000/api/schema/swagger-ui/`.

To create an administrator, run `docker compose exec web python manage.py createsuperuser`.

## Local development

Use Python 3.11 or newer. Create and activate a virtual environment, then run:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For a production deployment, select `config.settings.prod`, provide a random `SECRET_KEY` with at least 50 characters, configure `ALLOWED_HOSTS`, and terminate TLS at a trusted reverse proxy.

Start PostgreSQL and Redis, then:

```sh
python manage.py migrate
python manage.py seed_demo_data --days 10
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

Run background processes in separate terminals:

```sh
celery -A config worker -l INFO
celery -A config beat -l INFO
```

Tests use `config.settings.test` (local memory cache and an in-memory Channels layer). PostgreSQL remains the persistence backend:

```sh
python manage.py test --settings=config.settings.test
# or
pytest
```

## API examples

All application endpoints are under `/api/v1/`. Register and log in to get a JWT pair:

```sh
curl -X POST http://localhost:8000/api/v1/auth/register/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"trader@example.com","password":"Replace-this-Password-934!"}'

curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"trader@example.com","password":"Replace-this-Password-934!"}'
```

Pass the returned access token as `Authorization: Bearer <access-token>` for authenticated requests:

```sh
curl 'http://localhost:8000/api/v1/instruments/?search=Reliance' \
  -H 'Authorization: Bearer <access-token>'

curl 'http://localhost:8000/api/v1/instruments/1/prices/?page_size=50' \
  -H 'Authorization: Bearer <access-token>'

curl 'http://localhost:8000/api/v1/instruments/1/indicators/?indicators=RSI,SMA&lookback=100&period=14' \
  -H 'Authorization: Bearer <access-token>'

curl -X POST http://localhost:8000/api/v1/strategies/ \
  -H 'Authorization: Bearer <access-token>' -H 'Content-Type: application/json' \
  -d '{"name":"Oversold","logic":"AND","rules":[{"indicator":"RSI","condition":"less_than","value":30}],"exit_logic":"OR","exit_rules":[{"indicator":"RSI","condition":"greater_than","value":60}]}'

curl -X POST http://localhost:8000/api/v1/backtests/ \
  -H 'Authorization: Bearer <access-token>' -H 'Content-Type: application/json' \
  -d '{"strategy":1,"instrument":1,"start_date":"2026-09-01","end_date":"2026-09-27","interval":"1d","initial_capital":"10000.00"}'

curl http://localhost:8000/api/v1/backtests/1/ \
  -H 'Authorization: Bearer <access-token>'
```

Other endpoints include `/api/v1/watchlists/`, `/api/v1/watchlists/{id}/items/`, `/api/v1/alerts/`, and `/api/v1/alerts/{id}/history/`. API errors use a stable shape such as `{"error":{"status":400,"message":"Request validation failed.","details":{"field":["... "]}}}`. Collection endpoints use page-number pagination; price history uses cursor pagination.

### Market data ingestion

Seed only the instrument directory with `python manage.py seed_instruments`. To backfill actual provider history after configuring a provider:

```sh
python manage.py backfill_history --symbols RELIANCE.NS TCS.NS --start 2025-01-01 --end 2025-03-31 --interval 1d
```

The end date is inclusive. Set `MARKET_DATA_PROVIDER=alpha_vantage` and `ALPHA_VANTAGE_API_KEY` to select Alpha Vantage. Tests mock this boundary and never access live providers.

### WebSockets

The manual client is at `/realtime/test/`. Instrument feeds use `ws://localhost:8000/ws/prices/{instrument_id}/`; watchlist feeds use `/ws/watchlists/{watchlist_id}/`. Browser clients can pass a short-lived JWT as the `token` query parameter. For non-browser clients, send `Authorization: Bearer <access-token>` in the WebSocket handshake. Use `wss://` outside local development.

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_SETTINGS_MODULE` | Settings module (`config.settings.dev`, `.prod`, or `.test`) | `config.settings.dev` |
| `SECRET_KEY` | Django signing key; replace before deployment | unsafe development value |
| `DEBUG` | Django debug mode | `false` in base, enabled in dev |
| `ALLOWED_HOSTS` | Comma-separated allowed HTTP/WebSocket hosts | `localhost,127.0.0.1` |
| `DATABASE_URL` | PostgreSQL connection URL | Compose PostgreSQL service |
| `REDIS_URL` | Redis cache, Channels, and Celery broker URL | Compose Redis service |
| `MARKET_DATA_PROVIDER` | `yfinance` or `alpha_vantage` | `yfinance` |
| `ALPHA_VANTAGE_API_KEY` | API key required for Alpha Vantage | empty |
| `MARKET_DATA_TIMEOUT` | Provider HTTP timeout in seconds | `20` |
| `MARKET_DATA_POLL_INTERVAL` | Provider bar interval for simulated live updates | `1m` |
| `MARKET_DATA_POLL_SECONDS` | Celery Beat polling period in seconds | `60` |
| `INDICATOR_CACHE_TTL` | Indicator cache lifetime in seconds | `60` |
| `WEBHOOK_TIMEOUT` | Alert webhook HTTP timeout in seconds | `10` |
| `EMAIL_BACKEND` | Django email backend | Console backend |
| `DEFAULT_FROM_EMAIL` | Sender address for alert email | `marketpulse@localhost` |
| `EMAIL_HOST`, `EMAIL_PORT` | SMTP server and port when using an SMTP backend | `localhost`, `25` |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP credentials | empty |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | SMTP transport security options | both `false` |
| `SENTRY_DSN` | Optional Sentry DSN; empty disables Sentry | empty |
| `LOG_LEVEL` | Structured application log threshold | `INFO` |

## API schema

The OpenAPI schema is served at `/api/schema/` and interactive Swagger UI at `/api/schema/swagger-ui/`. The project also includes `.github/workflows/ci.yml`, which installs dependencies, checks Ruff, applies migrations, runs Django checks, and executes the test suite against PostgreSQL.
