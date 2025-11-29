from typing import Optional, Dict, Any

# Utils
from utils.log_utils import LogUtil

# Database
from database.flow_db import FlowDB

# Services
from services.user_state_service import UserStateService
from services.channel_message_adapter import ChannelMessageAdapter
from services.time_triggered_automation_service import TimeTriggeredAutomationService

# Models
from models.request.webhook_message_request import WebhookMessageRequest
from models.webhook_message_data import WebhookMessageData, WebhookMetadata


class WebhookService:
    """
    Service for handling webhook messages from channel services.
    Manages webhook processing, status tracking, and flow automation triggering.
    """
    
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB,
        user_state_service: UserStateService,
        time_triggered_automation_service: Optional[TimeTriggeredAutomationService] = None
    ):
        self.log_util = log_util
        self.flow_db = flow_db
        self.user_state_service = user_state_service
        self.time_triggered_automation_service = time_triggered_automation_service
        self.channel_adapter = ChannelMessageAdapter(log_util)
    
    def is_scheduled_trigger_webhook(self, request: WebhookMessageRequest) -> bool:
        """
        Identify if the webhook is a scheduled trigger webhook.
        
        Args:
            request: WebhookMessageRequest to check
        
        Returns:
            True if it's a scheduled trigger webhook, False otherwise
        """
        return (
            request.message_type == "scheduled_trigger" and
            request.sender == "system" and
            request.channel == "system"
        )
    
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
            
            # Step 1: Transform incoming webhook using channel adapter
            normalized_message = self.channel_adapter.normalize_message(
                channel=request.channel,
                message_type=request.message_type,
                message_body=request.message_body
            )
            
            # Step 2: Save webhook message with status: "pending"
            # Store normalized message structure in data field for consistent format
            # For system webhooks (delay_complete, scheduled_trigger), sender should be "system"
            metadata = WebhookMetadata(
                sender=request.sender,  # "system" for system webhooks
                brand_id=request.brand_id,
                user_id=request.user_id,
                channel_identifier=request.channel_identifier,  # None for system webhooks
                channel=request.channel,  # "system" for system webhooks
                status="pending",
                message_type=request.message_type
            )
            webhook_message = WebhookMessageData(
                metadata=metadata,
                data=normalized_message.to_dict()  # Store normalized message structure
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
            
            # Step 2.5: Save webhook adapter processed data (after adapter normalization)
            # Store in the same metadata/data format that gets passed to user_state_service
            from models.webhook_adapter_processed_data import WebhookAdapterProcessedData
            webhook_adapter_data = WebhookAdapterProcessedData(
                original_webhook_id=webhook_id,
                original_message_body=request.message_body,
                metadata=metadata,  # Same metadata as WebhookMessageData
                data=normalized_message.to_dict()  # Same normalized data as WebhookMessageData
            )
            saved_adapter_data = await self.flow_db.save_webhook_adapter_processed(webhook_adapter_data)
            if saved_adapter_data:
                self.log_util.info(
                    service_name="WebhookService",
                    message=f"Saved webhook adapter processed data with ID: {saved_adapter_data.id} for webhook: {webhook_id}"
                )
            
            # Step 2: Check if this is a scheduled trigger webhook
            if self.is_scheduled_trigger_webhook(request):
                # Route to time-triggered automation service
                if self.time_triggered_automation_service:
                    self.log_util.info(
                        service_name="WebhookService",
                        message=f"Routing scheduled trigger webhook to TimeTriggeredAutomationService"
                    )
                    result = await self.time_triggered_automation_service.process_scheduled_trigger(request)
                    
                    # Update webhook status based on result
                    if result.get("status") == "success":
                        webhook_message.metadata.status = "processed"
                    else:
                        webhook_message.metadata.status = "error"
                    
                    updated_webhook = await self.flow_db.update_webhook_message(webhook_id, webhook_message)
                    if updated_webhook:
                        self.log_util.info(
                            service_name="WebhookService",
                            message=f"Updated webhook message {webhook_id} status to: {webhook_message.metadata.status}"
                        )
                    
                    return {
                        "status": result.get("status", "success"),
                        "message": result.get("message", "Scheduled trigger processed"),
                        "automation_triggered": True,
                        "flow_id": result.get("flow_id"),
                        "current_node_id": None,
                        "error_details": None,
                        "webhook_id": webhook_id
                    }
                else:
                    self.log_util.error(
                        service_name="WebhookService",
                        message="TimeTriggeredAutomationService is not initialized, cannot process scheduled trigger"
                    )
                    webhook_message.metadata.status = "error"
                    await self.flow_db.update_webhook_message(webhook_id, webhook_message)
                    return {
                        "status": "error",
                        "message": "TimeTriggeredAutomationService not initialized",
                        "automation_triggered": False,
                        "flow_id": None,
                        "current_node_id": None,
                        "error_details": "Service not available",
                        "webhook_id": webhook_id
                    }
            
            # Step 3: Regular webhook processing - Map channel account ID (for WhatsApp, this is the phone number ID)
            channel_account_id = None
            if request.channel == "whatsapp" and request.channel_phone_number_id:
                channel_account_id = request.channel_phone_number_id
            
            # Step 4: Process user state and flow automation
            # This method handles:
            # - Creating new user if doesn't exist
            # - Checking for trigger matches
            # - Processing existing automation flows
            # - Finding next nodes and sending messages
            processing_result = await self.user_state_service.check_and_process_user_with_flow(
                metadata=webhook_message.metadata,
                data=webhook_message.data,
                channel_account_id=channel_account_id
            )
            
            # Step 4: Update webhook status to "processed"
            webhook_message.metadata.status = "processed"
            updated_webhook = await self.flow_db.update_webhook_message(webhook_id, webhook_message)
            
            if updated_webhook:
                self.log_util.info(
                    service_name="WebhookService",
                    message=f"Updated webhook message {webhook_id} status to: processed"
                )
            
            # Return status from UserStateService
            if processing_result:
                status = processing_result.get("status", "success")
                return {
                    "status": "success",
                    "message": "Webhook message processed successfully",
                    "automation_triggered": status == "triggered",
                    "flow_id": processing_result.get("flow_id"),
                    "current_node_id": processing_result.get("trigger_node_id"),
                    "error_details": None,
                    "webhook_id": webhook_id,
                    "trigger_status": status,
                    "trigger_message": processing_result.get("message")
                }
            else:
                # Fallback if no result returned
                return {
                    "status": "success",
                    "message": "Webhook message processed successfully",
                    "automation_triggered": False,
                    "flow_id": None,
                    "current_node_id": None,
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
                    # Transform webhook using adapter (same as initial save)
                    normalized_message = self.channel_adapter.normalize_message(
                        channel=request.channel,
                        message_type=request.message_type,
                        message_body=request.message_body
                    )
                    metadata = WebhookMetadata(
                        sender=request.sender,
                        brand_id=request.brand_id,
                        user_id=request.user_id,
                        channel_identifier=request.channel_identifier,
                        channel=request.channel,
                        status="error",
                        message_type=request.message_type
                    )
                    webhook_message = WebhookMessageData(
                        metadata=metadata,
                        data=normalized_message.to_dict()
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

