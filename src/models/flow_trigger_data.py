from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class FlowTriggerData(BaseModel):
    id: Optional[str] = None  # MongoDB _id
    flow_id: str  # Reference to the flow's MongoDB _id
    node_id: str  # The trigger node's id from flowNodes array
    trigger_type: str  # "keyword" or "template"
    trigger_values: List[str]  # Array of keywords for keyword trigger, array of reply button texts for template trigger
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

