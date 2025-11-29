from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class WebhookMetadata(BaseModel):
    """
    Metadata about the webhook message - system and processing information
    """
    sender: str = Field(..., description="User identifier (phone number, user ID, etc.) or 'system' for system webhooks")
    brand_id: int = Field(..., description="Brand ID for multitenancy")
    user_id: int = Field(..., description="User ID for multitenancy")
    channel_identifier: Optional[str] = Field(None, description="Channel-specific identifier (WABA ID, Bot ID, etc.). None for system webhooks")
    channel: str = Field(default="whatsapp", description="Channel name (whatsapp, telegram, sms, system, etc.)")
    status: str = Field(default="pending", description="Processing status: pending, processed, error")
    message_type: str = Field(..., description="Type of message (text, button, interactive, delay_complete, scheduled_trigger, etc.)")


class WebhookMessageData(BaseModel):
    """
    Model for storing webhook messages received from channel services (WhatsApp, Telegram, etc.)
    Structured into metadata (system info) and data (webhook payload)
    """
    id: Optional[str] = None  # MongoDB _id
    metadata: WebhookMetadata = Field(..., description="Metadata about the webhook (system and processing info)")
    data: Dict[str, Any] = Field(default_factory=dict, description="Webhook data payload (message content, event data, etc.)")

