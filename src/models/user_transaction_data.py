from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class UserTransactionData(BaseModel):
    """
    Model for storing user transaction data.
    Tracks node processing transactions for analytics and auditing.
    """
    id: Optional[str] = None  # MongoDB _id
    node_id: str = Field(..., description="Node ID that was processed")
    flow_id: str = Field(..., description="Flow ID where the node exists")
    user_detail: Dict[str, Any] = Field(..., description="User detail object with channel-specific identifiers")
    channel: str = Field(..., description="Channel name (whatsapp, telegram, sms, gmail, etc.)")
    channel_identifier_id: Optional[str] = Field(None, description="Channel account ID (WABA ID, Bot ID, etc.)")
    processed_status: str = Field(default="pending", description="Processing status: pending, success, error")
    node_type: Optional[str] = Field(None, description="Type of node (condition, delay, message, question, etc.)")
    processed_value: Optional[Any] = Field(None, description="Processed value from node (e.g., yes/no node ID for condition)")
    node_data: Optional[Dict[str, Any]] = Field(None, description="Complete node data dictionary")
    user_identifier: Optional[str] = Field(None, description="User identifier (phone number, email, etc.)")
    brand_id: Optional[int] = Field(None, description="Brand ID for multitenancy")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when transaction was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when transaction was last updated")

