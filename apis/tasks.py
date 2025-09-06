from fastapi import APIRouter

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("")
async def create_task():
    """Create new task (can associate to chat in body)."""
    pass


@router.put("/{task_id}")
async def update_task(task_id: str):
    """Update task (move column, change description, etc.)."""
    pass


@router.post("/{task_id}/notes")
async def add_task_note(task_id: str):
    """Add note to task."""
    pass


@router.post("/{task_id}/documents")
async def attach_document_to_task(task_id: str):
    """Attach document to task."""
    pass