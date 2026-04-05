from sqlmodel import Session, select, text
from models import Task, Group, Setting, Project
from typing import List, Dict, Any
import uuid

def _notify():
    from events import push_event
    push_event({"type": "refresh"})

def get_data(engine, project_id: int = None):
    with Session(engine) as s:
        stmt_g = select(Group)
        if project_id:
            stmt_g = stmt_g.where(Group.project_id == project_id)
        groups = s.exec(stmt_g.order_by(Group.position)).all()
        
        group_ids = [g.id for g in groups]
        stmt_t = select(Task)
        if group_ids:
            stmt_t = stmt_t.where(Task.group_id.in_(group_ids))
        elif project_id:
             # If no groups but project_id provided, return nothing or tasks with no group? 
             # Usually tasks must belong to a group in this UI.
             stmt_t = stmt_t.where(text("1=0"))
             
        tasks = s.exec(stmt_t.order_by(Task.position)).all()
        projects = s.exec(select(Project)).all()
        return {
            "projects": [p.dict() for p in projects],
            "groups": [g.dict() for g in groups], 
            "tasks": [t.dict() for t in tasks]
        }

def get_projects(engine):
    with Session(engine) as s:
        items = s.exec(select(Project)).all()
        return [it.dict() for it in items]

def create_project(engine, payload):
    p = Project(**payload)
    if not p.created_at:
        from datetime import datetime
        p.created_at = datetime.utcnow().isoformat()
    with Session(engine) as s:
        s.add(p)
        s.commit()
        s.refresh(p)
        _notify()
        return p.dict()

def delete_project(engine, project_id):
    with Session(engine) as s:
        p = s.get(Project, project_id)
        if not p: return {"error": "not found"}
        # Delete tasks belonging to project's groups
        groups = s.exec(select(Group).where(Group.project_id == project_id)).all()
        for g in groups:
            tasks = s.exec(select(Task).where(Task.group_id == g.id)).all()
            for t in tasks:
                s.delete(t)
            s.delete(g)
        s.delete(p)
        s.commit()
        _notify()
        return {"ok": True}


def update_project(engine, project_id, payload):
    with Session(engine) as s:
        p = s.get(Project, project_id)
        if not p: return {"error": "not found"}
        for k,v in payload.items():
            setattr(p, k, v)
        s.add(p)
        s.commit()
        s.refresh(p)
        _notify()
        return p.dict()

def create_task(engine, payload: Dict[str,Any]):
    t = Task(**payload)
    if not getattr(t, 'id', None):
        t.id = f"task-{int(uuid.uuid4().int>>64)}"
    if not t.created:
        from datetime import datetime
        t.created = datetime.utcnow().isoformat()
    with Session(engine) as s:
        s.add(t)
        s.commit()
        s.refresh(t)
        _notify()
        return t.dict()

def get_task(engine, task_id):
    with Session(engine) as s:
        return s.get(Task, task_id)

def update_task(engine, task_id, payload):
    with Session(engine) as s:
        t = s.get(Task, task_id)
        if not t:
            return {"error": "not found"}
        for k,v in payload.items():
            setattr(t, k, v)
        # set completed_at if status changed to done
        if payload.get('status') == 'done' and not t.completed_at:
            from datetime import datetime
            t.completed_at = datetime.utcnow().isoformat()
        s.add(t)
        s.commit()
        s.refresh(t)
        _notify()
        return t.dict()

def delete_task(engine, task_id):
    with Session(engine) as s:
        t = s.get(Task, task_id)
        if not t:
            return {"error": "not found"}
        s.delete(t)
        s.commit()
        _notify()
        return {"ok": True}

# Groups CRUD
def create_group(engine, payload):
    g = Group(**payload)
    with Session(engine) as s:
        s.add(g)
        s.commit()
        s.refresh(g)
        _notify()
        return g.dict()

def update_group(engine, group_id, payload):
    with Session(engine) as s:
        g = s.get(Group, group_id)
        if not g:
            return {"error": "not found"}
        for k,v in payload.items(): setattr(g,k,v)
        s.add(g); s.commit(); s.refresh(g)
        _notify()
        return g.dict()

def delete_group(engine, group_id):
    with Session(engine) as s:
        g = s.get(Group, group_id)
        if not g: return {"error": "not found"}
        # set tasks.group_id = NULL
        s.exec(text("UPDATE tasks SET group_id = NULL WHERE group_id = :gid"), {"gid": group_id})
        s.delete(g); s.commit()
        _notify()
        return {"ok": True}

# Stats
def get_stats(engine, project_id: int = None):
    with Session(engine) as s:
        stmt = select(Task)
        if project_id:
            groups = s.exec(select(Group).where(Group.project_id == project_id)).all()
            gids = [g.id for g in groups]
            if not gids: return {"total": 0, "done": 0, "pending": 0, "blocked": 0, "inProgress": 0, "high": 0, "progressPct": 0}
            stmt = stmt.where(Task.group_id.in_(gids))
            
        total = s.exec(stmt).all()
        total_n = len(total)
        done = len([t for t in total if t.status == 'done'])
        pending = len([t for t in total if t.status == 'pending'])
        blocked = len([t for t in total if t.status == 'blocked'])
        in_progress = len([t for t in total if t.status not in ('done','pending', 'blocked')])
        high = len([t for t in total if t.priority == 'high'])
        pct = int((done/total_n)*100) if total_n>0 else 0
        return {
            "total": total_n, 
            "done": done, 
            "pending": pending, 
            "blocked": blocked, 
            "inProgress": in_progress, 
            "high": high, 
            "progressPct": pct
        }

# Settings
def get_settings(engine):
    with Session(engine) as s:
        rows = s.exec(select(Setting)).all()
        return {r.key: r.value for r in rows}

def set_settings(engine, payload: Dict[str,Any]):
    with Session(engine) as s:
        for k,v in payload.items():
            existing = s.get(Setting, k)
            if existing:
                existing.value = v
                s.add(existing)
            else:
                s.add(Setting(key=k, value=v))
        s.commit()
        _notify()
        return {"ok": True}

# Reorder helpers
def reorder_tasks(engine, items: List[Dict[str,Any]]):
    # items: [{id, group_id, position}, ...]
    with Session(engine) as s:
        for it in items:
            t = s.get(Task, it['id'])
            if not t: continue
            t.group_id = it.get('group_id')
            t.position = int(it.get('position', 0))
            s.add(t)
        s.commit()
        _notify()
        return {"ok": True}

def reorder_groups(engine, items: List[Dict[str,Any]]):
    with Session(engine) as s:
        for it in items:
            g = s.get(Group, int(it['id']))
            if not g: continue
            g.position = int(it.get('position', 0))
            s.add(g)
        s.commit()
        _notify()
        return {"ok": True}

