# Deployment — CALL-E Backend on Google Cloud

Hackathon deployment guide. Target: a **single Google Compute Engine VM** running
the stack with Docker Compose. Every push to `main` runs CI, builds a Docker
image, pushes it to the **GitHub Container Registry (GHCR)**, then SSHes into the
VM and rolls the running stack forward to the new image.

```
git push origin main
      │
      ▼
GitHub Actions ── job: backend ──────► ruff / mypy / alembic / pytest   (must pass)
      │
      ▼
GitHub Actions ── job: build-and-deploy (main only)
      │  1. docker build  backend/Dockerfile
      │  2. docker push   ghcr.io/newton-and-chero/call-e-docs:<sha>  (+ :latest)
      │  3. ssh  →  GCE VM
      ▼
GCE VM  /opt/calle/deploy.sh <sha>
      │  git pull        (refresh compose files)
      │  docker compose pull
      │  alembic upgrade head          (one-shot, before new code serves traffic)
      │  docker compose up -d           (api + worker + beat + db + redis [+ caddy])
      ▼
https://<public-url>/healthz  →  {"status":"ok"}
```

---

## 1. What actually gets deployed

One Docker image (`backend/Dockerfile`) serves **three roles**, selected by the
`command:` in each Compose service:

| Service  | Image        | Command (prod)                                              | Purpose |
|----------|--------------|------------------------------------------------------------|---------|
| `api`    | our image    | `gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 4` | FastAPI REST/WS + CALL-E webhook receiver |
| `worker` | our image    | `celery -A app.workers.celery_app worker`                  | sweep orchestration + analytics tasks |
| `beat`   | our image    | `celery -A app.workers.celery_app beat`                    | scheduled watchlist sweeps |
| `db`     | `postgis/postgis:16-3.4` | —                                             | Postgres + PostGIS, named volume `db_data` |
| `redis`  | `redis:7-alpine`         | —                                             | Celery broker + cache + rate-limit + call-gate state |

Compose file layering (never a second full copy — additive overrides only):

```
docker-compose.yml            # base: build, ports, healthchecks, depends_on
  + docker-compose.prod.yml   # gunicorn, restart policies, resource limits, no bind mounts
  + docker-compose.deploy.yml # NEW (this guide): use GHCR image instead of building, close DB/Redis ports
```

Run command on the VM (wrapped by `deploy.sh`):

```sh
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.deploy.yml \
  up -d
```

---

## 2. One-time setup

### 2.1 Create the VM

```sh
gcloud compute instances create calle-prod \
  --project=<YOUR_GCP_PROJECT> \
  --zone=europe-west1-b \
  --machine-type=e2-medium \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB \
  --tags=calle-http
```

`e2-medium` (2 vCPU / 4 GB) is enough for the demo. The prod override caps
container resources; the box needs headroom for Postgres + 4 gunicorn workers +
1 Celery worker.

### 2.2 Firewall

Open only what is served publicly. If you use the **Caddy** option (2.6,
recommended — CALL-E webhooks want HTTPS), open 80/443. Otherwise open 8000.

```sh
# With Caddy (HTTPS):
gcloud compute firewall-rules create calle-web \
  --allow=tcp:80,tcp:443 --target-tags=calle-http --direction=INGRESS

# Without Caddy (plain HTTP on :8000):
gcloud compute firewall-rules create calle-api \
  --allow=tcp:8000 --target-tags=calle-http --direction=INGRESS
```

`docker-compose.deploy.yml` closes the `db` (5433) and `redis` (6379) host
ports that the base file opens for local dev — they must never be internet-facing.

### 2.3 Install Docker on the VM

```sh
gcloud compute ssh calle-prod --zone=europe-west1-b

# on the VM:
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker   # or log out / back in
docker compose version   # must be >= 2.24 for the !reset merge tag
```

### 2.4 Place the repo on the VM

The deploy pulls compose files + `deploy.sh` from git; only the image comes from
GHCR.

```sh
sudo mkdir -p /opt/calle && sudo chown $USER:$USER /opt/calle
git clone https://github.com/Newton-And-Chero/CALL-E-Docs.git /opt/calle
```

### 2.5 Create the production `.env`

`.env` is git-ignored — it never leaves the VM. Compose reads it two ways: for
`${VAR}` interpolation in the compose files, and as `env_file:` for the app
containers.

```sh
cp /opt/calle/backend/.env.example /opt/calle/backend/.env
nano /opt/calle/backend/.env
```

Values that **must** change from the example for a real deploy:

