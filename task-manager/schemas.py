from typing import Optional, List, Union
from pydantic import BaseModel

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    bot_chat_id: Optional[str] = None

class TaskCreate(BaseModel):
    group_id: Optional[int] = None
    project_id: Optional[int] = None
    title: str
    priority: Optional[str] = "medium"
    notes: Optional[str] = ""

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    group_id: Optional[int] = None
    position: Optional[int] = None

class GroupCreate(BaseModel):
    project_id: Optional[int] = None
    name: str
    color: Optional[str] = "#6366f1"

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    position: Optional[int] = None
    collapsed: Optional[int] = None

class ReorderItem(BaseModel):
    id: Union[str, int]
    position: int
    group_id: Optional[int] = None

class ReorderPayload(BaseModel):
    items: List[ReorderItem]
