#!/bin/bash
# Start FastAPI backend in background
uvicorn api:app --host 0.0.0.0 --port 8000 &

# Start Streamlit frontend in foreground
exec streamlit run app.py --server.port 7860 --server.address 0.0.0.0