| Variable | Set to | Why |
|---|---|---|
| `ENV` | `production` | enables the placeholder-secret boot guard |
| `JWT_SECRET` | a real random 32+ char secret (`openssl rand -hex 32`) | app **refuses to boot** in `production` with a placeholder |
| `PUBLIC_BASE_URL` | `https://<your-public-url>` | used to build the CALL-E `webhook_url`; must be reachable from CALL-E |
| `CORS_ALLOW_ORIGINS` | `["https://<your-frontend-origin>"]` | JSON array; no wildcard |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:<STRONG_PW>@db:5432/calle` | keep host `db` (compose network) |
| `POSTGRES_PASSWORD` *(see note)* | same strong password | see 2.5.1 |
| `REDIS_URL` | `redis://redis:6379/0` | keep host `redis` |
| `CALL_E_MODE` | `mock` for a dry run, `live` for real calls | `live` places billed phone calls |
| `CALLE_API_KEY` / `CALLE_BASE_URL` / `CALLE_WEBHOOK_TOKEN` | real values (only needed if `live`) | — |
| `SMS_MODE` | `mock` or `live` | `live` sends real Twilio SMS |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` or `TWILIO_MESSAGING_SERVICE_SID` | real values (only if `live`) | — |
| `CALLS_ENABLED_DEFAULT` | `false` | outbound calls stay off until an operator flips `POST /v1/call-engine/enable` |
| `CALL_DEMO_REDIRECT_NUMBERS` | `["+2547XXXXXXXX", ...]` | hackathon guardrail — every call redirected to these numbers, one facility per number |
| `SMS_DEMO_REDIRECT_NUMBERS` | `["+2547XXXXXXXX", ...]` | hackathon guardrail — every SMS redirected to these (Twilio trial only texts verified numbers) |
| `API_IMAGE` | `ghcr.io/newton-and-chero/call-e-docs:latest` | consumed by `docker-compose.deploy.yml`; `deploy.sh` overrides it per-release with the commit SHA |

> Keep `CALL_E_MODE=mock` and `SMS_MODE=mock` until the moment you actually want
> the demo to dial real phones. `seed_demo.py` is always mock regardless.

#### 2.5.1 Postgres password

The base compose file hardcodes `POSTGRES_USER/PASSWORD/DB` for the `db` service
(dev defaults). For production, override them from `.env` by adding this to
`docker-compose.deploy.yml` (already included in the file below) so the DB
credentials match `DATABASE_URL`:

```yaml
  db:
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}
```

Then set `POSTGRES_PASSWORD=<STRONG_PW>` in `.env` and use the same password in
`DATABASE_URL`. If you change this **after** the `db_data` volume already exists,
Postgres keeps the old password — you must `docker compose down -v` (wipes data)
or `ALTER USER` manually.

### 2.6 (Recommended) HTTPS with Caddy

CALL-E delivers call results to `PUBLIC_BASE_URL` — an HTTPS endpoint is the safe
assumption. No domain? Use `nip.io`: `<VM_EXTERNAL_IP>.nip.io` resolves to your
IP and Caddy will get a Let's Encrypt cert for it automatically.

Create `/opt/calle/backend/Caddyfile`:

```
<VM_EXTERNAL_IP>.nip.io {
    reverse_proxy api:8000
}
```

The `caddy` service is included (commented) in `docker-compose.deploy.yml` below —
uncomment it, and set `PUBLIC_BASE_URL=https://<VM_EXTERNAL_IP>.nip.io`.

### 2.7 GHCR image visibility

Simplest for a hackathon: after the first successful push, open
`https://github.com/orgs/Newton-And-Chero/packages`, open the `call-e-docs`
package → **Package settings** → **Change visibility → Public**. Then the VM
pulls with no auth.

If you keep it **private**, create a classic PAT with `read:packages`, and add
`GHCR_USER` / `GHCR_TOKEN` to the VM's `.env`; `deploy.sh` logs in with them.

---

## 3. Files to add to the repo

These three files are committed once. CI and `deploy.sh` depend on them.

### 3.1 `backend/docker-compose.deploy.yml`

```yaml
# Deploy-time override: run the pre-built GHCR image instead of building from
# source, and stop exposing infrastructure ports to the host. Layered LAST:
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.deploy.yml ...
services:
  db:
    ports: !reset []
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}

  redis:
    ports: !reset []

  api:
    build: !reset null
    image: ${API_IMAGE:?set API_IMAGE}
    pull_policy: always

  worker:
    build: !reset null
    image: ${API_IMAGE:?set API_IMAGE}
    pull_policy: always

  beat:
    build: !reset null
    image: ${API_IMAGE:?set API_IMAGE}
    pull_policy: always

  # --- Optional: HTTPS reverse proxy (see DEPLOYMENT.md 2.6) ---
  # caddy:
  #   image: caddy:2-alpine
  #   restart: unless-stopped
  #   ports:
  #     - "80:80"
  #     - "443:443"
  #   volumes:
  #     - ./Caddyfile:/etc/caddy/Caddyfile:ro
  #     - caddy_data:/data
  #     - caddy_config:/config
  #   depends_on:
  #     - api

# volumes:
#   caddy_data:
#   caddy_config:
```

