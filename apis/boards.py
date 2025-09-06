from fastapi import APIRouter

router = APIRouter(prefix="/boards", tags=["boards"])


@router.get("")
async def list_boards():
    """List all boards."""
    pass


@router.get("/{board_id}")
async def get_board(board_id: str):
    """Get board with all columns and tasks."""
    pass