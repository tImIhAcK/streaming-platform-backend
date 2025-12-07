#!/bin/bash
set -e

echo "Waiting for database..."
while ! nc -z db 5432; do
  sleep 2
done
echo "✓ Database is up!"

# Only run migrations if this is the app container
if [ "$1" = "uvicorn" ]; then
  echo "Running database migrations..."
  alembic upgrade head
  echo "✓ Migrations completed!"

  echo "Running initial data setup..."
  python -m app.initial_data
  echo "✓ Initial data setup completed!"
fi

echo "Starting application..."
exec "$@"
