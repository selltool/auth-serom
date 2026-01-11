#!/bin/bash
set -e

echo "Pulling latest code..."
git pull

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting Python app..."
exec ./.venv/bin/python app.py
