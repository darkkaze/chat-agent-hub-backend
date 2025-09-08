from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON
from typing import Optional, List
from .helper import id_generator


class Board(SQLModel, table=True):
    """Kanban-style board to organize work."""
    id: str = Field(default_factory=id_generator('board', 10), primary_key=True)
    name: str = Field(index=True)
    columns: List[str] = Field(default_factory=list, sa_column=Column(JSON))


class Task(SQLModel, table=True):
    """Work unit within a board, which can be linked to a chat."""
    id: str = Field(default_factory=id_generator('task', 10), primary_key=True)
    column: str = Field(index=True)
    chat_id: Optional[str] = Field(default=None, foreign_key="chat.id", index=True)
    title: str
    description: str = Field(default="")