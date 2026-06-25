#!/bin/bash
set -e

docker compose up -d --build
echo "Dashboard available at http://localhost:8501"
