#!/usr/bin/env bash
# Start Chart Suggest: FastAPI Backend + Streamlit Frontend

echo "🔍 Cleaning up existing ports 8000 & 8501..."
lsof -ti :8000 | xargs kill -9 2>/dev/null
lsof -ti :8501 | xargs kill -9 2>/dev/null

echo "🚀 Starting FastAPI backend on http://localhost:8000..."
(cd backend && python -m uvicorn main:app --port 8000 --reload) &
BACKEND_PID=$!

sleep 2

echo "✨ Starting Streamlit frontend on http://localhost:8501..."
python -m streamlit run frontend/app.py --server.port 8501 &
FRONTEND_PID=$!

echo "✅ Chart Suggest is running!"
echo "   - Frontend UI: http://localhost:8501"
echo "   - Backend API: http://localhost:8000"
echo "   - API Docs:    http://localhost:8000/docs"
echo "Press Ctrl+C to stop both servers."

trap "echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM EXIT

wait
