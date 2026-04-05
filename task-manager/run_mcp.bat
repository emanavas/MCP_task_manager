@echo off
set TASK_MANAGER_DB=C:\ENM Projects\PadelFlow\tools\mcp-dev-remote\tasks.db
set TASK_MANAGER_UI_DIR=C:\ENM Projects\PadelFlow\tools\mcp-dev-remote\ui\public
%~dp0\.venv\Scripts\python.exe %~dp0\mcp_server.py
