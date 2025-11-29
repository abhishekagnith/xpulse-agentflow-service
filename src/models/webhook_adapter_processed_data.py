from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from models.webhook_message_data import WebhookMetadata


class WebhookAdapterProcessedData(BaseModel):
    """
    Model for storing webhook messages after adapter processing (normalization).
    This stores the normalized webhook data in the same metadata/data format that gets passed to user_state_service.
    """
    id: Optional[str] = None  # MongoDB _id
    original_webhook_id: Optional[str] = Field(None, description="Reference to the original webhook message ID")
    original_message_body: Dict[str, Any] = Field(default_factory=dict, description="Original webhook payload before normalization")
    metadata: WebhookMetadata = Field(..., description="Normalized metadata (same format as WebhookMessageData)")
    data: Dict[str, Any] = Field(default_factory=dict, description="Normalized data (same format as WebhookMessageData, contains normalized message structure)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when webhook was processed by adapter")

