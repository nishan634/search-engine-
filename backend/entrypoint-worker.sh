#!/bin/sh
set -e
exec celery -A config worker --loglevel=info --concurrency="${CELERY_CONCURRENCY:-2}"
