from pydantic import BaseModel, Field
from typing import List, Optional


class CreateBoardRequest(BaseModel):
    """Schema for creating a new board."""
    name: str = Field(..., description="Board name")
    columns: List[str] = Field(default_factory=list, description="List of column names for the Kanban board")


class BoardResponse(BaseModel):
    """Schema for board responses."""
    id: str = Field(..., description="Board ID")
    name: str = Field(..., description="Board name")
    columns: List[str] = Field(..., description="List of column names")

    model_config = {"from_attributes": True}  # Allows Pydantic to work with SQLModel objects