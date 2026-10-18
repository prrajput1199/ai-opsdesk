#!/bin/sh
set -e
python manage.py migrate --noinput
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  # Demo data for local Docker runs only. Never enable this on a real deployment.
  python manage.py seed_demo --allow-production || true
fi
exec "$@"
