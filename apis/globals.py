"""
Global Configuration API

Exposes global application configuration from environment variables
available to the frontend.
"""

import os
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/globals", tags=["globals"])


class GlobalsResponse(BaseModel):
    """Global application configuration response."""
    frontend_project_name: str


@router.get("/", response_model=GlobalsResponse)
async def get_globals() -> GlobalsResponse:
    """Get global application configuration from environment variables."""
    return GlobalsResponse(
        frontend_project_name=os.getenv("FRONTEND_PROJECT_NAME", "Agent Hub")
    )
