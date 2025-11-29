from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class NodeDetailData(BaseModel):
    """
    Model for node details stored in node_details collection
    """
    id: Optional[str] = None
    node_id: str  # e.g., "trigger-keyword", "message", "question", etc.
    node_name: str  # e.g., "Keyword Trigger", "Send A Message", etc.
    category: str  # "Trigger", "Action", "Condition", "Delay"
    user_input_required: bool  # Whether this node requires user input
    is_internal: bool = Field(default=False, description="Whether this is an internal node (condition, delay) or external")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


