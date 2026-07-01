# ExamPro Deployment Guide

Single-server deployment and tuning for **100–500 concurrent candidates** with video proctoring.

---

## 1. Hardware

| Load                              | vCPU | RAM    | Disk             |
|-----------------------------------|------|--------|------------------|
| Up to 100 candidates              | 8    | 32 GB  | 200 GB NVMe      |
| 100–500 candidates (recommended)  | 16   | 64 GB  | 250–500 GB NVMe  |
| 500+ / long retention             | 32   | 128 GB | 500 GB–1 TB NVMe |

Disk priority is **NVMe IOPS + fsync latency**, not capacity — Postgres/MariaDB
durability is what gates throughput. Proctoring video goes directly to S3/R2,
so it never lands on the app-server disk. Reserve headroom for local DB dumps
(roughly 2× live DB size) before shipping them off-box.

Network: 1 Gbps. NTP/chrony synced — exam timing depends on it.

---

## 2. Stack

- **OS:** Ubuntu 22.04 LTS
- **DB:** MariaDB 10.11 (preferred) or PostgreSQL 15
- **App:** Frappe v15 + ExamPro
- **Web:** nginx 1.24
- **Cache/queue:** Redis 7 (3 instances: cache, queue, socketio)
- **Storage:** S3 or Cloudflare R2 (for proctoring video)
- **Python:** 3.11

---

## 3. Install

```bash
# 1. System packages
sudo apt update && sudo apt install -y \
    python3.11 python3.11-venv python3-dev build-essential \
    mariadb-server redis-server nginx supervisor \
    libmariadb-dev wkhtmltopdf nodejs npm

# 2. Frappe bench
pip3 install frappe-bench
bench init --frappe-branch version-15 ~/frappe-bench
cd ~/frappe-bench

# 3. Site
bench new-site exam.example.com --db-name exampro
bench --site exam.example.com install-app exampro

# 4. Production setup (writes nginx + supervisor configs)
sudo bench setup production $USER
```

---

## 4. ExamPro config

In **Desk → Exam Settings**, set:

- Storage provider (AWS S3 / Cloudflare R2)
- `aws_account_id` (R2 only), `aws_key`, `aws_secret`
- `s3_bucket`

### Bucket CORS (required — browser uploads directly to storage)

```json
[{
  "AllowedOrigins": ["https://exam.example.com"],
  "AllowedMethods": ["PUT"],
  "AllowedHeaders": ["Content-Type", "Content-Length"],
  "ExposeHeaders": ["ETag"],
  "MaxAgeSeconds": 3000
}]
```

### IAM scope

Grant only: `s3:PutObject`, `s3:GetObject`, `s3:ListBucket`, `s3:DeleteObject` on the bucket. Do not reuse a global key.

### Recommended: lock chunks against overwrite

Bucket policy denying `s3:DeleteObject` and `s3:PutObject` overwrites to all principals except the cleanup role. The server already issues unguessable keys; this is belt-and-braces.

---

## 5. System tuning

`/etc/security/limits.d/frappe.conf`:
```
frappe  soft  nofile  1048576
frappe  hard  nofile  1048576
```

`/etc/sysctl.d/99-frappe.conf`:
```
fs.file-max                  = 2097152
net.core.somaxconn           = 65535
net.core.netdev_max_backlog  = 16384
net.ipv4.tcp_max_syn_backlog = 16384
net.ipv4.tcp_tw_reuse        = 1
net.ipv4.tcp_fin_timeout     = 15
net.ipv4.ip_local_port_range = 1024 65535
vm.swappiness                = 10
vm.overcommit_memory         = 1
```
Apply: `sudo sysctl --system`.

Disable transparent hugepages:
```bash
echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
```

Mount the DB data dir on NVMe with `noatime`.

---

## 6. nginx

`/etc/nginx/nginx.conf` (key directives):

```nginx
worker_processes      auto;
worker_rlimit_nofile  200000;
events { worker_connections 8192; use epoll; multi_accept on; }

http {
  sendfile on; tcp_nopush on; tcp_nodelay on;
  keepalive_timeout 65; keepalive_requests 1000;

  client_max_body_size    5m;
  client_body_buffer_size 256k;
  proxy_read_timeout      180s;
  proxy_send_timeout      180s;

  upstream frappe_web  { server 127.0.0.1:8000; keepalive 64; }
  upstream frappe_sock { server 127.0.0.1:9000; keepalive 32; }

  gzip on;
  gzip_types text/css application/javascript application/json;

  server {
    listen 443 ssl http2;
    ssl_protocols TLSv1.2 TLSv1.3;

    location /socket.io/ {
      proxy_pass http://frappe_sock;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
    }

    location /assets/ { root /home/frappe/frappe-bench/sites; expires 1y; }
    location /files/  { root /home/frappe/frappe-bench/sites/exam.example.com/public; expires 1d; }

    location / {
      proxy_pass http://frappe_web;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
  }
}
```

