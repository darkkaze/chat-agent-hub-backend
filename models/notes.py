from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from .helper import id_generator


class Note(SQLModel, table=True):
    """Note information without ownership context."""
    id: str = Field(default_factory=id_generator('note', 10), primary_key=True)
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    created_by_user_id: str = Field(foreign_key="user.id", index=True)


class ChatNote(SQLModel, table=True):
    """Links a Note with a Chat."""
    chat_id: str = Field(foreign_key="chat.id", primary_key=True)
    note_id: str = Field(foreign_key="note.id", primary_key=True)


class TaskNote(SQLModel, table=True):
    """Links a Note with a Task."""
    task_id: str = Field(foreign_key="task.id", primary_key=True)
    note_id: str = Field(foreign_key="note.id", primary_key=True)