from pydantic import BaseModel, Field
from typing import List


class CreateMenuRequest(BaseModel):
    """Schema for creating a new menu item."""
    name: str = Field(..., description="Display name for menu item")
    icon: str = Field(..., description="MDI string name")
    url: str = Field(..., description="URL path for navigation")


class UpdateMenuRequest(BaseModel):
    """Schema for updating menu item."""
    name: str = Field(None, description="New display name for menu item")
    icon: str = Field(None, description="New MDI string name")
    url: str = Field(None, description="New URL path for navigation")


class MenuResponse(BaseModel):
    """Schema for menu item responses."""
    id: str = Field(..., description="Menu item ID")
    name: str = Field(..., description="Display name for menu item")
    icon: str = Field(..., description="MDI string name")
    url: str = Field(..., description="URL path for navigation")

    model_config = {"from_attributes": True}


class MenuListResponse(BaseModel):
    """Schema for menu list responses."""
    menus: List[MenuResponse]
    total_count: int