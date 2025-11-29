from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class DelayData(BaseModel):
    """
    Model for storing delay information when a delay node is processed.
    Used by background scheduler to trigger delay_complete webhooks.
    """
    id: Optional[str] = None  # MongoDB _id
    user_identifier: str = Field(..., description="User identifier (phone number, email, etc.)")
    brand_id: int = Field(..., description="Brand ID for multitenancy")
    flow_id: str = Field(..., description="Flow ID where delay node exists")
    delay_node_id: str = Field(..., description="Delay node ID")
    delay_node_data: Dict[str, Any] = Field(..., description="Complete delay node object")
    delay_duration: int = Field(..., description="Delay duration value")
    delay_unit: str = Field(..., description="Delay unit (seconds, minutes, hours, days)")
    wait_time_seconds: int = Field(..., description="Total wait time in seconds")
    delay_started_at: datetime = Field(default_factory=datetime.utcnow, description="When delay started")
    delay_completes_at: datetime = Field(..., description="When delay should complete (delay_started_at + wait_time_seconds)")
    processed: bool = Field(default=False, description="Whether delay_complete webhook has been sent")
    channel: str = Field(default="whatsapp", description="Channel name")
    channel_account_id: Optional[str] = Field(None, description="Channel account ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when delay record was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when delay record was last updated")

