from typing import Optional
from pydantic import BaseModel, Field


class WebhookMessageResponse(BaseModel):
    """
    Response model for webhook message processing.
    Indicates whether automation was triggered and current state.
    """
    status: str = Field(..., description="Processing status (success, error, no_automation)")
    message: str = Field(..., description="Human-readable message")
    automation_triggered: bool = Field(default=False, description="Whether flow automation was triggered")
    flow_id: Optional[str] = Field(None, description="Flow ID if automation was triggered")
    current_node_id: Optional[str] = Field(None, description="Current node ID if automation is active")
    error_details: Optional[str] = Field(None, description="Error details if status is error")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Automation processed successfully",
                "automation_triggered": True,
                "flow_id": "flow_123",
                "current_node_id": "node_456",
                "error_details": None
            }
        }

