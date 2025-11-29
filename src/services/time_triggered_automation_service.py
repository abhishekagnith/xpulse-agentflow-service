"""
Time Triggered Automation Service
Handles scheduled/time-based trigger webhooks for executing flows at specific times.
"""
from typing import Dict, Any, Optional
from utils.log_utils import LogUtil
from database.flow_db import FlowDB
from models.request.webhook_message_request import WebhookMessageRequest


class TimeTriggeredAutomationService:
    """
    Service for handling scheduled/time-based trigger webhooks.
    Processes flows that are triggered by time-based events (scheduled, recurring, etc.)
    """
    
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB
    ):
        self.log_util = log_util
        self.flow_db = flow_db
    
    async def process_scheduled_trigger(
        self,
        request: WebhookMessageRequest
    ) -> Dict[str, Any]:
        """
        Process scheduled trigger webhook and execute the associated flow.
        
        Expected message_body structure:
        {
            "trigger_id": "trigger_123",
            "flow_id": "691ee40841e8102454474848",
            "trigger_node_id": "trigger_keyword-node-1763631396283-h1ymxv3e3",
            "scheduled_time": "2025-11-26T10:00:00Z",
            "trigger_type": "scheduled",  # or "recurring", "one_time"
            "recurrence_pattern": "daily",  # optional: "daily", "weekly", "monthly", etc.
            "target_users": ["919634086404", "919634086405"],  # optional: specific users to trigger
            "target_brand_id": 1  # optional: specific brand
        }
        
        Returns:
            Dict with processing result
        """
        try:
            self.log_util.info(
                service_name="TimeTriggeredAutomationService",
                message=f"Processing scheduled trigger webhook, brand_id: {request.brand_id}, flow_id: {request.message_body.get('flow_id')}"
            )
            
            # Extract flow_id from message_body
            flow_id = request.message_body.get("flow_id")
            if not flow_id:
                self.log_util.error(
                    service_name="TimeTriggeredAutomationService",
                    message="Missing flow_id in scheduled trigger webhook"
                )
                return {
                    "status": "error",
                    "message": "Missing flow_id in scheduled trigger webhook",
                    "flow_id": None
                }
            
            # Extract trigger details
            trigger_id = request.message_body.get("trigger_id")
            trigger_node_id = request.message_body.get("trigger_node_id")
            scheduled_time = request.message_body.get("scheduled_time")
            trigger_type = request.message_body.get("trigger_type", "scheduled")
            recurrence_pattern = request.message_body.get("recurrence_pattern")
            target_users = request.message_body.get("target_users", [])
            
            self.log_util.info(
                service_name="TimeTriggeredAutomationService",
                message=f"Scheduled trigger details - trigger_id: {trigger_id}, flow_id: {flow_id}, trigger_node_id: {trigger_node_id}, scheduled_time: {scheduled_time}, trigger_type: {trigger_type}"
            )
            
            # TODO: Implement flow execution logic
            # 1. Retrieve flow by flow_id
            # 2. Get trigger node
            # 3. Get target users (from target_users or query based on criteria)
            # 4. For each target user, initiate the flow
            # 5. Handle recurring triggers if applicable
            
            self.log_util.info(
                service_name="TimeTriggeredAutomationService",
                message=f"Scheduled trigger processed successfully for flow_id: {flow_id}"
            )
            
            return {
                "status": "success",
                "message": "Scheduled trigger processed successfully",
                "flow_id": flow_id,
                "trigger_id": trigger_id,
                "target_users_count": len(target_users) if target_users else 0
            }
            
        except Exception as e:
            self.log_util.error(
                service_name="TimeTriggeredAutomationService",
                message=f"Error processing scheduled trigger: {str(e)}"
            )
            return {
                "status": "error",
                "message": f"Error processing scheduled trigger: {str(e)}",
                "flow_id": request.message_body.get("flow_id") if request.message_body else None
            }