Note: video chunks no longer pass through nginx — they go straight to S3/R2.

---

## 7. Frappe / Gunicorn

`common_site_config.json`:

```json
{
  "background_workers": 4,
  "gunicorn_workers": 24,
  "socketio_port": 9000,
  "redis_cache":    "redis://127.0.0.1:13000",
  "redis_queue":    "redis://127.0.0.1:11000",
  "redis_socketio": "redis://127.0.0.1:12000",
  "rate_limit": { "limit": 600, "window": 60 }
}
```

Gunicorn command (managed by supervisor):
```
gunicorn -b 127.0.0.1:8000 \
  --workers 24 \
  --worker-class gthread --threads 4 \
  --timeout 120 \
  --max-requests 2000 --max-requests-jitter 200 \
  frappe.app:application
```

Worker counts:
- `gunicorn_workers`: ~`1.5 × vCPU`
- `background_workers`: 4 (short/default/long)
- `socketio`: 1 (Node single-threaded; scale by adding processes behind nginx upstream)

---

## 8. Redis

Run 3 separate instances on ports 13000 / 11000 / 12000.

- **cache (13000):** `maxmemory 4gb`, `maxmemory-policy allkeys-lru`
- **queue (11000):** `maxmemory-policy noeviction`, AOF on
- **socketio (12000):** small, defaults fine

---

## 9. Database

### MariaDB 10.11 (recommended)

`/etc/mysql/mariadb.conf.d/99-exampro.cnf`:
```ini
[mysqld]
innodb_buffer_pool_size         = 40G
innodb_log_file_size            = 2G
innodb_flush_log_at_trx_commit  = 2
innodb_io_capacity              = 4000
innodb_io_capacity_max          = 8000
innodb_flush_neighbors          = 0
max_connections                 = 500
thread_cache_size               = 64
table_open_cache                = 8000
tmp_table_size                  = 256M
max_heap_table_size             = 256M
character-set-server            = utf8mb4
collation-server                = utf8mb4_unicode_ci
```

### PostgreSQL 15 (alternative)

`/etc/postgresql/15/main/postgresql.conf`:
```
max_connections                = 300
shared_buffers                 = 16GB
effective_cache_size           = 48GB
work_mem                       = 16MB
maintenance_work_mem           = 2GB
wal_buffers                    = 64MB
synchronous_commit             = off
checkpoint_timeout             = 15min
max_wal_size                   = 8GB
min_wal_size                   = 2GB
checkpoint_completion_target   = 0.9
random_page_cost               = 1.1
effective_io_concurrency       = 200
default_statistics_target      = 200
jit                            = off
log_min_duration_statement     = 500ms
shared_preload_libraries       = 'pg_stat_statements'
```

Front Postgres with **PgBouncer** (transaction pooling): `default_pool_size=50`, `max_client_conn=2000`.

> `synchronous_commit=off` trades a small durability window for throughput. Acceptable on a single-box setup; do **not** use it with replication.

---

## 10. Pre-launch checks

```bash
bench --site exam.example.com migrate
bench --site exam.example.com clear-cache
bench --site exam.example.com console <<< "import frappe; print(frappe.db.sql('SELECT 1'))"

# Verify storage path
bench --site exam.example.com execute \
  exampro.exam_pro.doctype.exam_settings.exam_settings.validate_video_settings
```

Smoke test:
```bash
cd loadtest && pip install -r requirements.txt
python test_data_manager.py setup
locust -f locustfile.py --host=https://exam.example.com \
       --users=100 --spawn-rate=10 --run-time=15m --headless
```

Target SLOs during load test:
- p95 question fetch < 500 ms
- p95 answer submit < 400 ms
- Video upload success rate > 99%
- DB CPU < 70%, app CPU < 70%

---

## 11. Scaling beyond one box

When a single server is not enough:

1. **Move DB off** the app server first (separate MariaDB/Postgres node).
2. **Move Redis off** (managed Redis or a small dedicated VM).
3. **Add app nodes** behind a load balancer; share Redis + DB. Frappe is stateless except for socketio — pin socketio behind a sticky upstream or run multiple socketio nodes against shared Redis.
4. **Cloudflare/CDN in front** of `/assets/` and `/files/`.
5. **Read replica** for Postgres/MariaDB once read traffic on the report views dominates.

---

## 12. Operational notes

- **Backups:** logical (`mysqldump` / `pg_dump`) nightly + DB binlog/WAL archived to object storage. Frappe `sites/<site>/private` also needs backup (private files, encryption key).
- **Monitoring:** node_exporter + mysqld_exporter / postgres_exporter + Frappe slow log. Track gunicorn busy workers, Redis memory, DB connection count.
- **Logs:** `bench logs`, `/var/log/nginx/`, supervisor logs under `~/frappe-bench/logs/`.
- **Time:** ensure chrony is running and synced — exam start/end is computed server-side and assumes accurate wall clock.
- **TLS:** terminate at nginx; HSTS on; modern cipher suite only.
