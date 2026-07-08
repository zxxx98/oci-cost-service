# OCI Current Month Cost Service Design

## Goal

Build a Docker-deployed HTTP service that runs on an Oracle Cloud Infrastructure
Compute instance and returns the current month's accumulated OCI cost. The
service is intended for public access, with every cost endpoint protected by an
API key.

## Scope

The service reports usage cost for the current UTC month. It does not report
formal invoices, payment status, invoice numbers, or second-by-second billing
state.

The first version provides:

- A public HTTP API.
- API key authentication for all cost endpoints.
- OCI Instance Principal authentication for production.
- Current-month total cost.
- Current-month breakdown by service.
- Current-month breakdown by resource.
- Current-month daily cost trend.
- Short-lived response caching to reduce OCI Usage API calls.

## Architecture

The application is a Python FastAPI service packaged as a Docker image. It runs
inside Docker on an OCI Compute instance. In production it authenticates to OCI
with Instance Principal credentials, so the container does not need OCI user API
keys or private key files.

The service queries OCI Usage API through the OCI Python SDK. Request handlers
delegate billing queries to a small billing service module, which is responsible
for calculating the current month time range, calling OCI, normalizing returned
items, aggregating totals, and applying an in-memory TTL cache.

Public access is protected at the application layer with an `X-API-Key` header.
The service can be exposed directly on a public port for the initial version.
For safer production use, the same container can sit behind Caddy, Nginx, or a
load balancer that terminates HTTPS.

## Runtime Configuration

Configuration is provided through environment variables:

- `BILLING_API_KEY`: Required. Shared secret expected in the `X-API-Key` request
  header for all cost endpoints.
- `OCI_AUTH`: Optional. Defaults to `instance_principal`. Initial production
  implementation uses Instance Principal.
- `CACHE_TTL_SECONDS`: Optional. Defaults to `1800`.
- `PORT`: Optional. Defaults to `8000`.
- `LOG_LEVEL`: Optional. Defaults to `INFO`.

The service fails to start when `BILLING_API_KEY` is empty.

## API

### `GET /health`

Unauthenticated health endpoint for Docker and external uptime checks.

Response:

```json
{
  "status": "ok"
}
```

### `GET /cost/month`

Returns the current UTC month's accumulated cost.

Authentication: required.

Request header:

```http
X-API-Key: <configured API key>
```

Response:

```json
{
  "month": "2026-07",
  "currency": "USD",
  "total": 12.34,
  "timeUsageStarted": "2026-07-01T00:00:00Z",
  "timeUsageEnded": "2026-07-07T00:00:00Z",
  "cached": false,
  "lastFetchedAt": "2026-07-07T00:00:00Z"
}
```

### `GET /cost/month/by-service`

Returns the current UTC month's cost grouped by OCI service.

Authentication: required.

Response:

```json
{
  "month": "2026-07",
  "currency": "USD",
  "items": [
    {
      "service": "Compute",
      "total": 8.12
    },
    {
      "service": "Block Storage",
      "total": 4.22
    }
  ],
  "cached": false,
  "lastFetchedAt": "2026-07-07T00:00:00Z"
}
```

### `GET /cost/month/by-resource`

Returns the current UTC month's cost grouped by OCI resource identifier.

Authentication: required.

Response:

```json
{
  "month": "2026-07",
  "currency": "USD",
  "items": [
    {
      "resourceId": "ocid1.instance.oc1.example",
      "service": "Compute",
      "total": 7.88
    }
  ],
  "cached": false,
  "lastFetchedAt": "2026-07-07T00:00:00Z"
}
```

### `GET /cost/month/daily`

Returns daily current-month cost trend.

Authentication: required.

Response:

```json
{
  "month": "2026-07",
  "currency": "USD",
  "items": [
    {
      "date": "2026-07-01",
      "total": 1.74
    },
    {
      "date": "2026-07-02",
      "total": 1.82
    }
  ],
  "cached": false,
  "lastFetchedAt": "2026-07-07T00:00:00Z"
}
```

## OCI Usage API Query Model

All cost queries use the current UTC month:

- `time_usage_started`: first day of the current UTC month at `00:00:00Z`.
- `time_usage_ended`: current UTC timestamp.
- Query type: cost.
- Granularity:
  - Monthly summary can use monthly or daily data aggregated by the service.
  - Daily trend uses daily granularity.
- Grouping:
  - Service endpoint groups by service.
  - Resource endpoint groups by resource identifier and includes service when
    available.

Usage API data can lag behind real usage. Responses expose `lastFetchedAt` and
`cached` so callers know when the service last queried OCI.

## Authentication And Authorization

HTTP authentication is a single static API key supplied in the `X-API-Key`
header. The comparison must be constant-time to avoid leaking key information
through timing differences. Authentication failures return HTTP 401 without
revealing whether the header was missing or incorrect.

OCI authorization is handled with Instance Principal. Deployment requires:

- A Dynamic Group that matches the Compute instance running the container.
- An IAM policy that allows the Dynamic Group to read cost and usage data at the
  tenancy scope required by OCI Usage API.

The exact policy statement should be verified in the target tenancy because OCI
Billing and Cost Management policy verbs can vary by account type and enabled
features.

## Error Handling

The service returns structured errors:

- `401`: missing or invalid `X-API-Key`.
- `503`: OCI authentication or metadata service is unavailable.
- `502`: OCI Usage API returned an upstream error.
- `500`: unexpected internal error.

Upstream OCI errors are logged with request context but responses do not expose
credentials, full OCI request signing details, or configured API keys.

## Docker Deployment

The repository includes:

- `Dockerfile` for a slim Python runtime image.
- `docker-compose.yml` for local and server deployment.
- `.env.example` documenting required environment variables.

The first deployment can expose port `8000` directly:

```bash
docker compose up -d
```

Production deployment should prefer HTTPS termination in front of the service.
The application-level API key remains required even when HTTPS is added.

## Testing Strategy

Unit tests cover:

- API key success and failure.
- Current-month UTC time range calculation.
- OCI Usage API request construction.
- Cost aggregation by total, service, resource, and day.
- Cache hit and cache expiry behavior.
- Mapping OCI SDK failures to HTTP errors.

OCI SDK calls are mocked in unit tests. A manual server integration check runs
on the target OCI Compute instance after Dynamic Group and IAM policy setup.

## Acceptance Criteria

- The Docker image builds successfully.
- The service refuses to start without `BILLING_API_KEY`.
- `/health` returns 200 without authentication.
- Cost endpoints return 401 without a valid `X-API-Key`.
- Cost endpoints return current-month cost data with a valid `X-API-Key`.
- Production authentication uses Instance Principal, not a stored OCI private
  key.
- Responses include `cached` and `lastFetchedAt`.
- Tests pass without real OCI credentials by mocking OCI SDK calls.
