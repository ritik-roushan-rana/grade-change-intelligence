#!/bin/bash
# Launch the Grade Change Intelligence Dashboard
# Usage: ./run_dashboard.sh

echo "Starting Grade Change Intelligence Dashboard..."
echo "Open http://localhost:8501 in your browser"
echo ""

cd "$(dirname "$0")"
streamlit run app.py --server.headless true
