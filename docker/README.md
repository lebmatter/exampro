# ExamPro Docker Setup

Local development deployment with PostgreSQL 15, Redis 7, and Frappe v15.

## Quick start

```bash
cd docker
cp .env.example .env
# Edit .env — at minimum change DB_ROOT_PASSWORD and ADMIN_PASSWORD

docker compose up -d
```

First run takes a few minutes — it creates the site, installs exampro, and runs migrations.

Watch logs:

```bash
docker compose logs -f frontend
```

Once you see `Booting worker` from gunicorn, the site is ready at http://localhost:8080.

## Services

| Service        | Port  | Purpose                     |
|----------------|-------|-----------------------------|
| frontend       | 8080  | Frappe web + socketio       |
| db             | 5432  | PostgreSQL 15               |
| redis-cache    | —     | Cache (allkeys-lru, 512 MB) |
| redis-queue    | —     | Background jobs (AOF on)    |
| redis-socketio | —     | Realtime pub/sub            |

## Architecture

- **PostgreSQL** is used instead of MariaDB — Frappe v15 supports both. The compose file configures `db_type: postgres` in `common_site_config.json` automatically.
- **Redis** runs as 3 separate containers matching Frappe's expected topology (cache / queue / socketio), connected via Docker DNS names.
- The exampro app directory is bind-mounted into the container so local code changes are reflected immediately (restart gunicorn with `docker compose restart frontend` or use `bench start` inside the container).

## Useful commands

```bash
# Open a bench shell
docker compose exec frontend bash

# Run bench commands
docker compose exec frontend bench --site exam.localhost console
docker compose exec frontend bench --site exam.localhost migrate
docker compose exec frontend bench --site exam.localhost clear-cache

# Reset (wipe all data)
docker compose down -v
```
