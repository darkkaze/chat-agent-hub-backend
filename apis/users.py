from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_current_user():
    """Get authenticated user information."""
    pass


@router.get("")
async def list_users():
    """List all users (Admins only)."""
    pass


@router.post("")
async def create_user():
    """Create new user (Admins only)."""
    pass