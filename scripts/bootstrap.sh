#!/usr/bin/env bash
set -euo pipefail
cp -n .env.example .env || true
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed
docker compose exec scraper python -m scraper.run --source NSFDC
echo "Open http://localhost:3000"
