from pydantic import BaseModel, Field
from typing import Optional


class ValidationData(BaseModel):
    """
    Validation state for user responses in flow automation.
    Tracks validation failures, count, and messages.
    """
    failed: bool = Field(default=False, description="Whether last validation failed")
    failure_count: int = Field(default=0, description="Count of consecutive validation failures")
    failure_message: Optional[str] = Field(default=None, description="Last validation failure message")

