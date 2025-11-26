#!/usr/bin/env bash

set -e  # stop if any command fails

echo "🔧 Sorting imports..."
isort .

echo "🖤 Formatting code..."
black .

# echo "🔍 Running type checks..."
# mypy --config-file=pyproject.toml .

echo "✅ All checks completed!"
