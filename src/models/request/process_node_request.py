from pydantic import BaseModel
from typing import Optional, Dict, Any


class ProcessNodeRequest(BaseModel):
    """
    Request model for processing a flow node
    This will be sent from flow_service to channel services (WhatsApp, Email, SMS, etc.)
    """
    # Flow information
    flow_id: str
    current_node_id: str
    next_node_id: str
    next_node_data: Dict[str, Any]  # Complete node JSON
    
    # User information
    user_identifier: str  # Phone number for WhatsApp, email for Email, etc.
    brand_id: int
    user_id: int
    
    # Channel information
    channel: str  # "whatsapp", "email", "sms", "facebook", etc.
    
    # Node processing options
    fallback_message: Optional[str] = None  # Message to send before node
    user_state: Optional[Dict[str, Any]] = None  # Complete user state from DB
    
    class Config:
        json_schema_extra = {
            "example": {
                "flow_id": "flow_123",
                "current_node_id": "node_1",
                "next_node_id": "node_2",
                "next_node_data": {
                    "id": "node_2",
                    "type": "message",
                    "flowReplies": [
                        {
                            "flowReplyType": "text",
                            "data": "Welcome to our service!",
                            "caption": ""
                        }
                    ]
                },
                "user_identifier": "1234567890",
                "brand_id": 1,
                "user_id": 1,
                "channel": "whatsapp",
                "fallback_message": None,
                "user_state": {
                    "user_phone_number": "1234567890",
                    "is_in_automation": True,
                    "current_flow_id": "flow_123",
                    "current_node_id": "node_1",
                    "validation_failure_count": 0
                }
            }
        }

