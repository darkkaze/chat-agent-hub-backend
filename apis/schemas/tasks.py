from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CreateTaskRequest(BaseModel):
    """Schema for creating a new task."""
    title: str = Field(..., description="Task title")
    description: str = Field(default="", description="Task description")
    column: str = Field(..., description="Column name where task is placed")
    chat_id: Optional[str] = Field(default=None, description="Associated chat ID (optional)")


class UpdateTaskRequest(BaseModel):
    """Schema for updating a task."""
    title: Optional[str] = Field(default=None, description="New task title")
    description: Optional[str] = Field(default=None, description="New task description")
    column: Optional[str] = Field(default=None, description="New column name")
    chat_id: Optional[str] = Field(default=None, description="New associated chat ID")


class CreateTaskNoteRequest(BaseModel):
    """Schema for adding a note to a task."""
    content: str = Field(..., description="Note content")


class CreateTaskDocumentRequest(BaseModel):
    """Schema for attaching a document to a task."""
    file_url: str = Field(..., description="URL or path to the file")
    file_name: str = Field(..., description="Name of the file")
    mime_type: str = Field(..., description="MIME type of the file")


# Response Schemas
class NoteResponse(BaseModel):
    """Schema for note responses."""
    id: str = Field(..., description="Note ID")
    content: str = Field(..., description="Note content")
    created_at: datetime = Field(..., description="Creation timestamp")
    created_by_user_id: str = Field(..., description="User who created the note")

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    """Schema for document responses."""
    id: str = Field(..., description="Document ID")
    file_url: str = Field(..., description="URL or path to the file")
    file_name: str = Field(..., description="Name of the file")
    mime_type: str = Field(..., description="MIME type of the file")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    uploaded_by_user_id: str = Field(..., description="User who uploaded the document")

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    """Schema for task responses."""
    id: str = Field(..., description="Task ID")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    column: str = Field(..., description="Column name")
    chat_id: Optional[str] = Field(default=None, description="Associated chat ID")

    model_config = {"from_attributes": True}


class TaskDetailResponse(BaseModel):
    """Schema for detailed task responses including notes and documents."""
    id: str = Field(..., description="Task ID")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    column: str = Field(..., description="Column name")
    chat_id: Optional[str] = Field(default=None, description="Associated chat ID")
    notes: List[NoteResponse] = Field(default_factory=list, description="Associated notes")
    documents: List[DocumentResponse] = Field(default_factory=list, description="Associated documents")

    model_config = {"from_attributes": True}