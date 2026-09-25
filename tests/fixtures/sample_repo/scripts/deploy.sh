#!/bin/bash
# Deployment script
set -euo pipefail

echo "Building project..."
python -m build

echo "Running tests..."
pytest tests/

echo "Deploying..."
echo "Done!"
