@echo off
REM Batch to start uvicorn with env vars for TaskManager
set TASK_MANAGER_DB=C:\ENM Projects\PadelFlow\tools\mcp-dev-remote\tasks.db
set TASK_MANAGER_API_KEY=dev_local_key
echo Starting uvicorn on 127.0.0.1:6543
"%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 6543
