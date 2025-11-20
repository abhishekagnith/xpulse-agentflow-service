from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class WhatsAppFlowEdgeData(BaseModel):
    id: Optional[str] = None  # MongoDB _id
    flow_id: str  # Reference to the flow's MongoDB _id
    edge_id: str  # The edge's id from flowEdges array
    source_node_id: str  # sourceNodeId
    target_node_id: str  # targetNodeId
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

