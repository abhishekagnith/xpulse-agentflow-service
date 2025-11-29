from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class WebhookMessageRequest(BaseModel):
    """
    Request model for incoming webhook messages from channel services.
    This model is channel-agnostic and can be used by WhatsApp, Telegram, SMS, etc.
    Also supports system webhooks (delay_complete, scheduled_trigger).
    For system webhooks, use sender="system" and channel="system".
    """
    sender: str = Field(..., description="User identifier (phone number, user ID, etc.) or 'system' for system webhooks")
    brand_id: int = Field(..., description="Brand ID for multitenancy")
    user_id: int = Field(..., description="User ID for multitenancy")
    channel_identifier: Optional[str] = Field(None, description="Channel-specific identifier (WABA ID, Bot ID, etc.). None for system webhooks")
    channel_phone_number_id: Optional[str] = Field(None, description="Channel phone number ID (for WhatsApp)")
    message_type: str = Field(..., description="Type of message (text, button, interactive, delay_complete, scheduled_trigger, etc.)")
    message_body: Dict[str, Any] = Field(..., description="Message content/payload or system event data")
    channel: str = Field(default="whatsapp", description="Channel name (whatsapp, telegram, sms, system, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "sender": "+1234567890",
                "brand_id": 123,
                "user_id": 456,
                "channel_identifier": "waba_id_12345",
                "channel_phone_number_id": "phone_number_id_67890",
                "message_type": "text",
                "message_body": {
                    "type": "text",
                    "text": {"body": "Hello"}
                },
                "channel": "whatsapp"
            }
        }