> If you uncomment `caddy`, also add `ports: !reset []` under `api:` here so the
> API is only reachable through Caddy.

### 3.2 `deploy.sh`  (repo root, `chmod +x`)

```sh
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=/opt/calle
IMAGE_TAG="${1:?usage: deploy.sh <image-tag>}"
IMAGE_REPO="ghcr.io/newton-and-chero/call-e-docs"

cd "$REPO_DIR"
git fetch --depth 1 origin main
git reset --hard origin/main          # refresh compose files + this script; .env is git-ignored, untouched

cd "$REPO_DIR/backend"

export API_IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"

COMPOSE="docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.deploy.yml"

# Private GHCR package only — set GHCR_USER / GHCR_TOKEN in backend/.env
if grep -q '^GHCR_TOKEN=' .env; then
  set -a; . ./.env; set +a
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
fi

$COMPOSE pull
$COMPOSE run --rm api uv run alembic upgrade head   # migrations BEFORE new code serves
$COMPOSE up -d --remove-orphans
$COMPOSE ps
docker image prune -f
```

### 3.3 `.github/workflows/ci.yml` — add the deploy job

Append this job to the existing workflow (keep the current `backend` job as-is).
It only runs on a **push to `main`** and only **after tests pass**.

```yaml
  build-and-deploy:
    needs: backend
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Image metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=sha,format=long
            type=raw,value=latest

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: backend
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.GCP_SSH_HOST }}
          username: ${{ secrets.GCP_SSH_USER }}
          key: ${{ secrets.GCP_SSH_KEY }}
          script: /opt/calle/deploy.sh ${{ github.sha }}
```

`ghcr.io/${{ github.repository }}` lowercases to
`ghcr.io/newton-and-chero/call-e-docs`. `type=sha,format=long` tags the image
with the full commit SHA — the same value passed to `deploy.sh`.

---

## 4. GitHub repository secrets

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `GCP_SSH_HOST` | VM external IP (`gcloud compute instances describe calle-prod --format='get(networkInterfaces[0].accessConfigs[0].natIP)'`) |
| `GCP_SSH_USER` | the Linux user on the VM (the one in the `docker` group, owns `/opt/calle`) |
| `GCP_SSH_KEY` | **private** key whose public half is in that user's `~/.ssh/authorized_keys` |

`GITHUB_TOKEN` is automatic — no secret needed for the GHCR push, just the
`packages: write` permission already in the job.

SSH key setup:

```sh
ssh-keygen -t ed25519 -f calle_deploy -N ""
# put calle_deploy.pub on the VM:
gcloud compute ssh calle-prod --zone=europe-west1-b \
  --command="echo '$(cat calle_deploy.pub)' >> ~/.ssh/authorized_keys"
# paste the contents of ./calle_deploy into the GCP_SSH_KEY secret
```

---

## 5. First deployment (bootstrap)

Do this once, manually on the VM, so migrations + seed data exist before the
first automated deploy:

```sh
gcloud compute ssh calle-prod --zone=europe-west1-b
cd /opt/calle/backend

# point at the latest image built by CI (push to main at least once first)
export API_IMAGE=ghcr.io/newton-and-chero/call-e-docs:latest

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.deploy.yml"

$COMPOSE pull
$COMPOSE up -d db redis
$COMPOSE run --rm api uv run alembic upgrade head
$COMPOSE run --rm api uv run python -m scripts.seed_demo   # facilities, commodities, users, 8 weeks mock sweep history
$COMPOSE up -d
$COMPOSE ps
```

Verify:

```sh
curl -fsS http://localhost:8000/healthz          # {"status":"ok"}
curl -fsS https://<your-public-url>/healthz       # from your laptop
```

Seed logins (mock deploy only — password `testpass123`): `+254700000001` (admin),
`+254700000002` (analyst), `+254700000003` (viewer).

After this, every `git push origin main` deploys automatically.

---

## 6. Routine deploys

```sh
git push origin main
```

Watch the run in the **Actions** tab. On success the VM is already updated.
`deploy.sh` runs `alembic upgrade head` every time (no-op when there are no new
migrations).

Manual redeploy of the current `main` without a code change:

```sh
gcloud compute ssh calle-prod --zone=europe-west1-b --command="/opt/calle/deploy.sh \$(git -C /opt/calle rev-parse origin/main)"
```

---

## 7. Migrations

- Never run automatically at container start — the compose services just run the
  app. `deploy.sh` runs `alembic upgrade head` as a one-shot
  `docker compose run --rm api` **before** `up -d`, so the schema is ready
  before the new `api`/`worker` start serving.
