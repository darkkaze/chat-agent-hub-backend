from pydantic import BaseModel, Field
from typing import List


class CreateMenuRequest(BaseModel):
    """Schema for creating a new menu item."""
    icon_svg: str = Field(..., description="SVG icon as string")
    url: str = Field(..., description="URL path for navigation")


class UpdateMenuRequest(BaseModel):
    """Schema for updating menu item."""
    icon_svg: str = Field(None, description="New SVG icon as string")
    url: str = Field(None, description="New URL path for navigation")


class MenuResponse(BaseModel):
    """Schema for menu item responses."""
    id: str = Field(..., description="Menu item ID")
    icon_svg: str = Field(..., description="SVG icon as string")
    url: str = Field(..., description="URL path for navigation")

    model_config = {"from_attributes": True}


class MenuListResponse(BaseModel):
    """Schema for menu list responses."""
    menus: List[MenuResponse]
    total_count: int