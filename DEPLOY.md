# Deploy

CI/CD lives in `.gitea/workflows/ci.yaml`. On push to `main`, Gitea Actions builds both Docker images, ships them via SSH to the Lightsail host, and `docker compose up -d`s on the box. Other branches lint+build only.

This doc covers the **one-time host setup** the workflow assumes is already in place.

## Prerequisites

- Lightsail (or any) host reachable as `ec2-user@tyler.colberts.us`
- Docker + docker compose installed on the host
- A reverse proxy (nginx) on the host fronting the public domain
- Gitea repo secret `LIGHTSAIL_SSH_KEY` set to a private key whose public half is in `~ec2-user/.ssh/authorized_keys`

## DNS

Point an A-record at the Lightsail static IP:

```
chemplan.colberts.us  →  <lightsail-ip>
```

## Host: model-data volume

AiZynthFinder needs ~750MB of USPTO model data. The backend container's entrypoint downloads it on first run if missing, so we just need a host directory to bind-mount:

```bash
sudo mkdir -p /opt/chemplan/data
sudo chown -R 1000:1000 /opt/chemplan/data
```

The first deploy will spend ~2–3 minutes downloading. Subsequent deploys are fast — the data persists across image rebuilds.

## Host: secrets

`docker-compose.yml` reads `~/chemplan/.env` (created on the host, never committed). Required:

```
ANTHROPIC_API_KEY=sk-ant-…
```

## Host: nginx reverse proxy

The compose file binds the frontend container to `127.0.0.1:8084` so it isn't directly exposed. Add an nginx site that terminates TLS and proxies to it:

```nginx
server {
    listen 443 ssl http2;
    server_name chemplan.colberts.us;

    # ssl_certificate / ssl_certificate_key managed by certbot

    location / {
        proxy_pass http://127.0.0.1:8084;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # /chat is NDJSON-streamed token-by-token — must not buffer.
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}

server {
    listen 80;
    server_name chemplan.colberts.us;
    return 301 https://$host$request_uri;
}
```

Reload nginx (`sudo nginx -t && sudo systemctl reload nginx`) once the cert is in place.

## First deploy

Once DNS resolves and the host directory + `.env` exist, push to `main`. The workflow will:

1. Build both Docker images on the runner.
2. `scp` them and `docker-compose.yml` to `~/chemplan/` on the host.
3. `docker compose up -d --force-recreate`.
4. Poll `http://localhost:8084/health` for up to 5 minutes (longer than designpair because the first-run AiZynthFinder download eats most of that).

## Rollback

```bash
ssh ec2-user@tyler.colberts.us
cd ~/chemplan
docker compose down
# re-tag a previous image as :latest, or re-run an older workflow run
docker compose up -d
```
