import sys
import json
import os
import traceback
from sqlmodel import create_engine
import crud

DB_PATH = os.environ.get("TASK_MANAGER_DB", r"C:\ENM Projects\PadelFlow\tools\mcp-dev-remote\tasks.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Global engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

TOOLS = [
    {
        "name": "tasks_pending",
        "description": "List all pending/unresolved tasks for a project. Call this at the START of every session to review what needs doing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "The ID of the project to query (optional, though recommended)"},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "Filter by priority"}
            }
        }
    },
    {
        "name": "tasks_list",
        "description": "List tasks with optional filters. Use to browse all tasks or filter by status/priority.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "The ID of the project"},
                "status": {"type": "string", "enum": ["pending", "in-progress", "done", "blocked"], "description": "Filter by status"},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "Filter by priority"}
            }
        }
    },
    {
        "name": "task_create",
        "description": "Create a new task. Status defaults to 'pending'. ID is auto-generated.",
        "inputSchema": {
            "type": "object",
            "required": ["title", "group_id"],
            "properties": {
                "group_id": {"type": "integer", "description": "ID of the group this task belongs to"},
                "title": {"type": "string", "description": "Task description"},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "Priority level"},
                "notes": {"type": "string", "description": "Additional context or acceptance criteria"}
            }
        }
    },
    {
        "name": "tasks_push",
        "description": "Advances a task to its next logical state: pending -> in-progress -> done. If blocked, push moves it back to pending.",
        "inputSchema": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "string", "description": "Task id to advance"}
            }
        }
    },
    {
        "name": "tasks_block",
        "description": "Blocks an 'in-progress' task. Requires a reason.",
        "inputSchema": {
            "type": "object",
            "required": ["id", "reason"],
            "properties": {
                "id": {"type": "string", "description": "Task id to block"},
                "reason": {"type": "string", "description": "Explanation for the blocker"}
            }
        }
    },
    {
        "name": "groups_list",
        "description": "List all groups for a given project. Needed to get group_id for creating tasks.",
        "inputSchema": {
            "type": "object",
            "required": ["project_id"],
            "properties": {
                "project_id": {"type": "integer", "description": "The ID of the project"}
            }
        }
    },
    {
        "name": "projects_list",
        "description": "List all available projects in the workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

def respond(req_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}) + '\n')
    sys.stdout.flush()

def rpc_error(req_id, code, message):
    if req_id is not None:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}) + '\n')
        sys.stdout.flush()

def handle_tasks_pending(args):
    project_id = args.get("project_id")
    prio = args.get("priority")
    data = crud.get_data(engine, project_id)
    tasks = data.get("tasks", [])
    
    pending = [t for t in tasks if t.get("status") not in ("done", "obsolete")]
    if prio:
        pending = [t for t in pending if t.get("priority") == prio]
        
    return json.dumps(pending, indent=2)

def handle_tasks_list(args):
    project_id = args.get("project_id")
    status = args.get("status")
    prio = args.get("priority")
    
    data = crud.get_data(engine, project_id)
    tasks = data.get("tasks", [])
    
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    if prio:
        tasks = [t for t in tasks if t.get("priority") == prio]
        
    return json.dumps(tasks, indent=2)

def handle_task_create(args):
    if "title" not in args or "group_id" not in args:
        raise ValueError("Missing 'title' or 'group_id' in arguments")
    
    payload = {
        "title": args["title"],
        "group_id": args["group_id"],
        "status": "pending" # Enforced by workflow
    }
    if "priority" in args: payload["priority"] = args["priority"]
    if "notes" in args: payload["notes"] = args["notes"]
    
    res = crud.create_task(engine, payload)
    return json.dumps(res, indent=2)

def handle_tasks_push(args):
    task_id = args.get("id")
    task = crud.get_task(engine, task_id)
    if not task:
        return f"Error: Task {task_id} not found."
    
    current_status = task.status
    next_status = None
    
    if current_status == "pending":
        next_status = "in-progress"
    elif current_status == "in-progress":
        next_status = "done"
    elif current_status == "blocked":
        next_status = "pending"
    else:
        return f"Error: Cannot 'push' task from status '{current_status}'. Allowed only from pending, in-progress or blocked."
        
    res = crud.update_task(engine, task_id, {"status": next_status})
    return f"Task {task_id} pushed from {current_status} to {next_status}.\n\n" + json.dumps(res, indent=2)

def handle_tasks_block(args):
    task_id = args.get("id")
    reason = args.get("reason")
    if not reason:
        return "Error: A reason is required to block a task."
        
    task = crud.get_task(engine, task_id)
    if not task:
        return f"Error: Task {task_id} not found."
        
    if task.status != "in-progress":
        return f"Error: Only 'in-progress' tasks can be blocked. Current status: {task.status}"
        
    existing_notes = task.notes or ""
    new_notes = existing_notes + f"\n\n[BLOCKER]: {reason}"
    res = crud.update_task(engine, task_id, {"status": "blocked", "notes": new_notes})
    return f"Task {task_id} blocked.\n\nReason: {reason}\n\n" + json.dumps(res, indent=2)

def handle_groups_list(args):
    project_id = args.get("project_id")
    data = crud.get_data(engine, project_id)
    return json.dumps(data.get("groups", []), indent=2)

def handle_projects_list(args):
    projects = crud.get_projects(engine)
    return json.dumps(projects, indent=2)

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
            
        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {})
        
        if method == "initialize":
            respond(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mcp-fastapi-backend", "version": "1.1.0"}
            })
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            respond(req_id, {"tools": TOOLS})
        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})
            try:
                text_result = ""
                if name == "tasks_pending": text_result = handle_tasks_pending(args)
                elif name == "tasks_list": text_result = handle_tasks_list(args)
                elif name == "task_create": text_result = handle_task_create(args)
                elif name == "tasks_push": text_result = handle_tasks_push(args)
                elif name == "tasks_block": text_result = handle_tasks_block(args)
                elif name == "groups_list": text_result = handle_groups_list(args)
                elif name == "projects_list": text_result = handle_projects_list(args)
                else:
                    rpc_error(req_id, -32601, f"Unknown tool: {name}")
                    continue
                
                respond(req_id, {
                    "content": [{"type": "text", "text": text_result}]
                })
            except Exception as e:
                respond(req_id, {"content": [{"type": "text", "text": f"Error: {str(e)}\n\n{traceback.format_exc()}"}]})
        else:
            rpc_error(req_id, -32601, f"Method not found: {method}")

if __name__ == "__main__":
    main()
