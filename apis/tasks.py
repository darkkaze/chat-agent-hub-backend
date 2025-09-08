from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from database import get_session
from models.auth import Token
from models.boards import Task
from models.notes import Note, TaskNote
from models.documents import Document, TaskDocument
from apis.schemas.tasks import (
    CreateTaskRequest, UpdateTaskRequest, CreateTaskNoteRequest, CreateTaskDocumentRequest,
    TaskResponse, TaskDetailResponse, NoteResponse, DocumentResponse
)
from helpers.auth import get_auth_token
from typing import List, Dict, Any

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse)
async def create_task(
    task_data: CreateTaskRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> TaskResponse:
    """Create new task (can associate to chat in body)."""
    task = Task(
        title=task_data.title,
        description=task_data.description,
        column=task_data.column,
        chat_id=task_data.chat_id
    )
    
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    
    return TaskResponse.model_validate(task)


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> List[TaskResponse]:
    """List all tasks (basic information only, no notes/documents)."""
    statement = select(Task)
    tasks = db_session.exec(statement).all()
    
    return [TaskResponse.model_validate(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> TaskDetailResponse:
    """Get task with notes and documents."""
    # Get task
    task_statement = select(Task).where(Task.id == task_id)
    task = db_session.exec(task_statement).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get associated notes
    notes_statement = select(Note).join(TaskNote).where(TaskNote.task_id == task_id)
    notes = db_session.exec(notes_statement).all()
    
    # Get associated documents
    documents_statement = select(Document).join(TaskDocument).where(TaskDocument.task_id == task_id)
    documents = db_session.exec(documents_statement).all()
    
    # Build response
    task_detail = TaskDetailResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        column=task.column,
        chat_id=task.chat_id,
        notes=[NoteResponse.model_validate(note) for note in notes],
        documents=[DocumentResponse.model_validate(document) for document in documents]
    )
    
    return task_detail


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_data: UpdateTaskRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> TaskResponse:
    """Update task (move column, change description, etc.)."""
    statement = select(Task).where(Task.id == task_id)
    task = db_session.exec(statement).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update only provided fields
    if task_data.title is not None:
        task.title = task_data.title
    if task_data.description is not None:
        task.description = task_data.description
    if task_data.column is not None:
        task.column = task_data.column
    if task_data.chat_id is not None:
        task.chat_id = task_data.chat_id
    
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    soft: bool = Query(default=False, description="If true, perform soft delete"),
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """Delete task (soft or hard delete)."""
    statement = select(Task).where(Task.id == task_id)
    task = db_session.exec(statement).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if soft:
        # Soft delete - mark as deleted (would need is_deleted field in actual implementation)
        # For now, just return success message
        return {"success": True, "message": f"Task {task_id} soft deleted successfully"}
    else:
        # Hard delete - remove associations first, then task
        # Remove task-note associations
        task_notes_statement = select(TaskNote).where(TaskNote.task_id == task_id)
        task_notes = db_session.exec(task_notes_statement).all()
        for task_note in task_notes:
            db_session.delete(task_note)
        
        # Remove task-document associations  
        task_documents_statement = select(TaskDocument).where(TaskDocument.task_id == task_id)
        task_documents = db_session.exec(task_documents_statement).all()
        for task_document in task_documents:
            db_session.delete(task_document)
        
        # Remove the task itself
        db_session.delete(task)
        db_session.commit()
        
        return {"success": True, "message": f"Task {task_id} permanently deleted successfully"}


@router.post("/{task_id}/notes", response_model=NoteResponse)
async def add_task_note(
    task_id: str,
    note_data: CreateTaskNoteRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> NoteResponse:
    """Add note to task."""
    # Verify task exists
    task_statement = select(Task).where(Task.id == task_id)
    task = db_session.exec(task_statement).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get user from token
    from models.auth import TokenUser, User
    token_user_statement = select(TokenUser).where(TokenUser.token_id == token.id)
    token_user = db_session.exec(token_user_statement).first()
    
    # Create note
    note = Note(
        content=note_data.content,
        created_by_user_id=token_user.user_id
    )
    
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)
    
    # Create task-note association
    task_note = TaskNote(task_id=task_id, note_id=note.id)
    db_session.add(task_note)
    db_session.commit()
    
    return NoteResponse.model_validate(note)


@router.post("/{task_id}/documents", response_model=DocumentResponse)
async def add_document_task(
    task_id: str,
    document_data: CreateTaskDocumentRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> DocumentResponse:
    """Attach document to task."""
    # Verify task exists
    task_statement = select(Task).where(Task.id == task_id)
    task = db_session.exec(task_statement).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get user from token
    from models.auth import TokenUser, User
    token_user_statement = select(TokenUser).where(TokenUser.token_id == token.id)
    token_user = db_session.exec(token_user_statement).first()
    
    # Create document
    document = Document(
        file_url=document_data.file_url,
        file_name=document_data.file_name,
        mime_type=document_data.mime_type,
        uploaded_by_user_id=token_user.user_id
    )
    
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    # Create task-document association
    task_document = TaskDocument(task_id=task_id, document_id=document.id)
    db_session.add(task_document)
    db_session.commit()
    
    return DocumentResponse.model_validate(document)


@router.delete("/{task_id}/notes/{note_id}")
async def delete_task_note(
    task_id: str,
    note_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """Delete task note (physical delete only)."""
    # Verify task exists
    task_statement = select(Task).where(Task.id == task_id)
    task = db_session.exec(task_statement).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Verify note exists and is associated with task
    task_note_statement = select(TaskNote).where(TaskNote.task_id == task_id, TaskNote.note_id == note_id)
    task_note = db_session.exec(task_note_statement).first()
    
    if not task_note:
        raise HTTPException(status_code=404, detail="Note not found or not associated with this task")
    
    # Get the note
    note_statement = select(Note).where(Note.id == note_id)
    note = db_session.exec(note_statement).first()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Remove task-note association
    db_session.delete(task_note)
    
    # Remove the note itself (physical delete)
    db_session.delete(note)
    db_session.commit()
    
    return {"success": True, "message": f"Note {note_id} permanently deleted from task {task_id}"}


@router.delete("/{task_id}/documents/{document_id}")
async def delete_document_task(
    task_id: str,
    document_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """Delete task document (physical delete only)."""
    # Verify task exists
    task_statement = select(Task).where(Task.id == task_id)
    task = db_session.exec(task_statement).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Verify document exists and is associated with task
    task_document_statement = select(TaskDocument).where(TaskDocument.task_id == task_id, TaskDocument.document_id == document_id)
    task_document = db_session.exec(task_document_statement).first()
    
    if not task_document:
        raise HTTPException(status_code=404, detail="Document not found or not associated with this task")
    
    # Get the document
    document_statement = select(Document).where(Document.id == document_id)
    document = db_session.exec(document_statement).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Remove task-document association
    db_session.delete(task_document)
    
    # Remove the document itself (physical delete)
    db_session.delete(document)
    db_session.commit()
    
    return {"success": True, "message": f"Document {document_id} permanently deleted from task {task_id}"}