from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class WhatsAppFlowNodeData(BaseModel):
    id: Optional[str] = None  # MongoDB _id
    flow_id: str  # Reference to the flow's MongoDB _id
    node_id: str  # The node's id from flowNodes array
    node_type: str  # type field from the node
    flow_node_type: str  # flowNodeType field
    node_data: Dict[str, Any]  # The entire node object as JSON
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

