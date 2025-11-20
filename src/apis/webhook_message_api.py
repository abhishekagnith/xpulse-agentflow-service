from fastapi import APIRouter, HTTPException
from typing import Dict, Any

# Utils
from utils.log_utils import LogUtil

# Services
from services.webhook_service import WebhookService

# Models
from models.request.webhook_message_request import WebhookMessageRequest
from models.response.webhook_message_response import WebhookMessageResponse


def create_webhook_message_api(
    log_util: LogUtil,
    webhook_service: WebhookService
) -> APIRouter:
    """
    Create API router for handling incoming webhook messages from channel services.
    This is the entry point for WhatsApp, Telegram, SMS, and other channel services
    to trigger flow automation.
    """
    router = APIRouter(
        prefix="/webhook",
        tags=["webhook"],
    )

    @router.post("/message", response_model=WebhookMessageResponse)
    async def process_webhook_message(request: WebhookMessageRequest) -> WebhookMessageResponse:
        """
        Process incoming webhook message and trigger flow automation if applicable.
        
        This endpoint:
        1. Receives message data from channel services (WhatsApp, Telegram, etc.)
        2. Saves webhook with status: "pending"
        3. Checks/creates user record
        4. Determines if flow automation should be triggered
        5. Processes automation flow if applicable
        6. Updates webhook status to "processed" or "error"
        7. Returns status of automation processing
        """
        try:
            # Delegate to webhook service
            result = await webhook_service.process_webhook_message(request)
            
            return WebhookMessageResponse(
                status=result.get("status", "success"),
                message=result.get("message", "Webhook message processed successfully"),
                automation_triggered=result.get("automation_triggered", False),
                flow_id=result.get("flow_id"),
                current_node_id=result.get("current_node_id"),
                error_details=result.get("error_details")
            )
            
        except Exception as e:
            log_util.error(
                service_name="WebhookMessageAPI",
                message=f"Error processing webhook message for user {request.sender}: {str(e)}"
            )
            
            # Return error response instead of raising exception
            # This allows webhook service to handle gracefully
            return WebhookMessageResponse(
                status="error",
                message="Error processing webhook message",
                automation_triggered=False,
                flow_id=None,
                current_node_id=None,
                error_details=str(e)
            )

    @router.get("/health")
    async def webhook_health_check() -> Dict[str, Any]:
        """Health check endpoint for webhook API"""
        return {
            "status": "healthy",
            "api": "webhook_message_api",
            "service": "flow_service"
        }

    return router

