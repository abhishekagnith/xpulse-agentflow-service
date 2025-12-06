from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class EmailSettings(BaseModel):
    """
    Email settings configuration for flow nodes
    """
    source_email: str = Field(..., description="Source email address for sending emails")


class FlowSettingsData(BaseModel):
    """
    Model for storing flow settings/configuration for specific nodes in flows.
    Used to store channel-specific settings like email source addresses.
    """
    id: Optional[str] = None  # MongoDB _id
    flow_id: str = Field(..., description="Flow ID")
    node_id: str = Field(..., description="Node ID within the flow")
    email: Optional[EmailSettings] = Field(None, description="Email settings configuration")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when settings were created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when settings were last updated")

