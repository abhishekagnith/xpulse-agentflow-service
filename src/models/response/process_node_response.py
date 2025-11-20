from pydantic import BaseModel
from typing import Optional


class ProcessNodeResponse(BaseModel):
    """
    Response model from channel services after processing a node
    """
    status: str  # "success", "error", "validation_exit", "validation_retry"
    message: str  # Description of what happened
    
    # Flow information
    flow_id: Optional[str] = None
    next_node_id: Optional[str] = None
    node_type: Optional[str] = None  # "message", "question", "button_question", etc.
    
    # Automation status
    automation_exited: bool = False  # True if user exited automation due to validation failures
    
    # Additional data
    sent_message_id: Optional[str] = None  # Message ID if message was sent
    validation_count: Optional[int] = None  # Current validation failure count
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "status": "success",
                    "message": "Message sent successfully",
                    "flow_id": "flow_123",
                    "next_node_id": "node_2",
                    "node_type": "message",
                    "automation_exited": False,
                    "sent_message_id": "wamid.123456",
                    "validation_count": 0
                },
                {
                    "status": "validation_exit",
                    "message": "Validation limit exceeded, automation exited",
                    "flow_id": "flow_123",
                    "next_node_id": "node_2",
                    "node_type": "button_question",
                    "automation_exited": True,
                    "validation_count": 3
                },
                {
                    "status": "error",
                    "message": "Failed to send message: Invalid phone number",
                    "flow_id": "flow_123",
                    "next_node_id": "node_2",
                    "node_type": "message",
                    "automation_exited": False
                }
            ]
        }

