from sqlmodel import SQLModel, Field
from datetime import datetime
from .helper import id_generator


class Document(SQLModel, table=True):
    """File information without ownership context."""
    id: str = Field(default_factory=id_generator('document', 10), primary_key=True)
    file_url: str
    file_name: str = Field(index=True)
    mime_type: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    uploaded_by_user_id: str = Field(foreign_key="user.id", index=True)


class ChatDocument(SQLModel, table=True):
    """Links a Document with a Chat."""
    chat_id: str = Field(foreign_key="chat.id", primary_key=True)
    document_id: str = Field(foreign_key="document.id", primary_key=True)


class TaskDocument(SQLModel, table=True):
    """Links a Document with a Task."""
    task_id: str = Field(foreign_key="task.id", primary_key=True)
    document_id: str = Field(foreign_key="document.id", primary_key=True)