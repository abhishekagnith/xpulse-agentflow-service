from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from models.validation_data import ValidationData
from models.user_detail import UserDetail

class UserData(BaseModel):
    id: Optional[str] = None  # MongoDB _id
    user_detail: UserDetail = Field(..., description="User detail with channel-specific identifiers")
    brand_id: int
    user_id: int  # Internal user ID (brand owner)
    lead_id: Optional[str] = Field(None, description="Lead ID from lead management service")
    channel: str = Field(default="whatsapp", description="Channel name (whatsapp, telegram, sms, gmail, etc.)")
    channel_account_id: Optional[str] = None  # Channel account ID (phone number ID for WhatsApp, account ID for other channels)
    is_in_automation: bool = False  # Whether user is currently in a flow automation
    current_flow_id: Optional[str] = None  # MongoDB _id of the active flow
    last_flow_id: Optional[str] = None  # MongoDB _id of the last flow user was in
    current_node_id: Optional[str] = None  # Current node ID in the flow
    switch: bool = False  # Whether user is in switch state
    switch_flow_id: Optional[str] = None  # Flow ID when user is in switch state
    validation: ValidationData = Field(default_factory=ValidationData, description="Validation state for user responses")
    delay_node_data: Optional[Dict[str, Any]] = Field(None, description="Complete delay node object when user is waiting on a delay node")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

