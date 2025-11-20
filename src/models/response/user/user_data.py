from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from enum import Enum
from datetime import datetime

class PermissionType(Enum):
    BANNER_IMAGE_GENERATION = "banner_image_generation"
    SOCIAL_MEDIA_IMAGE_GENERATION = "social_media_image_generation"

class Permission(BaseModel):
    name: Literal["form", "social"]
    privileges: List[str]

class UserData(BaseModel):
    user_id: Optional[int] = None
    email: str
    password: str
    is_active: bool
    brand_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    permissions: Optional[List[Permission]] = None
    