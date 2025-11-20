from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FlowUserContext(BaseModel):
    """
    Model for storing user's flow context data separately
    Each record stores one variable-value pair per flow
    """
    id: Optional[str] = Field(default=None, alias="_id")
    user_phone_number: str
    brand_id: int
    flow_id: str
    variable_name: str  # The @variable name (e.g., "@user_name")
    variable_value: str  # The user's answer
    node_id: Optional[str] = None  # Which node collected this data
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

