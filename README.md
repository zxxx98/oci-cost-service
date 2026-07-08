# OCI Cost Service

Dockerized FastAPI service for querying the current UTC month's Oracle Cloud
Infrastructure cost through OCI Usage API.

The service is designed to run on an OCI Compute instance. It uses Instance
Principal authentication for OCI access and protects public HTTP cost endpoints
with an `X-API-Key` header.

## Features

- Current-month total cost.
- Current-month cost grouped by OCI service.
- Current-month cost grouped by OCI resource.
- Current-month daily cost trend.
- Optional Nezha dashboard widget endpoint for one configured server.
- In-memory TTL cache for Usage API responses.
- Docker deployment with configurable public port.
- No OCI user API key or private key file required in production.

## API

Health check does not require authentication:

```bash
curl http://SERVER_IP:8000/health
```

Cost endpoints require `X-API-Key`:

```bash
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month/by-service
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month/by-resource
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month/daily
```

Nezha widget endpoint does not require `X-API-Key`; it only returns data when
`serverId` matches `NEZHA_SERVER_ID`. Non-target servers receive `204 No Content`:

```bash
curl "http://SERVER_IP:8000/widget/month?serverId=1"
```

Example response:

```json
{
  "month": "2026-07",
  "currency": "SGD",
  "timeUsageStarted": "2026-07-01T00:00:00Z",
  "timeUsageEnded": "2026-07-08T00:00:00Z",
  "cached": false,
  "lastFetchedAt": "2026-07-08T02:53:03Z",
  "total": 0.0
}
```

## OCI IAM

Create a Dynamic Group for the Compute instance that runs this service. For a
single instance, use an instance OCID matching rule:

```text
instance.id = '<instance_ocid>'
```

Create a policy at the tenancy/root compartment:

```text
Allow dynamic-group <dynamic_group_name> to read usage-report in tenancy
```

IAM changes can take a few minutes to propagate.

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env`:

```env
BILLING_API_KEY=replace-with-a-long-random-secret
OCI_AUTH=instance_principal
CACHE_TTL_SECONDS=1800
NEZHA_SERVER_ID=
HOST_PORT=8000
PORT=8000
LOG_LEVEL=INFO
```

Generate a random API key:

```bash
openssl rand -hex 32
```

`HOST_PORT` is the public host port. `PORT` is the internal Uvicorn port inside
the container and should normally remain `8000`.

Set `NEZHA_SERVER_ID` only when exposing the Nezha widget endpoint. Leave it
empty to disable widget responses.

## Docker

Build and start:

```bash
docker compose up -d --build
```

Check status:

```bash
docker ps --filter name=oci-cost-service
docker logs oci-cost-service
```

Stop:

```bash
docker compose down
```

## Direct Docker Run

```bash
API_KEY="$(openssl rand -hex 32)"

docker build -t oci-cost-service:latest .
docker run -d \
  --name oci-cost-service \
  --restart unless-stopped \
  -e BILLING_API_KEY="$API_KEY" \
  -e OCI_AUTH=instance_principal \
  -e CACHE_TTL_SECONDS=1800 \
  -e NEZHA_SERVER_ID=1 \
  -e PORT=8000 \
  -p 20000:8000 \
  oci-cost-service:latest
```

Then call:

```bash
curl -H "X-API-Key: $API_KEY" http://SERVER_IP:20000/cost/month
```

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/python -m pytest -v
```

## Security Notes

- Do not commit `.env`.
- Do not expose the service without `X-API-Key`.
- Do not put `BILLING_API_KEY` in frontend custom code. Use `/widget/month`
  only for limited dashboard display data.
- Use HTTPS termination, such as Caddy, Nginx, or an OCI Load Balancer, for
  public production access.
- Rotate `BILLING_API_KEY` if it is ever shared accidentally.
