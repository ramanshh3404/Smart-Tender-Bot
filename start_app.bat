@echo off
echo =========================================================
echo  Procurement ^& Vendor Query Analyzer (The Smart Tender Bot)
echo =========================================================
echo.

echo [1/3] Launching FastAPI Backend on http://localhost:8000...

start "Tender Bot - Backend API" cmd /k "python -m uvicorn backend.main:app --reload --port 8000"
echo [2/3] Launching React-Vite Frontend on http://localhost:5173...
start "Tender Bot - Frontend UI" cmd /k "cd frontend && npm.cmd run dev"

echo.
echo [3/3] Application Launch Initiated!
echo =========================================================
echo  - Backend Docs: http://localhost:8000/docs
echo  - Frontend App: http://localhost:5173
echo =========================================================
echo.
pause
