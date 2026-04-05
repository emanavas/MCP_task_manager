from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
import json, asyncio, os
from sqlmodel import SQLModel, create_engine, Session, text
from models import Task, Group, Setting
import crud
from events import subscribe, unsubscribe, push_event
from schemas import (
    ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate, 
    GroupCreate, GroupUpdate, ReorderPayload
)

# Configuration
API_KEY = os.environ.get("TASK_MANAGER_API_KEY", "dev_local_key")
DB_PATH = os.environ.get("TASK_MANAGER_DB", r"C:\ENM Projects\PadelFlow\tools\mcp-dev-remote\tasks.db")
UI_DIR = os.environ.get("TASK_MANAGER_UI_DIR", r"C:\ENM Projects\PadelFlow\tools\mcp-dev-remote\ui\public")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
app = FastAPI(title="TaskManager FastAPI")

# CORS
origins = ["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "x-api-key"]
)

# --- UI Routes ---
@app.get('/', include_in_schema=False)
@app.get('/index.html', include_in_schema=False)
def serve_index(request: Request):
    index_path = os.path.join(UI_DIR, 'index.html')
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail='UI index.html not found')
    
    with open(index_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Inject API Key and Base URL for the UI to use
    injection = f"""
    <script>
        window.TASK_MANAGER_API_KEY = "{API_KEY}";
        window.TASK_MANAGER_API_BASE = "";
    </script>
    """
    # Insert before </head>
    if '</head>' in html:
        html = html.replace('</head>', f'{injection}</head>')
    else:
        html = html + injection
        
    return HTMLResponse(content=html)

@app.get('/favicon.ico', include_in_schema=False)
def favicon():
    p = os.path.join(UI_DIR, 'favicon.ico')
    if os.path.exists(p):
        return FileResponse(p, media_type='image/x-icon')
    raise HTTPException(status_code=404)

# --- API Routes ---
async def require_api_key(x_api_key: str = Header(None)):
    pass
#        raise HTTPException(status_code=401, detail="Invalid API Key")

@app.get('/api/events')
async def sse_events(request: Request):
    q = subscribe()
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await q.get()
                except asyncio.CancelledError:
                    break
                data = json.dumps(payload)
                # Emit a named event 'refresh' as expected by the UI
                yield f"event: refresh\ndata: {data}\n\n"
        finally:
            unsubscribe(q)
    return StreamingResponse(event_generator(), media_type='text/event-stream')

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get('/api/data')
def api_data(project_id: int = None):
    return crud.get_data(engine, project_id)

@app.get('/api/stats')
def api_stats(project_id: int = None):
    return crud.get_stats(engine, project_id)

# --- Projects API ---
@app.get('/api/projects', summary="Get all projects")
def api_get_projects():
    """Retrieve a list of all projects in the system."""
    return crud.get_projects(engine)

@app.post('/api/projects', summary="Create a new project")
def api_create_project(payload: ProjectCreate):
    """Create a new project with the provided name and description."""
    return crud.create_project(engine, payload.dict())

@app.delete('/api/projects/{project_id}', summary="Delete a project")
def api_delete_project(project_id: int):
    """Delete a project and all its associated groups and tasks (cascading)."""
    return crud.delete_project(engine, project_id)

@app.put('/api/projects/{project_id}', summary="Update a project")
def api_update_project(project_id: int, payload: ProjectUpdate):
    """Update project details like name, description, or notification settings."""
    return crud.update_project(engine, project_id, payload.dict(exclude_unset=True))

@app.get('/api/settings', summary="Get global settings")
def api_get_settings():
    """Retrieve global application settings."""
    return crud.get_settings(engine)

@app.put('/api/settings', summary="Update global settings")
def api_put_settings(payload: dict):
    """Update global application settings."""
    return crud.set_settings(engine, payload)

@app.post('/api/reorder/tasks', summary="Reorder tasks")
def api_reorder_tasks(payload: ReorderPayload):
    """Update the position and group assignment of multiple tasks."""
    items = [it.dict() for it in payload.items]
    return crud.reorder_tasks(engine, items)

@app.post('/api/reorder/groups', summary="Reorder groups")
def api_reorder_groups(payload: ReorderPayload):
    """Update the position of multiple groups."""
    items = [it.dict() for it in payload.items]
    return crud.reorder_groups(engine, items)

@app.post('/api/tasks', summary="Create a task")
def api_create_task(payload: TaskCreate):
    """Add a new task to a specific group and project."""
    return crud.create_task(engine, payload.dict())

@app.put('/api/tasks/{task_id}', summary="Update a task")
def api_update_task(task_id: str, payload: TaskUpdate):
    """Update task details like title, status, priority, or notes."""
    return crud.update_task(engine, task_id, payload.dict(exclude_unset=True))

@app.delete('/api/tasks/{task_id}', summary="Delete a task")
def api_delete_task(task_id: str):
    """Permanently remove a task from the system."""
    return crud.delete_task(engine, task_id)

@app.post('/api/groups', summary="Create a group")
def api_create_group(payload: GroupCreate):
    """Add a new group (category) to a project."""
    return crud.create_group(engine, payload.dict())

@app.put('/api/groups/{group_id}', summary="Update a group")
def api_update_group(group_id: int, payload: GroupUpdate):
    """Update group details like name, color, or collapsed state."""
    return crud.update_group(engine, group_id, payload.dict(exclude_unset=True))

@app.delete('/api/groups/{group_id}', summary="Delete a group")
def api_delete_group(group_id: int):
    """Remove a group and unassign its tasks."""
    return crud.delete_group(engine, group_id)

# Start static files mount AFTER API routes to avoid shadowing
# Fallback for static files
@app.get('/{file_path:path}', include_in_schema=False)
def serve_static(file_path: str):
    p = os.path.join(UI_DIR, file_path)
    if os.path.isfile(p):
        return FileResponse(p)
    raise HTTPException(status_code=404)

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        try:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
        except Exception:
            pass

