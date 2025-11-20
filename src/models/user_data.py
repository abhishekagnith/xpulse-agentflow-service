from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class UserData(BaseModel):
    id: Optional[str] = None  # MongoDB _id
    user_phone_number: str  # User identifier (phone number, user ID, etc.)
    brand_id: int
    user_id: int  # Internal user ID (brand owner)
    channel: str = Field(default="whatsapp", description="Channel name (whatsapp, telegram, sms, etc.)")
    channel_identifier: Optional[str] = None  # Channel-specific identifier (WABA ID, Bot ID, etc.)
    phone_number_id: Optional[str] = None  # Phone number ID associated with this user
    is_in_automation: bool = False  # Whether user is currently in a flow automation
    current_flow_id: Optional[str] = None  # MongoDB _id of the active flow
    last_flow_id: Optional[str] = None  # MongoDB _id of the last flow user was in
    current_node_id: Optional[str] = None  # Current node ID in the flow
    switch: bool = False  # Whether user is in switch state
    switch_flow_id: Optional[str] = None  # Flow ID when user is in switch state
    validation_failed: bool = False  # Whether last validation failed
    validation_failure_count: int = 0  # Count of consecutive validation failures
    validation_failure_message: Optional[str] = None  # Last validation failure message
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

