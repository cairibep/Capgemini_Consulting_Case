#!/bin/bash
set -e

echo "Running ETL pipeline..."
python -m etl.pipeline

echo "Starting Streamlit..."
exec streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port=8501 \
  --server.headless=true
