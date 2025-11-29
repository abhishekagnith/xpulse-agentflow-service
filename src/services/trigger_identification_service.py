from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING

# Utils
from utils.log_utils import LogUtil

# Database
from database.flow_db import FlowDB

# Services
from services.flow_service import FlowService

# Models
from models.user_data import UserData
from models.flow_data import FlowData
from models.webhook_message_data import WebhookMetadata

if TYPE_CHECKING:
    from services.user_state_service import UserStateService


class TriggerIdentificationService:
    """
    Service for identifying triggers and initiating flows when users are not in automation.
    Handles trigger checking and flow initiation for both new and existing users.
    """
    
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB,
        flow_service: FlowService,
        user_state_service: "UserStateService"
    ):
        self.log_util = log_util
        self.flow_db = flow_db
        self.flow_service = flow_service
        self.user_state_service = user_state_service
    
    async def identify_and_initiate_trigger_flow(
        self,
        metadata: "WebhookMetadata",
        data: Dict[str, Any],
        channel_account_id: Optional[str] = None,
        existing_user: Optional[UserData] = None
    ) -> Dict[str, Any]:
        """
        Identify triggers and initiate flow if a trigger matches.
        
        This method:
        1. Checks for matching triggers using FlowService
        2. If trigger matches, retrieves the flow
        3. Returns flow_id and trigger_node_id for UserStateService to process
        
        Args:
            metadata: WebhookMetadata from saved webhook
            data: Normalized data from saved webhook
            channel_account_id: Channel account ID
            existing_user: Existing user data (if user already exists)
        
        Returns:
            Dict with status and result information:
            - status: "triggered", "no_trigger", or "error"
            - message: Status message
            - flow_id: Flow ID if triggered
            - trigger_node_id: Trigger node ID if triggered
        """
        try:
            # Extract values from metadata
            user_identifier = metadata.sender
            brand_id = metadata.brand_id
            user_id = metadata.user_id
            message_type = metadata.message_type
            channel = metadata.channel
            
            user_type = "existing" if existing_user else "new"
            self.log_util.info(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_IDENTIFY] Checking triggers for {user_type} user {user_identifier}, brand_id: {brand_id}, message_type: {message_type}"
            )
            
            # Step 1: Check for matching triggers
            trigger_result = await self.check_and_get_flow_for_trigger(
                brand_id=brand_id,
                message_type=message_type,
                message_body=data,  # Pass normalized data
                channel=channel
            )
            
            if not trigger_result:
                self.log_util.info(
                    service_name="TriggerIdentificationService",
                    message=f"[TRIGGER_IDENTIFY] ❌ No trigger matched for user {user_identifier}, brand_id: {brand_id}, message_type: {message_type}"
                )
                return {
                    "status": "no_trigger",
                    "message": "No trigger matched",
                    "flow_id": None,
                    "trigger_node_id": None
                }
            
            # Step 2: Trigger matched - get flow and trigger node
            flow_id, trigger_node_id = trigger_result
            self.log_util.info(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_IDENTIFY] ✅ Trigger matched! flow_id: {flow_id}, trigger_node_id: {trigger_node_id}"
            )
            
            # Step 3: Retrieve the flow and verify it's published
            flow = await self.flow_db.get_flow_by_id(flow_id)
            if not flow:
                self.log_util.error(
                    service_name="TriggerIdentificationService",
                    message=f"[TRIGGER_IDENTIFY] ❌ Failed to retrieve flow with id: {flow_id}"
                )
                return {
                    "status": "error",
                    "message": f"Failed to retrieve flow with id: {flow_id}",
                    "flow_id": flow_id,
                    "trigger_node_id": trigger_node_id
                }
            
            # Verify flow is published (only published flows should be triggered)
            if flow.status != "published":
                self.log_util.warning(
                    service_name="TriggerIdentificationService",
                    message=f"[TRIGGER_IDENTIFY] ⚠️ Flow {flow_id} is not published (status: {flow.status}). Skipping trigger."
                )
                return {
                    "status": "no_trigger",
                    "message": f"Flow is not published (status: {flow.status})",
                    "flow_id": flow_id,
                    "trigger_node_id": trigger_node_id
                }
            
            self.log_util.info(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_IDENTIFY] ✅ Flow retrieved successfully: {flow.name} (id: {flow_id})"
            )
            
            # Step 4: Get or ensure user data exists
            if not existing_user:
                # For new users, get the user that was just created
                existing_user = await self.flow_db.get_user_data(
                    user_identifier=user_identifier,
                    brand_id=brand_id,
                    channel=channel,
                    channel_account_id=channel_account_id
                )
                if not existing_user:
                    self.log_util.error(
                        service_name="TriggerIdentificationService",
                        message=f"[TRIGGER_IDENTIFY] ❌ Failed to retrieve user data for {user_identifier}"
                    )
                    return {
                        "status": "error",
                        "message": f"Failed to retrieve user data for {user_identifier}",
                        "flow_id": flow_id,
                        "trigger_node_id": trigger_node_id
                    }
            
            self.log_util.info(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_IDENTIFY] ✅ User data retrieved for {user_identifier}"
            )
            
            # Step 5: Return trigger result - UserStateService will call node service
            self.log_util.info(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_IDENTIFY] ✅ Trigger matched! Returning flow_id: {flow_id}, trigger_node_id: {trigger_node_id}"
            )
            
            return {
                "status": "triggered",
                "message": "Trigger matched",
                "flow_id": flow_id,
                "trigger_node_id": trigger_node_id
            }
            
        except Exception as e:
            self.log_util.error(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_IDENTIFY] ❌ Error identifying trigger for user {user_identifier}: {str(e)}"
            )
            return {
                "status": "error",
                "message": f"Error identifying trigger: {str(e)}",
                "flow_id": None,
                "trigger_node_id": None
            }
    
    async def check_and_get_flow_for_trigger(
        self,
        brand_id: int,
        message_type: str,
        message_body: Dict[str, Any],
        channel: str = "whatsapp"
    ) -> Optional[Tuple[str, str]]:
        """
        Check user message against available triggers and return flow_id and node_id if match found.
        Uses channel adapter to normalize message content for channel-agnostic processing.
        
        Returns: (flow_id, node_id) tuple if match found, None otherwise
        """
        try:
            self.log_util.info(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_CHECK] Starting trigger check for brand_id: {brand_id}, message_type: {message_type}, channel: {channel}"
            )
            
            # Step 1: Extract text content from normalized data
            # Data is already normalized by WebhookService, so extract user_reply directly
            text_content = message_body.get("user_reply", "").strip() or None
            
            if not text_content:
                self.log_util.warning(
                    service_name="TriggerIdentificationService",
                    message=f"[TRIGGER_CHECK] ❌ No text content extracted from message_body: {message_body}"
                )
                return None
            
            self.log_util.info(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_CHECK] Extracted text content: '{text_content}' (channel: {channel})"
            )
            
            # Step 3: Get all triggers for this brand
            self.log_util.info(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_CHECK] Fetching triggers for brand_id: {brand_id}"
            )
            triggers = await self.flow_db.get_flow_triggers_by_brand_id(brand_id)
            if triggers is None or len(triggers) == 0:
                self.log_util.warning(
                    service_name="TriggerIdentificationService",
                    message=f"[TRIGGER_CHECK] ❌ No triggers found for brand_id: {brand_id}"
                )
                return None
            
            self.log_util.info(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_CHECK] Found {len(triggers)} triggers to check against text: '{text_content}'"
            )
            
            # Step 4: Check each trigger
            for trigger in triggers:
                self.log_util.info(
                    service_name="TriggerIdentificationService",
                    message=f"[TRIGGER_CHECK] Checking trigger: type={trigger.trigger_type}, flow_id={trigger.flow_id}, node_id={trigger.node_id}, values={trigger.trigger_values}"
                )
                if trigger.trigger_type == "keyword":
                    # Keyword triggers only work with text messages
                    if message_type == "text":
                        # Check if message text contains any keyword (case-insensitive)
                        for keyword in trigger.trigger_values:
                            self.log_util.info(
                                service_name="TriggerIdentificationService",
                                message=f"[TRIGGER_CHECK] Comparing keyword '{keyword}' (lower: '{keyword.lower()}') with text '{text_content}' (lower: '{text_content.lower()}')"
                            )
                            if keyword.lower() in text_content.lower():
                                self.log_util.info(
                                    service_name="TriggerIdentificationService",
                                    message=f"[TRIGGER_CHECK] ✅ Keyword trigger matched: '{keyword}' in message '{text_content}' for flow_id: {trigger.flow_id}, node_id: {trigger.node_id}"
                                )
                                return (trigger.flow_id, trigger.node_id)
                            else:
                                self.log_util.info(
                                    service_name="TriggerIdentificationService",
                                    message=f"[TRIGGER_CHECK] ❌ Keyword '{keyword}' not found in '{text_content}'"
                                )
                    else:
                        self.log_util.info(
                            service_name="TriggerIdentificationService",
                            message=f"[TRIGGER_CHECK] Skipping keyword trigger (message_type is '{message_type}', not 'text')"
                        )
                
                elif trigger.trigger_type == "template":
                    # Template triggers work with both text and button messages
                    # Check if message text/button exactly matches any expected button text (case-insensitive)
                    for button_text in trigger.trigger_values:
                        self.log_util.info(
                            service_name="TriggerIdentificationService",
                            message=f"[TRIGGER_CHECK] Comparing template button '{button_text}' (lower: '{button_text.lower()}') with text '{text_content}' (lower: '{text_content.lower()}')"
                        )
                        if button_text.lower() == text_content.lower():
                            self.log_util.info(
                                service_name="TriggerIdentificationService",
                                message=f"[TRIGGER_CHECK] ✅ Template trigger matched: '{button_text}' matches message '{text_content}' (type: {message_type}) for flow_id: {trigger.flow_id}, node_id: {trigger.node_id}"
                            )
                            return (trigger.flow_id, trigger.node_id)
                        else:
                            self.log_util.info(
                                service_name="TriggerIdentificationService",
                                message=f"[TRIGGER_CHECK] ❌ Template button '{button_text}' does not match '{text_content}'"
                            )
            
            self.log_util.info(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_CHECK] ❌ No trigger matched for text: '{text_content}'"
            )
            return None
            
        except Exception as e:
            self.log_util.error(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_CHECK] ❌ Error checking triggers: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="TriggerIdentificationService",
                message=f"[TRIGGER_CHECK] Traceback: {traceback.format_exc()}"
            )
            return None

