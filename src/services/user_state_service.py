from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

# Utils
from utils.log_utils import LogUtil

# Database
from database.flow_db import FlowDB

# Services
from services.flow_service import FlowService
from services.whatsapp_flow_service import WhatsAppFlowService
from services.node_identification_service import NodeIdentificationService
from services.reply_validation_service import ReplyValidationService
from services.lead_management_service import LeadManagementService
from services.lead_management_service import LeadManagementService

# Models
from models.user_data import UserData
from models.flow_data import FlowData
from models.user_detail import UserDetail
from models.webhook_message_data import WebhookMetadata


class UserStateService:
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB,
        flow_service: Optional[FlowService] = None,
        node_process_service: Optional[Any] = None,  # Channel-specific, made optional
        node_process_api_url: Optional[str] = None,  # API endpoint URL
        node_identification_service: Optional[NodeIdentificationService] = None,  # Node identification service
        reply_validation_service: Optional[ReplyValidationService] = None,  # Reply validation service
        lead_management_service: Optional[LeadManagementService] = None,  # Lead management service
    ):
        self.log_util = log_util
        self.flow_db = flow_db
        self.flow_service = flow_service
        self.node_process_service = node_process_service  # Kept for backward compatibility, but will use API
        self.trigger_identification_service = None  # Will be set via setter to avoid circular dependency
        # Initialize WhatsAppFlowService for channel-specific operations
        self.whatsapp_flow_service = WhatsAppFlowService(
            log_util=log_util,
            flow_db=flow_db,
            node_process_api_url=node_process_api_url
        )
        # Initialize ReplyValidationService if not provided
        if reply_validation_service:
            self.reply_validation_service = reply_validation_service
        else:
            self.reply_validation_service = ReplyValidationService(
                log_util=log_util,
                flow_db=flow_db
            )
        # Initialize NodeIdentificationService if not provided
        if node_identification_service:
            self.node_identification_service = node_identification_service
        else:
            self.node_identification_service = NodeIdentificationService(
                log_util=log_util,
                flow_db=flow_db,
                whatsapp_flow_service=self.whatsapp_flow_service
            )
        # Initialize LeadManagementService if not provided
        if lead_management_service:
            self.lead_management_service = lead_management_service
        else:
            self.lead_management_service = LeadManagementService(
                log_util=log_util
            )
    
    def set_trigger_identification_service(self, trigger_identification_service):
        """Set the trigger identification service (called after initialization to avoid circular dependency)"""
        self.trigger_identification_service = trigger_identification_service
    
    async def _process_validation_and_get_node_service_params(
        self,
        metadata: "WebhookMetadata",
        data: Dict[str, Any],
        existing_user: "UserData",
        flow: "FlowData",
        current_node: Dict[str, Any],
        node_type: str,
        is_text: bool,
        sender: str,
        brand_id: int,
        channel: str,
        channel_account_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Process validation service call and return parameters for node identification service.
        
        This function:
        1. Calls validation service with current node and user reply
        2. Handles validation_exit case (exits automation and returns early)
        3. Returns parameters needed to call node identification service
        
        Args:
            metadata: WebhookMetadata from saved webhook
            data: Normalized data from saved webhook
            existing_user: Current user data
            flow: Flow data
            current_node: Current node data
            node_type: Current node type
            is_text: Whether node is text question type
            sender: User identifier
            brand_id: Brand ID
            channel: Channel name
            channel_account_id: Channel account ID
        
        Returns:
            Dict with:
                - handled: bool - True if validation_exit was handled (automation exited), False if node service should be called
                - is_validation_error: bool - Whether validation failed
                - fallback_message: Optional[str] - Fallback message for validation errors
                - node_id_to_process: Optional[str] - Node ID to process (for matched_other_node or retry)
                - current_node_id_for_service: str - Current node ID to use for node service (may be matched_answer_id)
                - validation_result: Dict[str, Any] - Validation result for later use
        """
        try:
            self.log_util.info(
                service_name="UserStateService",
                message=f"[EXISTING_USER] Current node has expected reply, calling validation service"
            )
            
            # Get current validation count from user state
            current_validation_count = 0
            if existing_user.validation:
                if isinstance(existing_user.validation, dict):
                    current_validation_count = existing_user.validation.get("failure_count", 0)
                else:
                    current_validation_count = existing_user.validation.failure_count if hasattr(existing_user.validation, "failure_count") else 0
            
            # Log data being passed to validation service for debugging
            self.log_util.info(
                service_name="UserStateService",
                message=f"[EXISTING_USER] Data passed to validation service - keys: {list(data.keys()) if data else 'None'}, user_reply: '{data.get('user_reply') if data else None}', full_data: {data}"
            )
            
            validation_result = await self.reply_validation_service.validate_and_match_reply(
                metadata=metadata,
                data=data,
                current_node_id=existing_user.current_node_id,
                flow_id=flow.id,
                is_text=is_text,
                current_validation_count=current_validation_count
            )
            
            # Log validation result for debugging
            self.log_util.info(
                service_name="UserStateService",
                message=f"[EXISTING_USER] Validation result: status={validation_result.get('status')}, matched_answer_id={validation_result.get('matched_answer_id')}, matched_node_id={validation_result.get('matched_node_id')}"
            )
            
            # Handle validation_exit case - send error message but keep automation active
            if validation_result["status"] == "validation_exit":
                # Validation limit exceeded - send error message but DON'T exit automation
                # User can still send correct message to proceed (validation will pass if correct)
                self.log_util.warning(
                    service_name="UserStateService",
                    message=f"[EXISTING_USER] Validation limit exceeded for user {sender}, sending error message but keeping automation active. User can still send correct message."
                )
                
                # Get fallback message from validation result
                fallback_message = validation_result.get("fallback_message")
                
                # Call node service with validation error to send error message only
                user_detail_dict = existing_user.user_detail.model_dump() if existing_user.user_detail else None
                node_service_response = await self.node_identification_service.identify_and_process_node(
                    metadata=metadata,
                    data=data,
                    is_validation_error=True,
                    fallback_message=fallback_message,
                    node_id_to_process=None,
                    current_node_id=existing_user.current_node_id,
                    flow_id=flow.id,
                    user_detail=user_detail_dict,
                    lead_id=existing_user.lead_id if existing_user else None
                )
                
                # DON'T exit automation - keep is_in_automation=True and validation count
                # DON'T update user state - keep current_node_id and validation count as is
                # User can still send correct message to proceed
                # Return handled=True to return early (don't process any node)
                return {
                    "handled": True,  # Return early, don't process any node
                    "validation_exit": True,
                    "node_service_response": node_service_response
                }
            
            # Determine parameters for node service
            is_validation_error = False
            fallback_message = None
            node_id_to_process = None
            
            if validation_result["status"] == "matched":
                # Reply matched expected answer
                is_validation_error = False
                fallback_message = None
                node_id_to_process = None
                
            elif validation_result["status"] == "matched_other_node":
                # Reply matched another node in the flow
                is_validation_error = False
                fallback_message = None
                node_id_to_process = validation_result.get("matched_node_id")
                
            elif validation_result["status"] == "mismatch_retry":
                # Reply didn't match, retry current node with fallback
                is_validation_error = True
                fallback_message = validation_result.get("fallback_message")
                node_id_to_process = existing_user.current_node_id  # Retry same node
                
            else:
                # use_default_edge or other status
                is_validation_error = False
                fallback_message = None
                node_id_to_process = None
            
            # Determine current_node_id_for_service
            # For matched status, use matched_answer_id as current_node_id
            current_node_id_for_service = existing_user.current_node_id
            if validation_result["status"] == "matched":
                matched_answer_id = validation_result.get("matched_answer_id")
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"[EXISTING_USER] Status is 'matched', matched_answer_id={matched_answer_id}, original current_node_id={existing_user.current_node_id}"
                )
                if not matched_answer_id:
                    self.log_util.error(
                        service_name="UserStateService",
                        message=f"[EXISTING_USER] Status is 'matched' but matched_answer_id is None/empty. Cannot proceed without matched_answer_id."
                    )
                    return {
                        "handled": False,
                        "is_validation_error": False,
                        "fallback_message": None,
                        "node_id_to_process": None,
                        "current_node_id_for_service": None,
                        "validation_result": validation_result,
                        "error": "matched_answer_id is required for 'matched' status but is None/empty"
                    }
                current_node_id_for_service = matched_answer_id
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"[EXISTING_USER] ✅ Using matched_answer_id as current_node_id_for_service: {current_node_id_for_service}"
                )
            else:
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"[EXISTING_USER] Status is '{validation_result.get('status')}', using original current_node_id: {current_node_id_for_service}"
                )
            
            # Return parameters for node identification service
            return {
                "handled": False,
                "is_validation_error": is_validation_error,
                "fallback_message": fallback_message,
                "node_id_to_process": node_id_to_process,
                "current_node_id_for_service": current_node_id_for_service,
                "validation_result": validation_result
            }
            
        except Exception as e:
            self.log_util.error(
                service_name="UserStateService",
                message=f"Error in _process_validation_and_get_node_service_params: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="UserStateService",
                message=f"Traceback: {traceback.format_exc()}"
            )
            # Return error state
            return {
                "handled": False,
                "is_validation_error": False,
                "fallback_message": None,
                "node_id_to_process": None,
                "current_node_id_for_service": existing_user.current_node_id,
                "validation_result": None,
                "error": str(e)
            }
    
    async def _update_delay_node_state(
        self,
        sender: str,
        brand_id: int,
        flow_id: str,
        channel: str,
        channel_account_id: Optional[str],
        next_node_id: Optional[str] = None,
        next_node_data: Optional[Dict[str, Any]] = None,
        validation_result: Optional[Dict[str, Any]] = None,
        fallback_message: Optional[str] = None,
        clear_delay_data: bool = False
    ) -> Dict[str, Any]:
        """
        Update user state with delay node data or clear delay node data.
        This function handles delay node processing separately.
        
        Args:
            sender: User identifier
            brand_id: Brand ID
            flow_id: Flow ID
            channel: Channel name
            channel_account_id: Channel account ID
            next_node_id: Delay node ID (required when saving, optional when clearing)
            next_node_data: Complete delay node data (required when saving, ignored when clearing)
            validation_result: Optional validation result (for validation state updates)
            fallback_message: Optional fallback message (for validation state updates)
            clear_delay_data: If True, clears delay_node_data instead of saving it
        
        Returns:
            Dict with status="success" and delay node information (or cleared status)
        """
        try:
            if clear_delay_data:
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"Clearing delay node data for user {sender}"
                )
            else:
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"Updating delay node state for node {next_node_id}"
                )
            
            # Convert delay node data to dict for storage (only if not clearing)
            delay_node_dict = None
            if not clear_delay_data and next_node_data:
                def _node_to_dict(node: Any) -> Dict[str, Any]:
                    if hasattr(node, "model_dump"):
                        return node.model_dump()
                    if isinstance(node, dict):
                        return node
                    return dict(node)
                
                delay_node_dict = _node_to_dict(next_node_data)
            
            # Update validation state if needed (for validation scenarios)
            if validation_result:
                if validation_result.get("status") == "mismatch_retry":
                    await self.flow_db.update_validation_state(
                        user_identifier=sender,
                        brand_id=brand_id,
                        validation_failed=True,
                        failure_message=fallback_message,
                        channel=channel,
                        channel_account_id=channel_account_id
                    )
                else:
                    await self.flow_db.update_validation_state(
                        user_identifier=sender,
                        brand_id=brand_id,
                        validation_failed=False,
                        failure_message=None,
                        channel=channel,
                        channel_account_id=channel_account_id
                    )
            
            # Update user automation state with complete delay node object or clear it
            # When clearing delay data, check if user is still in automation (may have exited if terminal node)
            # Get current user state to preserve is_in_automation if it was set to False
            current_user = await self.flow_db.get_user_data(
                user_identifier=sender,
                brand_id=brand_id,
                channel=channel,
                channel_account_id=channel_account_id
            )
            
            # If clearing delay data and user is not in automation, preserve that state
            # Otherwise, use the appropriate state (True when saving delay, preserve existing when clearing)
            is_in_automation_value = True
            if clear_delay_data and current_user and not current_user.is_in_automation:
                # User already exited automation (e.g., terminal node), preserve that state
                is_in_automation_value = False
                flow_id = None  # Also clear flow_id if exiting automation
                next_node_id = None  # Also clear current_node_id if exiting automation
            
            await self.flow_db.update_user_automation_state(
                user_identifier=sender,
                brand_id=brand_id,
                is_in_automation=is_in_automation_value,
                current_flow_id=flow_id if not clear_delay_data or is_in_automation_value else None,
                current_node_id=next_node_id if not clear_delay_data else None,  # Update to delay node ID when saving
                channel=channel,
                channel_account_id=channel_account_id,
                delay_node_data=None if clear_delay_data else delay_node_dict
            )
            
            # Save delay record to database for background scheduler (only when saving delay, not clearing)
            if not clear_delay_data and delay_node_dict:
                from models.delay_data import DelayData
                from datetime import timedelta
                
                delay_duration = delay_node_dict.get("delayDuration", 0)
                delay_unit = delay_node_dict.get("delayUnit", "minutes")
                wait_time_seconds = delay_node_dict.get("wait_time_seconds", 0)
                
                # Calculate wait_time_seconds if not provided
                if wait_time_seconds == 0:
                    if delay_unit == "seconds":
                        wait_time_seconds = delay_duration
                    elif delay_unit == "minutes":
                        wait_time_seconds = delay_duration * 60
                    elif delay_unit == "hours":
                        wait_time_seconds = delay_duration * 3600
                    elif delay_unit == "days":
                        wait_time_seconds = delay_duration * 86400
                
                delay_started_at = datetime.utcnow()
                delay_completes_at = delay_started_at + timedelta(seconds=wait_time_seconds)
                
                # Get delay_node_id from delay_node_dict
                delay_node_id = delay_node_dict.get("id") if delay_node_dict else next_node_id
                if not delay_node_id:
                    self.log_util.error(
                        service_name="UserStateService",
                        message=f"Cannot save delay record: delay_node_id is missing"
                    )
                else:
                    delay_record = DelayData(
                        user_identifier=sender,
                        brand_id=brand_id,
                        flow_id=flow_id,
                        delay_node_id=delay_node_id,
                        delay_node_data=delay_node_dict,
                        delay_duration=delay_duration,
                        delay_unit=delay_unit,
                        wait_time_seconds=wait_time_seconds,
                        delay_started_at=delay_started_at,
                        delay_completes_at=delay_completes_at,
                        channel=channel,
                        channel_account_id=channel_account_id
                    )
                    
                    saved_delay = await self.flow_db.save_delay(delay_record)
                    if saved_delay:
                        self.log_util.info(
                            service_name="UserStateService",
                            message=f"Delay record saved with ID: {saved_delay.id}, completes at: {delay_completes_at}"
                        )
                    else:
                        self.log_util.warning(
                            service_name="UserStateService",
                            message=f"Failed to save delay record for node {delay_node_id}"
                        )
            
            if clear_delay_data:
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"Successfully cleared delay node data for user {sender}"
                )
                return {
                    "status": "success",
                    "message": "Delay node data cleared successfully"
                }
            else:
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"Successfully updated delay node state for node {next_node_id}"
                )
                return {
                    "status": "success",
                    "message": "Delay node state updated successfully",
                    "delay_node_id": next_node_id,
                    "delay_node_data": delay_node_dict
                }
            
        except Exception as e:
            self.log_util.error(
                service_name="UserStateService",
                message=f"Error updating delay node state: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="UserStateService",
                message=f"Traceback: {traceback.format_exc()}"
            )
            return {
                "status": "error",
                    "message": f"Error updating delay node state: {str(e)}"
                }
    
    async def _handle_delay_interrupt(
        self,
        metadata: "WebhookMetadata",
        data: Dict[str, Any],
        existing_user: "UserData",
        sender: str,
        brand_id: int,
        channel: str,
        channel_account_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Handle user reply when user is in delay state.
        Checks delayInterrupt flag and processes interrupted/not interrupted paths accordingly.
        
        Args:
            metadata: WebhookMetadata
            data: Webhook data
            existing_user: UserData with delay_node_data
            sender: User identifier
            brand_id: Brand ID
            channel: Channel name
            channel_account_id: Channel account ID
        
        Returns:
            Dict with status and processing result
        """
        try:
            delay_node_data = existing_user.delay_node_data
            if not delay_node_data:
                self.log_util.error(
                    service_name="UserStateService",
                    message=f"[DELAY_INTERRUPT] User {sender} has no delay_node_data"
                )
                return {
                    "status": "error",
                    "message": "No delay node data found"
                }
            
            # Check delayInterrupt flag
            delay_interrupt = delay_node_data.get("delayInterrupt", False)
            
            self.log_util.info(
                service_name="UserStateService",
                message=f"[DELAY_INTERRUPT] User {sender} sent message during delay. delayInterrupt={delay_interrupt}"
            )
            
            # Get delayResult array
            delay_result = delay_node_data.get("delayResult", [])
            if not delay_result or not isinstance(delay_result, list):
                self.log_util.error(
                    service_name="UserStateService",
                    message=f"[DELAY_INTERRUPT] delayResult is missing or invalid in delay_node_data"
                )
                return {
                    "status": "error",
                    "message": "Invalid delayResult in delay_node_data"
                }
            
            # Extract delay result IDs (the id field, not nodeResultId)
            # These IDs are used as source_node_id in edges (e.g., "delay-node-xxx__interrupted" or "delay-node-xxx__not_interrupted")
            interrupted_node_id = None
            not_interrupted_node_id = None
            for item in delay_result:
                if isinstance(item, dict):
                    item_id = item.get("id", "")
                    if "__interrupted" in item_id:
                        interrupted_node_id = item_id  # Use the delay result ID itself, not nodeResultId
                    elif "__not_interrupted" in item_id:
                        not_interrupted_node_id = item_id  # Use the delay result ID itself, not nodeResultId
            
            # Handle based on delayInterrupt flag
            if delay_interrupt:
                # Interrupt enabled - process interrupted path
                if not interrupted_node_id:
                    self.log_util.error(
                        service_name="UserStateService",
                        message=f"[DELAY_INTERRUPT] delayInterrupt=true but interruptedNodeId is missing"
                    )
                    return {
                        "status": "error",
                        "message": "interruptedNodeId not found in delayResult"
                    }
                
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"[DELAY_INTERRUPT] Delay interrupted by user message, processing interruptedNodeId: {interrupted_node_id}"
                )
                
                # Cancel delay record in database
                # Find delay record by user_identifier, flow_id, and delay_node_id
                delay_node_id = delay_node_data.get("id")
                if delay_node_id:
                    # Get all pending delays for this user
                    from models.delay_data import DelayData
                    client_data = self.flow_db._get_client_for_current_loop()
                    try:
                        from bson import ObjectId
                        # Find delay record
                        delay_record = await client_data['collections']['delays'].find_one({
                            "user_identifier": sender,
                            "brand_id": brand_id,
                            "flow_id": existing_user.current_flow_id,
                            "delay_node_id": delay_node_id,
                            "processed": False
                        })
                        
                        if delay_record:
                            # Mark as processed (cancelled)
                            await client_data['collections']['delays'].update_one(
                                {"_id": delay_record["_id"]},
                                {
                                    "$set": {
                                        "processed": True,
                                        "updated_at": datetime.utcnow()
                                    }
                                }
                            )
                            self.log_util.info(
                                service_name="UserStateService",
                                message=f"[DELAY_INTERRUPT] Cancelled delay record {delay_record['_id']}"
                            )
                    except Exception as e:
                        self.log_util.warning(
                            service_name="UserStateService",
                            message=f"[DELAY_INTERRUPT] Error cancelling delay record: {str(e)}"
                        )
                
                # Process interrupted path
                node_service_response = await self.node_identification_service.identify_and_process_node(
                    metadata=metadata,
                    data=data,
                    is_validation_error=False,
                    fallback_message=None,
                    node_id_to_process=None,
                    current_node_id=interrupted_node_id,
                    flow_id=existing_user.current_flow_id,
                    user_detail=existing_user.user_detail.model_dump() if existing_user.user_detail else None,
                    lead_id=existing_user.lead_id if existing_user else None
                )
                
                if node_service_response.get("status") == "success":
                    next_node_id = node_service_response.get("next_node_id")
                    if next_node_id:
                        # Handle successful node processing
                        processed_value = node_service_response.get("processed_value")
                        await self._handle_successful_node_processing(
                            metadata=metadata,
                            data=data,
                            next_node_id=next_node_id,
                            flow_id=existing_user.current_flow_id,
                            sender=sender,
                            brand_id=brand_id,
                            channel=channel,
                            channel_account_id=channel_account_id,
                            validation_result=None,
                            fallback_message=None,
                            processed_value=processed_value
                        )
                        
                        # Clear delay_node_data after processing interrupted path
                        await self._update_delay_node_state(
                            sender=sender,
                            brand_id=brand_id,
                            flow_id=existing_user.current_flow_id,
                            channel=channel,
                            channel_account_id=channel_account_id,
                            clear_delay_data=True
                        )
                        
                        self.log_util.info(
                            service_name="UserStateService",
                            message=f"[DELAY_INTERRUPT] Successfully processed interrupted path, cleared delay_node_data"
                        )
                        
                        return {
                            "status": "success",
                            "message": "Delay interrupted and processed successfully",
                            "node_id": next_node_id
                        }
                    else:
                        return {
                            "status": "error",
                            "message": "Node service returned success but no next_node_id"
                        }
                else:
                    return {
                        "status": "error",
                        "message": f"Node service failed: {node_service_response.get('message')}"
                    }
            
            else:
                # Interrupt disabled - skip processing webhook data, delay continues
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"[DELAY_INTERRUPT] delayInterrupt=false, skipping webhook processing. Delay will continue until completion."
                )
                
                return {
                    "status": "ignored",
                    "message": "User message ignored - delay continues (delayInterrupt=false)"
                }
        
        except Exception as e:
            self.log_util.error(
                service_name="UserStateService",
                message=f"[DELAY_INTERRUPT] Error handling delay interrupt: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="UserStateService",
                message=f"[DELAY_INTERRUPT] Traceback: {traceback.format_exc()}"
            )
            return {
                "status": "error",
                "message": f"Error handling delay interrupt: {str(e)}"
            }
    
    async def _handle_successful_node_processing(
        self,
        metadata: "WebhookMetadata",
        data: Dict[str, Any],
        next_node_id: str,
        flow_id: str,
        sender: str,
        brand_id: int,
        channel: str,
        channel_account_id: Optional[str],
        validation_result: Optional[Dict[str, Any]] = None,
        fallback_message: Optional[str] = None,
        processed_value: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Handle successful node processing when is_validation_error = False.
        
        Logic:
        1. Check if processed node is user input type or delay type
           - If yes: Update user state DB
        2. If not user input or delay:
           - Check if processed node is terminal node (no outgoing edges)
           - If terminal: Update user state with is_in_automation = False
           - If not terminal: Recursively call node identification service with processed node as current_node_id
        
        Args:
            metadata: WebhookMetadata
            data: Webhook data
            next_node_id: Processed node ID
            flow_id: Flow ID
            sender: User identifier
            brand_id: Brand ID
            channel: Channel name
            channel_account_id: Channel account ID
            validation_result: Optional validation result (for validation state updates)
            fallback_message: Optional fallback message (for validation state updates)
        """
        try:
            # Get flow to check node type and edges
            flow = await self.flow_db.get_flow_by_id(flow_id)
            if not flow:
                self.log_util.error(
                    service_name="UserStateService",
                    message=f"Flow {flow_id} not found for node processing"
                )
                return
            
            # Get next node data
            def _node_to_dict(node: Any) -> Dict[str, Any]:
                if hasattr(node, "model_dump"):
                    return node.model_dump()
                if isinstance(node, dict):
                    return node
                return dict(node)
            
            next_node_data = None
            for node in flow.flowNodes:
                node_dict = _node_to_dict(node)
                if node_dict.get("id") == next_node_id:
                    next_node_data = node_dict
                    break
            
            if not next_node_data:
                self.log_util.error(
                    service_name="UserStateService",
                    message=f"Next node {next_node_id} not found in flow"
                )
                return
            
            # Get node type
            next_node_type = next_node_data.get("type")
            
            # Check if node is condition or delay (processed by internal node service)
            if next_node_type == "condition" and processed_value:
                # Condition node - use processed_value (yes/no node ID) as current_node_id for next call
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"Condition node processed, using processed_value {processed_value} as next node"
                )
                
                # Call node identification service with processed_value as current_node_id
                # Note: user_detail not available in this recursive call context
                node_service_response = await self.node_identification_service.identify_and_process_node(
                    metadata=metadata,
                    data=data,
                    is_validation_error=False,
                    fallback_message=None,
                    node_id_to_process=None,
                    current_node_id=processed_value,  # Use yes/no node ID from condition
                    flow_id=flow_id,
                    user_detail=None,  # Not available in recursive condition node processing
                    lead_id=None  # Not available in recursive condition node processing
                )
                
                if node_service_response.get("status") == "success":
                    next_next_node_id = node_service_response.get("next_node_id")
                    if next_next_node_id:
                        # Recursively handle successful node processing
                        next_processed_value = node_service_response.get("processed_value")
                        recursive_result = await self._handle_successful_node_processing(
                            metadata=metadata,
                            data=data,
                            next_node_id=next_next_node_id,
                            flow_id=flow_id,
                            sender=sender,
                            brand_id=brand_id,
                            channel=channel,
                            channel_account_id=channel_account_id,
                            validation_result=validation_result,
                            fallback_message=fallback_message,
                            processed_value=next_processed_value
                        )
                        # Return recursive result (may be delay node response)
                        return recursive_result
                return None
            
            # Check if node is delay type
            if next_node_type == "delay" and processed_value:
                # Delay node - use separate function to update delay node state
                delay_update_result = await self._update_delay_node_state(
                    sender=sender,
                            brand_id=brand_id,
                    flow_id=flow_id,
                            channel=channel,
                    channel_account_id=channel_account_id,
                    next_node_id=next_node_id,
                    next_node_data=next_node_data,
                    validation_result=validation_result,
                    fallback_message=fallback_message,
                    clear_delay_data=False
                )
                
                # Return success response (will be sent back to webhook service)
                return delay_update_result
            
            # Check if node is user input type or delay type
            node_detail = await self.flow_db.get_node_detail_by_id(next_node_type)
            is_user_input = False
            is_delay = False
            
            if node_detail:
                is_user_input = node_detail.user_input_required
                is_delay = (next_node_type == "delay")
            else:
                # Fallback check
                is_user_input = next_node_type in ("button_question", "list_question", "question", "trigger_template")
                is_delay = (next_node_type == "delay")
            
            if is_user_input or is_delay:
                # Update user state DB
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"Processed node {next_node_id} is user input or delay type, updating user state"
                )
                
                # Update validation state if needed (for validation scenarios)
                if validation_result:
                    if validation_result.get("status") == "mismatch_retry":
                        await self.flow_db.update_validation_state(
                            user_identifier=sender,
                            brand_id=brand_id,
                            validation_failed=True,
                            failure_message=fallback_message,
                            channel=channel,
                            channel_account_id=channel_account_id
                        )
                    else:
                        await self.flow_db.update_validation_state(
                            user_identifier=sender,
                            brand_id=brand_id,
                            validation_failed=False,
                            failure_message=None,
                            channel=channel,
                            channel_account_id=channel_account_id
                        )
                
                # Update user automation state
                await self.flow_db.update_user_automation_state(
                    user_identifier=sender,
                    brand_id=brand_id,
                    is_in_automation=True,
                    current_flow_id=flow_id,
                    current_node_id=next_node_id,
                    channel=channel,
                    channel_account_id=channel_account_id
                )
                
                # Return success response
                return {
                    "status": "success",
                    "message": f"User state updated for node {next_node_id}",
                    "node_id": next_node_id
                }
            else:
                # Not user input or delay - check if terminal node
                edges = await self.flow_db.get_flow_edges(flow_id)
                is_terminal = True
                
                # Check if node has outgoing edges
                # Edges are objects with source_node_id and target_node_id attributes
                for edge in edges:
                    # Edge objects have source_node_id as an attribute, not in a dict
                    source_node_id = edge.source_node_id if hasattr(edge, 'source_node_id') else None
                    if source_node_id == next_node_id:
                        is_terminal = False
                        break

                if is_terminal:
                    # Terminal node - exit automation
                    self.log_util.info(
                        service_name="UserStateService",
                        message=f"Processed node {next_node_id} is terminal node, exiting automation"
                    )
                    
                    await self.flow_db.update_user_automation_state(
                        user_identifier=sender,
                        brand_id=brand_id,
                        is_in_automation=False,
                        current_flow_id=None,
                        current_node_id=None,
                        channel=channel,
                        channel_account_id=channel_account_id
                    )
                else:
                    # Not terminal - recursively call node identification service
                    self.log_util.info(
                        service_name="UserStateService",
                        message=f"Processed node {next_node_id} is not terminal, processing next node"
                    )
                    
                    # Note: user_detail not available in this recursive call context
                    node_service_response = await self.node_identification_service.identify_and_process_node(
                        metadata=metadata,
                        data=data,
                        is_validation_error=False,
                        fallback_message=None,
                        node_id_to_process=None,
                        current_node_id=next_node_id,  # Use processed node as current node
                        flow_id=flow_id,
                        user_detail=None,  # Not available in recursive processing
                        lead_id=None  # Not available in recursive processing
                    )
                    
                    # Handle the response recursively
                    if node_service_response.get("status") == "success":
                        next_next_node_id = node_service_response.get("next_node_id")
                        if next_next_node_id:
                            # Recursively handle successful node processing
                            processed_value = node_service_response.get("processed_value")
                            try:
                                recursive_result = await self._handle_successful_node_processing(
                                    metadata=metadata,
                                    data=data,
                                    next_node_id=next_next_node_id,
                                    flow_id=flow_id,
                                    sender=sender,
                                    brand_id=brand_id,
                                    channel=channel,
                                    channel_account_id=channel_account_id,
                                    validation_result=None,
                                    fallback_message=None,
                                    processed_value=processed_value
                                )
                                # Return recursive result (may be delay node response)
                                return recursive_result
                            except Exception as e:
                                self.log_util.error(
                                    service_name="UserStateService",
                                    message=f"Error handling successful node processing: {str(e)}"
                                )
                                return {
                                    "status": "error",
                                    "message": f"Error handling successful node processing: {str(e)}"
                                }
        except Exception as e:
            self.log_util.error(
                service_name="UserStateService",
                message=f"Error in _handle_successful_node_processing: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="UserStateService",
                message=f"Traceback: {traceback.format_exc()}"
            )
            return {
                "status": "error",
                "message": f"Error in _handle_successful_node_processing: {str(e)}"
            }
    
    def _get_status_for_webhook(
        self,
        status: str,
        message: str,
        flow_id: Optional[str] = None,
        trigger_node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create status response to send back to WebhookService.
        Handles all scenarios: triggered, no_trigger, in_automation, etc.
        
        Args:
            status: Status type ("triggered", "no_trigger", "in_automation", "error", etc.)
            message: Status message
            flow_id: Flow ID if applicable
            trigger_node_id: Trigger node ID if applicable
        
        Returns:
            Dict with status information for WebhookService
        """
        if status == "no_trigger":
            return {
                "status": "no_trigger",
                "message": "No trigger matched",
                "flow_id": None,
                "trigger_node_id": None
            }
        # TODO: Add other status cases as needed
        return {
            "status": status,
            "message": message,
            "flow_id": flow_id,
            "trigger_node_id": trigger_node_id
        }
    
    async def _check_triggers_and_initiate_flow(
        self,
        metadata: "WebhookMetadata",
        data: Dict[str, Any],
        sender: str,
        brand_id: int,
        user_id: int,
        channel: str,
        channel_account_id: Optional[str],
        existing_user: Optional["UserData"] = None
    ) -> Dict[str, Any]:
        """
        Common function to check triggers and initiate flow for users not in automation.
        Used for both new users and existing users not in automation.
        
        Args:
            metadata: Webhook metadata
            data: Webhook data
            sender: User identifier
            brand_id: Brand ID
            user_id: User ID
            channel: Channel name
            channel_account_id: Channel account ID
            existing_user: Existing user data (None for new users)
        
        Returns:
            Dict with status information for WebhookService
        """
        if not self.trigger_identification_service:
            self.log_util.warning(
                service_name="UserStateService",
                message=f"⚠️ TriggerIdentificationService is not initialized, cannot check triggers"
            )
            return self._get_status_for_webhook(
                status="error",
                message="TriggerIdentificationService not initialized"
            )
        
        # Use existing_user's channel_account_id if available, otherwise use provided one
        final_channel_account_id = channel_account_id
        if existing_user and existing_user.channel_account_id:
            final_channel_account_id = existing_user.channel_account_id
        
        trigger_result = await self.trigger_identification_service.identify_and_initiate_trigger_flow(
            metadata=metadata,
            data=data,
            channel_account_id=final_channel_account_id,
            existing_user=existing_user
        )
        
        # If trigger matched, call node service first
        if trigger_result.get("status") == "triggered":
            flow_id = trigger_result.get("flow_id")
            trigger_node_id = trigger_result.get("trigger_node_id")
            
            if flow_id and trigger_node_id:
                user_type = "EXISTING_USER" if existing_user else "NEW_USER"
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"[{user_type}] Trigger matched! Calling node service with trigger_node_id: {trigger_node_id}"
                )
                
                # Step 1: Call node service first (don't update user state yet)
                # - node_id_to_process = null (node service identifies next node from trigger node)
                # - current_node_id = trigger_node_id
                user_detail_dict = None
                if existing_user and existing_user.user_detail:
                    user_detail_dict = existing_user.user_detail.model_dump()
                
                # Get lead_id from existing_user if available
                lead_id_for_trigger = existing_user.lead_id if existing_user and hasattr(existing_user, 'lead_id') else None
                
                node_service_response = await self.node_identification_service.identify_and_process_node(
                    metadata=metadata,
                    data=data,
                    is_validation_error=False,
                    fallback_message=None,
                    node_id_to_process=None,
                    current_node_id=trigger_node_id,
                    flow_id=flow_id,
                    user_detail=user_detail_dict,
                    lead_id=lead_id_for_trigger
                )

                # Step 2: Check node service response
                if node_service_response.get("status") == "success":
                    next_node_id = node_service_response.get("next_node_id")
                    if next_node_id:
                        self.log_util.info(
                            service_name="UserStateService",
                            message=f"[{user_type}] Node service processed successfully, next_node_id: {next_node_id}"
                        )
                        
                        # Step 3: Handle successful node processing (is_validation_error = False)
                        processed_value = node_service_response.get("processed_value")
                        await self._handle_successful_node_processing(
                            metadata=metadata,
                            data=data,
                            next_node_id=next_node_id,
                            flow_id=flow_id,
                            sender=sender,
                            brand_id=brand_id,
                            channel=channel,
                            channel_account_id=final_channel_account_id,
                            validation_result=None,
                            fallback_message=None,
                            processed_value=processed_value
                        )
                        
                        # Step 4: Return status to WebhookService
                        return self._get_status_for_webhook(
                            status="triggered",
                            message="Trigger matched and flow initiated",
                            flow_id=flow_id,
                            trigger_node_id=trigger_node_id
                        )
                else:
                    # Node service failed
                    self.log_util.error(
                        service_name="UserStateService",
                        message=f"[{user_type}] Node service failed: {node_service_response.get('message')}"
                    )
                    return self._get_status_for_webhook(
                        status="error",
                        message=f"Node processing failed: {node_service_response.get('message')}",
                        flow_id=flow_id,
                        trigger_node_id=trigger_node_id
                    )
            else:
                # No trigger matched
                return self._get_status_for_webhook(
                    status="no_trigger",
                    message="No trigger matched"
                )
            
    async def check_and_process_user_with_flow(
        self,
        metadata: "WebhookMetadata",
        data: Dict[str, Any],
        channel_account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check/create user and process flow automation based on user state.
        
        Flow:
        1. If user doesn't exist: create user → check triggers → if match, call node service with trigger_node_id
        2. If user exists and in automation:
           - Check if delay_complete webhook → call node service with current_node_id (delay node)
           - Otherwise: check if current node has expected reply → call validation service → call node service
        3. If user exists but not in automation: check triggers → if match, call node service
        
        Args:
            metadata: WebhookMetadata from saved webhook
            data: Normalized data from saved webhook
            channel_account_id: Channel account ID
        """
        try:
            sender = metadata.sender
            brand_id = metadata.brand_id
            user_id = metadata.user_id
            channel = metadata.channel
            message_type = metadata.message_type
            
            # For delay_complete webhooks, extract user_identifier from data if sender is "system"
            # This handles cases where delay webhook was created with sender="system"
            if message_type == "delay_complete":
                user_state_id = data.get("user_state_id")
                if user_state_id:
                    # Use user_state_id from data instead of sender
                    sender = user_state_id
                    self.log_util.info(
                        service_name="UserStateService",
                        message=f"[DELAY_COMPLETE] Using user_state_id from data: {user_state_id}"
                    )
            
            existing_user = await self.flow_db.get_user_data(
                user_identifier=sender,
                brand_id=brand_id,
                channel=channel,
                channel_account_id=channel_account_id
            )

            if existing_user is None:
                # ========== SCENARIO 1: NEW USER (NOT IN AUTOMATION) ==========
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"[NEW_USER] Creating new user: {sender}, brand_id: {brand_id}"
                )
                
                # Step 1: Create user_detail based on channel
                user_detail = UserDetail()
                user_detail.set_identifier(channel, sender)
                
                # Step 2: Get or create lead in lead management service
                # Extract phone and email from user_detail
                phone = user_detail.phone_number
                email = user_detail.email
                
                # Extract additional user info from data if available
                first_name = data.get("first_name") or data.get("firstName")
                last_name = data.get("last_name") or data.get("lastName")
                address = data.get("address")
                
                # Get or create lead
                lead_id = await self.lead_management_service.get_or_create_lead(
                    phone=phone,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    address=address,
                    brand_id=brand_id,
                    user_id=user_id
                )
                
                if not lead_id:
                    self.log_util.warning(
                        service_name="UserStateService",
                        message=f"Failed to get/create lead for user: {sender}, brand_id: {brand_id}. Continuing without lead_id."
                    )
                else:
                    self.log_util.info(
                        service_name="UserStateService",
                        message=f"Got lead_id: {lead_id} for user: {sender}"
                    )
                
                # Step 3: Create user in user state with lead_id
                new_user = UserData(
                    user_detail=user_detail,
                    brand_id=brand_id,
                    user_id=user_id,
                    lead_id=lead_id,
                    channel=channel,
                    channel_account_id=channel_account_id
                )
                saved_user = await self.flow_db.save_user_data(new_user)
                if not saved_user:
                    self.log_util.error(
                        service_name="UserStateService",
                        message=f"Failed to create user record for user: {sender}, brand_id: {brand_id}"
                    )
                    return self._get_status_for_webhook(
                        status="error",
                        message=f"Failed to create user record for user: {sender}"
                    )
                
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"Created new user record for user: {sender}, brand_id: {brand_id}, lead_id: {lead_id}"
                )
                
                # Check for triggers and initiate flow if matched (new user, not in automation)
                # Pass saved_user (which contains lead_id) as existing_user for trigger flow
                return await self._check_triggers_and_initiate_flow(
                    metadata=metadata,
                    data=data,
                    sender=sender,
                    brand_id=brand_id,
                    user_id=user_id,
                    channel=channel,
                    channel_account_id=channel_account_id,
                    existing_user=saved_user  # Pass saved_user which contains lead_id
                )
            else:
                # ========== SCENARIO 2: EXISTING USER ==========
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"[EXISTING_USER] Processing existing user {sender}, is_in_automation: {existing_user.is_in_automation}, current_flow_id: {existing_user.current_flow_id}, current_node_id: {existing_user.current_node_id}"
                )
                
                # Handle delay_complete webhooks - check if user has delay_node_data
                if message_type == "delay_complete":
                    if not existing_user.delay_node_data:
                        self.log_util.warning(
                            service_name="UserStateService",
                            message=f"[EXISTING_USER] Delay complete webhook received but user {sender} has no delay_node_data. User may have exited automation or delay was already processed. Skipping."
                        )
                        return
                    
                    # User must be in automation for delay_complete to be valid
                    if not existing_user.is_in_automation or not existing_user.current_flow_id:
                        self.log_util.warning(
                            service_name="UserStateService",
                            message=f"[EXISTING_USER] Delay complete webhook received but user {sender} is not in automation or has no current_flow_id. Skipping."
                        )
                        return
                
                if (
                    existing_user.is_in_automation
                    and existing_user.current_flow_id
                    and (existing_user.current_node_id or message_type == "delay_complete")  # Allow delay_complete even if current_node_id is None
                ):
                    # ========== USER IN AUTOMATION ==========
                    self.log_util.info(
                        service_name="UserStateService",
                        message=f"[EXISTING_USER] User is in automation, flow_id: {existing_user.current_flow_id}, current_node_id: {existing_user.current_node_id}"
                    )
                    
                    # Check if user is in delay state and has delay_node_data
                    if existing_user.delay_node_data and message_type != "delay_complete":
                        # User is in delay state and sent a message - check for interrupt
                        return await self._handle_delay_interrupt(
                            metadata=metadata,
                            data=data,
                            existing_user=existing_user,
                            sender=sender,
                            brand_id=brand_id,
                            channel=channel,
                            channel_account_id=channel_account_id
                    )
                    
                    # Check if delay_complete webhook
                    if message_type == "delay_complete":
                        # ========== DELAY COMPLETE WEBHOOK ==========
                        self.log_util.info(
                            service_name="UserStateService",
                            message=f"[EXISTING_USER] Delay complete webhook received, processing next node"
                        )
                        
                        # Validate delay node exists in user state
                        if not existing_user.delay_node_data:
                            self.log_util.warning(
                                service_name="UserStateService",
                                message=f"[EXISTING_USER] Cannot process delay_complete webhook: delay_node_data is missing in user state. User may have exited automation or delay was already processed."
                            )
                            return
                        
                        # Get delay node ID from webhook data to validate it matches user state
                        delay_node_id_from_webhook = data.get("node_id") or (data.get("user_state_id") and None)  # Will be in original_message_body
                        # Note: delay_node_id is in original_message_body, not in normalized data
                        # We'll validate by checking if delay_node_data exists and has the expected structure
                        
                        delay_result = existing_user.delay_node_data.get("delayResult")
                        if not delay_result or not isinstance(delay_result, list):
                            self.log_util.error(
                                service_name="UserStateService",
                                message=f"[EXISTING_USER] Cannot process delay_complete webhook: delayResult is missing or invalid in delay_node_data"
                            )
                            return
                        
                        # Extract notInterruptedNodeId from array format
                        # Should use delay result ID (e.g., "delay-node-xxx__not_interrupted") not nodeResultId
                        current_node_id_for_delay = None
                        for item in delay_result:
                            if isinstance(item, dict):
                                item_id = item.get("id", "")
                                if "__not_interrupted" in item_id:
                                    # Use the delay result ID itself (e.g., "delay-node-xxx__not_interrupted")
                                    # This is used as source_node_id in edges
                                    current_node_id_for_delay = item_id
                                    break
                        
                        if not current_node_id_for_delay:
                            self.log_util.error(
                                service_name="UserStateService",
                                message=f"[EXISTING_USER] Cannot process delay_complete webhook: __not_interrupted result ID is missing in delayResult"
                            )
                            return
                        
                        self.log_util.info(
                            service_name="UserStateService",
                            message=f"[EXISTING_USER] Extracted notInterruptedNodeId from delay_node_data: {current_node_id_for_delay}"
                        )
                        
                        # Step 1: Call node service with:
                        # - node_id_to_process = null (node service identifies next node from delay node)
                        # - current_node_id = notInterruptedNodeId from delay_node_data
                        node_service_response = await self.node_identification_service.identify_and_process_node(
                            metadata=metadata,
                            data=data,
                            is_validation_error=False,
                            fallback_message=None,
                            node_id_to_process=None,
                            current_node_id=current_node_id_for_delay,
                            flow_id=existing_user.current_flow_id,
                            user_detail=None,
                            lead_id=existing_user.lead_id if existing_user and hasattr(existing_user, 'lead_id') else None
                        )
                        
                        # Step 2: Update user state based on node service response
                        if node_service_response.get("status") == "success":
                            next_node_id = node_service_response.get("next_node_id")
                            if next_node_id:
                                # Handle successful node processing (is_validation_error = False)
                                processed_value = node_service_response.get("processed_value")
                                await self._handle_successful_node_processing(
                                    metadata=metadata,
                                    data=data,
                                    next_node_id=next_node_id,
                                    flow_id=existing_user.current_flow_id,
                                    sender=sender,
                                    brand_id=brand_id,
                                    channel=channel,
                                    channel_account_id=existing_user.channel_account_id,
                                    validation_result=None,
                                    fallback_message=None,
                                    processed_value=processed_value
                                )
                                
                                # Step 3: Clear delay_node_data after successful next node processing
                                await self._update_delay_node_state(
                                    sender=sender,
                                    brand_id=brand_id,
                                    flow_id=existing_user.current_flow_id,
                                    channel=channel,
                                    channel_account_id=existing_user.channel_account_id,
                                    clear_delay_data=True
                                )
                                
                                # Mark delay record as processed in database
                                # Find delay record by user_identifier, flow_id, and delay_node_id
                                from models.delay_data import DelayData
                                # Note: We'll mark it as processed when delay_complete webhook is sent
                                # This is handled by the delay scheduler service
                                
                                self.log_util.info(
                                    service_name="UserStateService",
                                    message=f"[EXISTING_USER] Delay complete processed successfully, cleared delay_node_data, next_node_id: {next_node_id}"
                                )
                        else:
                            self.log_util.error(
                                service_name="UserStateService",
                                message=f"[EXISTING_USER] Node service failed for delay webhook: {node_service_response.get('message')}"
                            )
                    else:
                        # ========== REGULAR REPLY - CHECK VALIDATION ==========
                        # Extract user reply from data
                        user_reply = data.get("user_reply")
                        
                        if not user_reply:
                            self.log_util.warning(
                                service_name="UserStateService",
                                message=f"[EXISTING_USER] Could not extract user reply from data"
                            )
                            return
                        
                        # Get flow to check if current node has expected reply
                        flow = await self.flow_db.get_flow_by_id(existing_user.current_flow_id)
                        if not flow:
                            self.log_util.error(
                                service_name="UserStateService",
                                message=f"[EXISTING_USER] ❌ Failed to retrieve flow with id: {existing_user.current_flow_id}"
                            )
                            return
                        
                        # Check if current node has expected reply using node_details database
                        def _node_to_dict(node: Any) -> Dict[str, Any]:
                            if hasattr(node, "model_dump"):
                                return node.model_dump()
                            if isinstance(node, dict):
                                return node
                            return dict(node)
                        
                        current_node = None
                        for node in flow.flowNodes:
                            node_dict = _node_to_dict(node)
                            if node_dict.get("id") == existing_user.current_node_id:
                                current_node = node_dict
                                break
                        
                        if not current_node:
                            self.log_util.error(
                                service_name="UserStateService",
                                message=f"[EXISTING_USER] ❌ Current node {existing_user.current_node_id} not found in flow"
                            )
                            return
                        
                        # Get node type from current node
                        node_type = current_node.get("type")
                        
                        # Get node detail from database to check if it requires user input
                        node_detail = await self.flow_db.get_node_detail_by_id(node_type)
                        has_expected_reply = False
                        is_text = False
                        
                        if node_detail:
                            has_expected_reply = node_detail.user_input_required
                            # Check if node type is "question" (text question)
                            is_text = (node_type == "question")
                        else:
                            # Fallback: if node_detail not found, check node type directly
                            self.log_util.warning(
                                service_name="UserStateService",
                                message=f"[EXISTING_USER] Node detail not found for node_type: {node_type}, using fallback check"
                            )
                            has_expected_reply = node_type in ("button_question", "list_question", "trigger_template")
                            is_text = (node_type == "question")
                        
                        if has_expected_reply:
                            # ========== CURRENT NODE HAS EXPECTED REPLY - CALL VALIDATION SERVICE ==========
                            validation_params = await self._process_validation_and_get_node_service_params(
                                metadata=metadata,
                                data=data,
                                existing_user=existing_user,
                                flow=flow,
                                current_node=current_node,
                                node_type=node_type,
                                is_text=is_text,
                                sender=sender,
                                        brand_id=brand_id,
                                        channel=channel,
                                        channel_account_id=existing_user.channel_account_id
                                    )
                            
                            # Check if validation_exit was handled (automation exited)
                            if validation_params.get("handled"):
                                # Validation limit exceeded, automation already exited
                                    return
                            
                            # Extract parameters for node identification service
                            is_validation_error = validation_params.get("is_validation_error", False)
                            fallback_message = validation_params.get("fallback_message")
                            node_id_to_process = validation_params.get("node_id_to_process")
                            current_node_id_for_service = validation_params.get("current_node_id_for_service")
                            validation_result = validation_params.get("validation_result")
                            
                            if not current_node_id_for_service:
                                self.log_util.error(
                                    service_name="UserStateService",
                                    message=f"[EXISTING_USER] Cannot proceed: current_node_id_for_service is None/empty"
                                    )
                                return
                            
                            self.log_util.info(
                                service_name="UserStateService",
                                message=f"[EXISTING_USER] Calling NodeIdentificationService with: current_node_id={current_node_id_for_service}, node_id_to_process={node_id_to_process}, is_validation_error={is_validation_error}"
                            )
                            
                            user_detail_dict = existing_user.user_detail.model_dump() if existing_user.user_detail else None
                            node_service_response = await self.node_identification_service.identify_and_process_node(
                                metadata=metadata,
                                data=data,
                                is_validation_error=is_validation_error,
                                fallback_message=fallback_message,
                                node_id_to_process=node_id_to_process,
                                current_node_id=current_node_id_for_service,
                                flow_id=flow.id,
                                user_detail=user_detail_dict,
                                lead_id=existing_user.lead_id if existing_user and hasattr(existing_user, 'lead_id') else None
                            )
                            
                            # Step 2: Update user state based on node service response (only after successful node processing)
                            if node_service_response.get("status") == "success":
                                next_node_id = node_service_response.get("next_node_id")
                                if next_node_id:
                                    # Use _handle_successful_node_processing for all cases (it handles both validation_error and normal cases)
                                    processed_value = node_service_response.get("processed_value")
                                    node_processing_result = await self._handle_successful_node_processing(
                                        metadata=metadata,
                                        data=data,
                                        next_node_id=next_node_id,
                                        flow_id=flow.id,
                                        sender=sender,
                                        brand_id=brand_id,
                                        channel=channel,
                                        channel_account_id=existing_user.channel_account_id,
                                        validation_result=validation_result,
                                        fallback_message=fallback_message,
                                            processed_value=processed_value
                                    )
                                    
                                    # If delay node was processed, return the delay response to webhook service
                                    if node_processing_result and node_processing_result.get("status") == "success" and node_processing_result.get("delay_node_id"):
                                        return self._get_status_for_webhook(
                                            status="triggered",
                                            message=node_processing_result.get("message", "Delay node processed successfully"),
                                            flow_id=flow.id
                                        )
                            else:
                                self.log_util.error(
                                    service_name="UserStateService",
                                    message=f"[EXISTING_USER] Node service failed: {node_service_response.get('message')}"
                                )
                        else:
                            # ========== CURRENT NODE HAS NO EXPECTED REPLY - CALL NODE SERVICE DIRECTLY ==========
                            self.log_util.info(
                                service_name="UserStateService",
                                message=f"[EXISTING_USER] Current node has no expected reply, calling node service directly"
                            )
                            
                            # Step 1: Call node service with:
                            # - node_id_to_process = null (node service identifies next node via default edge)
                            # - current_node_id = current node ID
                            user_detail_dict = existing_user.user_detail.model_dump() if existing_user.user_detail else None
                            node_service_response = await self.node_identification_service.identify_and_process_node(
                                metadata=metadata,
                                data=data,
                                is_validation_error=False,
                                fallback_message=None,
                                node_id_to_process=None,
                                current_node_id=existing_user.current_node_id,
                                flow_id=flow.id,
                                user_detail=user_detail_dict,
                                lead_id=existing_user.lead_id if existing_user and hasattr(existing_user, 'lead_id') else None
                            )
                            
                            # Step 2: Update user state based on node service response
                            if node_service_response.get("status") == "success":
                                next_node_id = node_service_response.get("next_node_id")
                                if next_node_id:
                                    # Handle successful node processing (is_validation_error = False)
                                    processed_value = node_service_response.get("processed_value")
                                    await self._handle_successful_node_processing(
                                        metadata=metadata,
                                        data=data,
                                        next_node_id=next_node_id,
                                        flow_id=flow.id,
                                        sender=sender,
                                        brand_id=brand_id,
                                        channel=channel,
                                        channel_account_id=existing_user.channel_account_id,
                                        validation_result=None,
                                        fallback_message=None,
                                        processed_value=processed_value
                                    )
                            else:
                                self.log_util.error(
                                    service_name="UserStateService",
                                    message=f"[EXISTING_USER] Node service failed: {node_service_response.get('message')}"
                                )
                else:
                    # ========== USER EXISTS BUT NOT IN AUTOMATION ==========
                    self.log_util.info(
                        service_name="UserStateService",
                        message=f"[EXISTING_USER] User not in automation, checking triggers"
                    )
                    
                    # Check for triggers and initiate flow if matched (existing user, not in automation)
                    return await self._check_triggers_and_initiate_flow(
                        metadata=metadata,
                        data=data,
                        sender=sender,
                        brand_id=brand_id,
                        user_id=user_id,
                        channel=channel,
                        channel_account_id=channel_account_id,
                        existing_user=existing_user
                    )
        except Exception as e:
            self.log_util.error(
                service_name="UserStateService",
                message=f"Error in check_and_process_user_with_flow: {str(e)}"
            )

