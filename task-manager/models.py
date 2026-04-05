from sqlmodel import SQLModel, Field
from typing import Optional

class Project(SQLModel, table=True):
    __tablename__ = 'projects'
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = ""
    description: str = ""
    created_at: Optional[str] = Field(default=None)
    notifications_enabled: bool = Field(default=True)
    bot_chat_id: str = Field(default="")

class Group(SQLModel, table=True):
    __tablename__ = 'groups'
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: Optional[int] = Field(default=None, foreign_key='projects.id')
    name: str = ""
    color: str = '#6366f1'
    position: int = 0
    collapsed: int = 0

class Task(SQLModel, table=True):
    __tablename__ = 'tasks'
    id: Optional[str] = Field(default=None, primary_key=True)
    group_id: Optional[int] = Field(default=None, foreign_key='groups.id')
    project_id: Optional[int] = Field(default=None, foreign_key='projects.id')
    title: str = ""
    notes: str = ""
    status: str = 'pending'
    priority: str = 'medium'
    position: int = 0
    created: Optional[str] = Field(default=None)
    completed_at: Optional[str] = Field(default=None)

class Setting(SQLModel, table=True):
    __tablename__ = 'settings'
    key: Optional[str] = Field(default=None, primary_key=True)
    value: str = ""
