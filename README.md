# OCI Current Month Cost Service

Dockerized FastAPI service for querying the current UTC month's OCI cost.

## Configuration

Copy `.env.example` to `.env` and set a long random `BILLING_API_KEY`.

```env
BILLING_API_KEY=replace-with-a-long-random-secret
OCI_AUTH=instance_principal
CACHE_TTL_SECONDS=1800
PORT=8000
LOG_LEVEL=INFO
```

## OCI IAM

Deploy this service on an OCI Compute instance and use Instance Principal
authentication. Create a Dynamic Group that matches the instance, then grant the
group permission to read tenancy cost and usage data required by OCI Usage API.

Verify the exact policy statement in the target tenancy's Billing and Cost
Management IAM documentation before production use.

## Run

```bash
docker compose up -d --build
```

## Check

```bash
curl http://SERVER_IP:8000/health
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month/by-service
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month/by-resource
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month/daily
```

## Security

The initial deployment exposes port 8000 directly and uses `X-API-Key` for
application authentication. For public production use, put the service behind
HTTPS termination with Caddy, Nginx, an OCI Load Balancer, or another TLS proxy.
