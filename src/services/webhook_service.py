from typing import Optional, Dict, Any

# Utils
from utils.log_utils import LogUtil

# Database
from database.flow_db import FlowDB

# Services
from services.user_state_service import UserStateService

# Models
from models.request.webhook_message_request import WebhookMessageRequest
from models.webhook_message_data import WebhookMessageData


class WebhookService:
    """
    Service for handling webhook messages from channel services.
    Manages webhook processing, status tracking, and flow automation triggering.
    """
    
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB,
        user_state_service: UserStateService
    ):
        self.log_util = log_util
        self.flow_db = flow_db
        self.user_state_service = user_state_service
    
    async def process_webhook_message(
        self,
        request: WebhookMessageRequest
    ) -> Dict[str, Any]:
        """
        Process incoming webhook message and trigger flow automation.
        
        Steps:
        1. Save webhook with status: "pending"
        2. Process user state and flow automation
        3. Update webhook status to "processed" or "error"
        
        Returns:
            Dict with processing result including flow_id, current_node_id, etc.
        """
        webhook_id = None
        try:
            self.log_util.info(
                service_name="WebhookService",
                message=f"Received webhook message from {request.channel} for user {request.sender}, brand_id: {request.brand_id}"
            )
            
            # Step 1: Save webhook message with status: "pending"
            webhook_message = WebhookMessageData(
                sender=request.sender,
                brand_id=request.brand_id,
                user_id=request.user_id,
                channel_identifier=request.channel_identifier,
                channel_phone_number_id=request.channel_phone_number_id,
                message_type=request.message_type,
                message_body=request.message_body,
                channel=request.channel,
                status="pending"
            )
            
            saved_webhook = await self.flow_db.save_webhook_message(webhook_message)
            if not saved_webhook:
                self.log_util.error(
                    service_name="WebhookService",
                    message="Failed to save webhook message to database"
                )
                return {
                    "status": "error",
                    "message": "Failed to save webhook message",
                    "automation_triggered": False,
                    "flow_id": None,
                    "current_node_id": None,
                    "error_details": "Database save failed"
                }
            
            webhook_id = saved_webhook.id
            self.log_util.info(
                service_name="WebhookService",
                message=f"Saved webhook message to database with ID: {webhook_id}, status: pending"
            )
            
            # Step 2: Map channel-specific identifiers to generic format
            waba_id = request.channel_identifier
            phone_number_id = request.channel_phone_number_id or request.channel_identifier
            
            # Step 3: Process user state and flow automation
            # This method handles:
            # - Creating new user if doesn't exist
            # - Checking for trigger matches
            # - Processing existing automation flows
            # - Finding next nodes and sending messages
            await self.user_state_service.check_and_process_user_with_flow(
                sender=request.sender,
                brand_id=request.brand_id,
                user_id=request.user_id,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
                message_type=request.message_type,
                message_body=request.message_body,
                channel=request.channel
            )
            
            # Step 4: Update webhook status to "processed"
            webhook_message.status = "processed"
            updated_webhook = await self.flow_db.update_webhook_message(webhook_id, webhook_message)
            
            if updated_webhook:
                self.log_util.info(
                    service_name="WebhookService",
                    message=f"Updated webhook message {webhook_id} status to: processed"
                )
            
            self.log_util.info(
                service_name="WebhookService",
                message=f"Successfully processed webhook message for user {request.sender}"
            )
            
            # Note: check_and_process_user_with_flow doesn't return a value
            # We return a generic success response
            # TODO: Consider modifying user_state_service to return processing details
            
            return {
                "status": "success",
                "message": "Webhook message processed successfully",
                "automation_triggered": True,  # Assume true if no error occurred
                "flow_id": None,  # TODO: Get from user state service return value
                "current_node_id": None,  # TODO: Get from user state service return value
                "error_details": None,
                "webhook_id": webhook_id
            }
            
        except Exception as e:
            self.log_util.error(
                service_name="WebhookService",
                message=f"Error processing webhook message for user {request.sender}: {str(e)}"
            )
            
            # Update webhook status to "error" if it was saved
            if webhook_id:
                try:
                    webhook_message = WebhookMessageData(
                        sender=request.sender,
                        brand_id=request.brand_id,
                        user_id=request.user_id,
                        channel_identifier=request.channel_identifier,
                        channel_phone_number_id=request.channel_phone_number_id,
                        message_type=request.message_type,
                        message_body=request.message_body,
                        channel=request.channel,
                        status="error"
                    )
                    await self.flow_db.update_webhook_message(webhook_id, webhook_message)
                    self.log_util.info(
                        service_name="WebhookService",
                        message=f"Updated webhook message {webhook_id} status to: error"
                    )
                except Exception as update_error:
                    self.log_util.error(
                        service_name="WebhookService",
                        message=f"Error updating webhook message status: {str(update_error)}"
                    )
            
            return {
                "status": "error",
                "message": "Error processing webhook message",
                "automation_triggered": False,
                "flow_id": None,
                "current_node_id": None,
                "error_details": str(e),
                "webhook_id": webhook_id
            }

