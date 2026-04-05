FROM python:3.11-slim
WORKDIR /app
COPY taskmanager_fastapi/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY taskmanager_fastapi/ .
# Copy UI files from the root context
COPY tools/mcp-dev-remote/ui/public ./ui
ENV TASK_MANAGER_DB=/data/tasks.db
ENV TASK_MANAGER_UI_DIR=/app/ui
EXPOSE 6543
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6543"]
