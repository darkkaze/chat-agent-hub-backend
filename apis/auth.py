from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token")
async def login():
    """Login for internal users."""
    pass