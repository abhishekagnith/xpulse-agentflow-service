from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class WebhookMessageData(BaseModel):
    """
    Model for storing webhook messages received from channel services (WhatsApp, Telegram, etc.)
    Matches the WebhookMessageRequest structure with added status field
    """
    id: Optional[str] = None  # MongoDB _id
    sender: str = Field(..., description="User identifier (phone number, user ID, etc.)")
    brand_id: int = Field(..., description="Brand ID for multitenancy")
    user_id: int = Field(..., description="User ID for multitenancy")
    channel_identifier: str = Field(..., description="Channel-specific identifier (WABA ID, Bot ID, etc.)")
    channel_phone_number_id: Optional[str] = Field(None, description="Channel phone number ID (for WhatsApp)")
    message_type: str = Field(..., description="Type of message (text, button, interactive, etc.)")
    message_body: Dict[str, Any] = Field(..., description="Message content/payload")
    channel: str = Field(default="whatsapp", description="Channel name (whatsapp, telegram, sms, etc.)")
    status: str = Field(default="pending", description="Processing status: pending, processed, error")