- Migrations live in `backend/alembic/versions/` and are applied in CI too
  (`Alembic upgrade head` step), so a broken migration fails the build before it
  can reach production.
- Rolling a migration back is manual: `docker compose ... run --rm api uv run alembic downgrade -1`.

---

## 8. Verifying a deploy

```sh
# on the VM, from /opt/calle/backend
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.deploy.yml"

$COMPOSE ps                      # all services "running (healthy)"
$COMPOSE logs -f api             # startup, no traceback
curl -fsS http://localhost:8000/healthz

# from your laptop
curl -fsS https://<your-public-url>/healthz
open https://<your-public-url>/docs
```

Healthchecks are defined for every service; `api` probes `/healthz`, `worker`
uses `celery inspect ping`, `beat` checks its pidfile.

---

## 9. Rollback

Images are tagged by commit SHA and kept in GHCR. To go back:

```sh
gcloud compute ssh calle-prod --zone=europe-west1-b
/opt/calle/deploy.sh <previous-good-sha>
```

`deploy.sh` also does `git reset --hard origin/main`, which would pull the newer
compose files — for a true rollback, also revert the commit on `main`
(`git revert <bad-sha> && git push`) so the pipeline redeploys the previous state
cleanly. If a bad **migration** shipped, downgrade it manually (7) before
rolling the image back.

---

## 10. Demo-day checklist

- [ ] `backend/.env` on the VM: `ENV=production`, real `JWT_SECRET`, correct
      `PUBLIC_BASE_URL` (HTTPS), `CORS_ALLOW_ORIGINS` has the demo frontend.
- [ ] `CALL_DEMO_REDIRECT_NUMBERS` and `SMS_DEMO_REDIRECT_NUMBERS` set to the
      team's verified phones (JSON arrays).
- [ ] Decide `CALL_E_MODE` / `SMS_MODE`: `mock` for a safe run, `live` only when
      you want real calls/SMS. After editing `.env`, restart:
      `docker compose -f ... up -d`.
- [ ] `seed_demo` has been run (analytics time-series has 8 weeks of data).
- [ ] Calls start disabled (`CALLS_ENABLED_DEFAULT=false`). Enable at showtime:
      `POST /v1/call-engine/enable` (admin token). Disable again with
      `POST /v1/call-engine/disable`.
- [ ] `GET /healthz` green from outside the VM; `GET /docs` loads.
- [ ] One end-to-end dry run: `POST /v1/sweeps/query` → watch
      `/ws/sweeps/{id}` → `GET /v1/analytics/stockout-rate` reflects it.
- [ ] `docker compose ps` — all healthy; disk not full (`df -h`).

---

## 11. Troubleshooting

| Symptom | Check |
|---|---|
| `api` exits immediately, `ValueError: JWT_SECRET is still a placeholder` | set a real `JWT_SECRET` in `.env` (guard fires only when `ENV=production`) |
| `docker compose` errors on `!reset` | Compose plugin `< 2.24` — `curl -fsSL https://get.docker.com \| sudo sh` to update |
| `denied` / `manifest unknown` on `docker compose pull` | GHCR package is private and the VM isn't logged in — make it public (2.7) or set `GHCR_USER`/`GHCR_TOKEN` in `.env` |
| CI deploy step: `ssh: handshake failed` | `GCP_SSH_KEY` is the wrong key, or its `.pub` isn't in the VM user's `authorized_keys`, or `GCP_SSH_USER` is wrong |
| CALL-E webhooks never arrive | `PUBLIC_BASE_URL` not publicly reachable / not HTTPS; firewall rule missing; Caddy not running |
| `api` up but DB errors | migrations not applied (`deploy.sh` step), or `DATABASE_URL` password ≠ `POSTGRES_PASSWORD` (2.5.1) |
| Postgres won't accept new password | old `db_data` volume — `docker compose down -v` wipes it, then re-bootstrap (5) |
| workers idle, sweeps stuck `pending` | `worker`/`beat` unhealthy or Redis unreachable — `docker compose logs worker redis` |
| disk full after many deploys | `docker image prune -af && docker builder prune -f` |

---

## 12. Optional hardening (post-hackathon)

- Add `backend/.dockerignore` (`.git`, `.venv`, `.mypy_cache`, `.ruff_cache`,
  `.pytest_cache`, `tests`, `*.md`) — smaller, faster image builds.
- Move Postgres/Redis to managed Cloud SQL / Memorystore.
- Real secrets via GCP Secret Manager instead of a plaintext `.env` on the box.
- Pin `postgis`/`redis`/`caddy` images by digest.
- Nightly `pg_dump` of `db_data` to a Cloud Storage bucket.
