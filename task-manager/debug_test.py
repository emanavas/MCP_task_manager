"""Quick startup test - simulates what FastAPI does on /api/data"""
import os
os.environ["TASK_MANAGER_DB"] = r"c:\ENM Projects\PadelFlow\tools\mcp-dev-remote\tasks.db"
os.environ["TASK_MANAGER_UI_DIR"] = r"c:\ENM Projects\PadelFlow\tools\mcp-dev-remote\ui\public"
os.environ["TASK_MANAGER_API_KEY"] = "dev_local_key"

import traceback

try:
    from sqlmodel import SQLModel, create_engine
    from models import Task, Group, Setting, Project
    import crud

    DB_PATH = os.environ["TASK_MANAGER_DB"]
    engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    print("=== Calling crud.get_data() ===")
    result = crud.get_data(engine)
    print("Keys:", list(result.keys()))
    print("Projects:", result["projects"])
    print("Groups count:", len(result["groups"]))
    print("Tasks count:", len(result["tasks"]))
    print("SUCCESS!")
except Exception as e:
    print("ERROR:", e)
    traceback.print_exc()
