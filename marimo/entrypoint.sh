#!/bin/bash
set -e

VENV_DIR="/app/state/venv"
REQUIREMENTS="/app/requirements.txt"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python -m venv "$VENV_DIR"

    # Install base requirements
    source "$VENV_DIR/bin/activate"
    pip install --no-cache-dir -r "$REQUIREMENTS"
else
    echo "Using existing virtual environment from $VENV_DIR"
    source "$VENV_DIR/bin/activate"

    # Optionally sync requirements (install any new ones)
    pip install --no-cache-dir -r "$REQUIREMENTS" 2>/dev/null || true
fi

# Run marimo with the configured mode and notebook
exec marimo "${MARIMO_MODE:-edit}" "/app/${MARIMO_NOTEBOOK:-main.py}" \
    --host 0.0.0.0 \
    --port 8080 \
    --no-token
