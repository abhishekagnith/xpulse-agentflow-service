"""
Node Identification and Processing Service
Handles node identification, reply matching, validation, and node processing.
Refactored from UserStateService to separate concerns.
"""
from typing import Optional, Dict, Any, List, Callable, TYPE_CHECKING
from utils.log_utils import LogUtil
from database.flow_db import FlowDB
from models.flow_data import FlowData
from models.user_data import UserData
from models.webhook_message_data import WebhookMetadata

if TYPE_CHECKING:
    from services.whatsapp_flow_service import WhatsAppFlowService
    from services.process_internal_node_service import ProcessInternalNodeService
    from services.user_transaction_service import UserTransactionService


class NodeIdentificationService:
    """
    Service for identifying next nodes in a flow and processing them.
    Handles reply matching, validation, mismatch handling, and node processing.
    """
    
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB,
        whatsapp_flow_service: "WhatsAppFlowService",
        process_internal_node_service: Optional["ProcessInternalNodeService"] = None,
        user_transaction_service: Optional["UserTransactionService"] = None
    ):
        self.log_util = log_util
        self.flow_db = flow_db
        self.whatsapp_flow_service = whatsapp_flow_service
        self.process_internal_node_service = process_internal_node_service
        self.user_transaction_service = user_transaction_service
    
    async def identify_and_process_node(
        self,
        metadata: WebhookMetadata,
        data: Dict[str, Any],
        is_validation_error: bool,
        fallback_message: Optional[str],
        node_id_to_process: Optional[str],
        current_node_id: str,
        flow_id: str,
        user_detail: Optional[Dict[str, Any]] = None,
        lead_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process the identified next node.
        
        This service processes nodes based on the provided parameters.
        It handles:
        1. Getting user state and flow
        2. Identifying next node (from node_id_to_process, matched_answer_id, or default edge)
        3. Checking if next node is internal (from node_details DB)
        4. Processing the node via node process API (if not internal)
        5. Handling auto-chaining for message nodes
        
        Args:
            metadata: WebhookMetadata from saved webhook (contains user_identifier, brand_id, user_id, channel, channel_identifier)
            data: Normalized data from saved webhook (may contain matched_answer_id for matched replies)
            is_validation_error: True if validation failed, False otherwise
            fallback_message: Optional fallback message for validation failures
            node_id_to_process: Node ID to process (if None, identifies next node)
            current_node_id: Current node ID from user state (or trigger_node_id for new triggers)
            flow_id: Flow ID
            user_detail: Optional user detail object from user table (contains channel-specific identifiers)
            lead_id: Optional lead ID from lead management service
        
        Returns:
            Dict with status ("success" or "error"), message, next_node_id
        """
        def _node_to_dict(node: Any) -> Dict[str, Any]:
            if hasattr(node, "model_dump"):
                return node.model_dump()
            if isinstance(node, dict):
                return node
            return dict(node)

        try:
            # Extract values from metadata
            user_identifier = metadata.sender
            brand_id = metadata.brand_id
            user_id = metadata.user_id
            channel = metadata.channel
            channel_account_id = metadata.channel_identifier
            
            self.log_util.info(
                service_name="NodeIdentificationService",
                message=f"[IDENTIFY_NODE] Starting identify_and_process_node for user {user_identifier}, current_node_id: {current_node_id}, node_id_to_process: {node_id_to_process}"
            )
            
            # STEP 1: Get flow
            flow = await self.flow_db.get_flow_by_id(flow_id)
            if not flow:
                return {
                    "status": "error",
                    "message": f"Flow {flow_id} not found",
                    "next_node_id": None
                }
            
            # STEP 3: Get edges
            edges = await self.flow_db.get_flow_edges(flow_id)
            if not edges:
                return {
                    "status": "error",
                    "message": "No edges found for flow",
                    "next_node_id": None
                }
            
            # STEP 4: Get current node (if current_node_id is an actual node, not a button answer ID)
            # Check if current_node_id exists as a node in flowNodes
            current_node = None
            is_button_answer_id = False
            
            # First check if current_node_id is a button answer ID by checking edges
            # Button answer IDs are source_node_ids in edges but not nodes in flowNodes
            source_node_ids_in_edges = {edge.source_node_id for edge in edges}
            node_ids_in_flow = {_node_to_dict(node).get("id") for node in flow.flowNodes}
            
            if current_node_id in source_node_ids_in_edges and current_node_id not in node_ids_in_flow:
                # current_node_id is a button answer ID, not a node
                is_button_answer_id = True
                self.log_util.info(
                    service_name="NodeIdentificationService",
                    message=f"[IDENTIFY_NODE] current_node_id={current_node_id} is a button answer ID, not a node. Skipping node lookup."
                )
            else:
                # Try to find it as a node
                for node in flow.flowNodes:
                    node_dict = _node_to_dict(node)
                    if node_dict.get("id") == current_node_id:
                        current_node = node_dict
                        break
            
            if not current_node:
                self.log_util.warning(
                    service_name="NodeIdentificationService",
                    message=f"[IDENTIFY_NODE] current_node_id={current_node_id} not found as a node, but will try to use it as source_node_id in edges"
                )
            
            # STEP 5: Note - Question node reply saving is handled by ReplyValidationService
            # This service only processes nodes and identifies next nodes, not saving user answers
            
            # STEP 6: Identify next node using flow edges
            # Simple logic: Use source_node_id from edges table to find target_node_id
            next_node_id = None
            next_node_data = None
            
            # Special handling for validation errors
            if is_validation_error:
                if node_id_to_process:
                    # mismatch_retry: retry the same node (don't move to next node)
                    next_node_id = node_id_to_process
                    self.log_util.info(
                        service_name="NodeIdentificationService",
                        message=f"[IDENTIFY_NODE] Validation error - retrying same node: {next_node_id}"
                    )
                    
                    # Get node data for the node to retry
                    for node in flow.flowNodes:
                        node_dict = _node_to_dict(node)
                        if node_dict.get("id") == next_node_id:
                            next_node_data = node_dict
                            break
                    
                    if not next_node_data:
                        return {
                            "status": "error",
                            "message": f"Node to retry {next_node_id} not found",
                            "next_node_id": None
                        }
                else:
                    # validation_exit: just send error message, don't process any node
                    # No node IDs needed - just send error message
                    next_node_id = None
                    next_node_data = None
                    self.log_util.info(
                        service_name="NodeIdentificationService",
                        message=f"[IDENTIFY_NODE] Validation exit - sending error message only, no node IDs"
                    )
            elif node_id_to_process:
                # Node to process is specified (e.g., matched_other_node) - process it directly
                next_node_id = node_id_to_process
                self.log_util.info(
                    service_name="NodeIdentificationService",
                    message=f"[IDENTIFY_NODE] node_id_to_process specified - processing node directly: {next_node_id}"
                )
                
                # Get node data for the node to process
                for node in flow.flowNodes:
                    node_dict = _node_to_dict(node)
                    if node_dict.get("id") == next_node_id:
                        next_node_data = node_dict
                        break
                
                if not next_node_data:
                    return {
                        "status": "error",
                        "message": f"Node to process {next_node_id} not found",
                        "next_node_id": None
                    }
            else:
                # Normal flow: find next node via edges
                # Determine source_node_id to use for edge lookup
                source_node_id_to_use = None
                
                # Check if matched_answer_id is in data
                matched_answer_id = data.get("matched_answer_id")
                if matched_answer_id:
                    # Use matched_answer_id as source_node_id (button answer ID)
                    source_node_id_to_use = matched_answer_id
                    self.log_util.info(
                        service_name="NodeIdentificationService",
                        message=f"[IDENTIFY_NODE] Using matched_answer_id from data as source_node_id: {source_node_id_to_use}"
                    )
                else:
                    # Use current_node_id as source_node_id
                    source_node_id_to_use = current_node_id
                    self.log_util.info(
                        service_name="NodeIdentificationService",
                        message=f"[IDENTIFY_NODE] Using current_node_id as source_node_id: {source_node_id_to_use}"
                    )
                
                # Find next node from edges using source_node_id
                self.log_util.info(
                    service_name="NodeIdentificationService",
                    message=f"[IDENTIFY_NODE] Looking for edge with source_node_id={source_node_id_to_use} in {len(edges)} edges"
                )
                for edge in edges:
                    if edge.source_node_id == source_node_id_to_use:
                        next_node_id = edge.target_node_id
                        self.log_util.info(
                            service_name="NodeIdentificationService",
                            message=f"[IDENTIFY_NODE] ✅ Found edge: {source_node_id_to_use} -> {next_node_id}"
                        )
                        break
                
                if not next_node_id:
                    self.log_util.error(
                        service_name="NodeIdentificationService",
                        message=f"[IDENTIFY_NODE] ❌ No edge found with source_node_id={source_node_id_to_use}. Available source_node_ids: {[edge.source_node_id for edge in edges]}"
                    )
                    return {
                        "status": "error",
                        "message": f"No next node found for source_node_id: {source_node_id_to_use}",
                        "next_node_id": None
                    }
                
                # Get next node data
                for node in flow.flowNodes:
                    node_dict = _node_to_dict(node)
                    if node_dict.get("id") == next_node_id:
                        next_node_data = node_dict
                        break
                
                if not next_node_data:
                    return {
                        "status": "error",
                        "message": f"Next node {next_node_id} not found",
                        "next_node_id": None
                    }
            
            # STEP 6.5: Check if next node is condition or delay - process via internal node service
            # Skip if next_node_id is None (validation_exit case)
            if next_node_id is None:
                # Validation exit - just send error message, no node to process
                # Only send through WhatsAppFlowService if channel is whatsapp and is_validation_error is True
                if channel == "whatsapp" and is_validation_error:
                    self.log_util.info(
                        service_name="NodeIdentificationService",
                        message=f"[IDENTIFY_NODE] Validation exit - sending error message via WhatsAppFlowService (channel=whatsapp, is_validation_error=True)"
                    )
                    # Send error message via node process API with next_node_id=None and current_node_id=None
                    # Only send fallback message, no node data
                    node_result = await self.whatsapp_flow_service.call_node_process_api(
                        flow=flow,
                        current_node_id=None,  # No current node for validation exit
                        next_node_id=None,  # No next node for validation exit
                        next_node_data=None,  # No node data for validation exit
                        user_identifier=user_identifier,
                        brand_id=brand_id,
                        user_id=user_id,
                        channel=channel,
                        fallback_message=fallback_message,
                        is_validation_error=True,
                        user_state={}
                    )
                    
                    if node_result.get("status") != "success":
                        return {
                            "status": "error",
                            "message": node_result.get("message", "Failed to send validation error message"),
                            "next_node_id": None
                        }
                    
                    return {
                        "status": "success",
                        "message": "Validation error message sent",
                        "next_node_id": None
                    }
                else:
                    # For non-WhatsApp channels or when is_validation_error is False, just return success
                    # (Error message handling for other channels should be done elsewhere)
                    self.log_util.info(
                        service_name="NodeIdentificationService",
                        message=f"[IDENTIFY_NODE] Validation exit - skipping WhatsAppFlowService (channel={channel}, is_validation_error={is_validation_error})"
                    )
                    return {
                        "status": "success",
                        "message": "Validation exit handled (no node to process)",
                        "next_node_id": None
                    }
            
            next_node_type = next_node_data.get("type")
            if next_node_type in ("condition", "delay") and self.process_internal_node_service:
                self.log_util.info(
                    service_name="NodeIdentificationService",
                    message=f"[IDENTIFY_NODE] Next node is {next_node_type}, processing via internal node service"
                )
                
                internal_node_response = await self.process_internal_node_service.process_internal_node(
                    metadata=metadata,
                    data=data,
                    node_id=next_node_id,
                    flow_id=flow_id
                )
                
                if internal_node_response.get("status") == "success":
                    processed_value = internal_node_response.get("processed_value")
                    
                    # Send processed data to user transaction service
                    if self.user_transaction_service:
                        await self.user_transaction_service.process_node_transaction(
                            metadata=metadata,
                            data=data,
                            node_id=next_node_id,
                            node_type=next_node_type,
                            flow_id=flow_id,
                            processed_value=processed_value,
                            node_data=next_node_data,
                            user_detail=user_detail
                        )
                    
                    return {
                        "status": "success",
                        "message": f"{next_node_type.capitalize()} node processed successfully",
                        "next_node_id": next_node_id,
                        "processed_value": processed_value  # For condition: yes/no node ID, for delay: delay info dict
                    }
                else:
                    return {
                        "status": "error",
                        "message": internal_node_response.get("message", f"Failed to process {next_node_type} node"),
                        "next_node_id": None
                    }
            
            # STEP 7: Process the node via node process API
            # Only call WhatsAppFlowService if channel is "whatsapp"
            if channel == "whatsapp":
                # Use empty dict for user_state - node processing doesn't require user state
                self.log_util.info(
                    service_name="NodeIdentificationService",
                    message=f"[IDENTIFY_NODE] Calling node process API: next_node_id={next_node_id}, next_node_type={next_node_data.get('type') if next_node_data else None}, is_validation_error={is_validation_error}, fallback_message={'present' if fallback_message else 'None'}"
                )
                node_result = await self.whatsapp_flow_service.call_node_process_api(
                    flow=flow,
                    current_node_id=current_node_id,
                    next_node_id=next_node_id,
                    next_node_data=next_node_data,
                    user_identifier=user_identifier,
                    brand_id=brand_id,
                    user_id=user_id,
                    channel=channel,
                    fallback_message=fallback_message,
                    is_validation_error=is_validation_error,
                    user_state={}  # Empty dict - user state not needed for node processing
                )
                
                if node_result.get("status") != "success":
                    return {
                        "status": "error",
                        "message": node_result.get("message", "Node processing failed"),
                        "next_node_id": None
                    }
            else:
                # For non-WhatsApp channels, skip WhatsAppFlowService
                self.log_util.info(
                    service_name="NodeIdentificationService",
                    message=f"[IDENTIFY_NODE] Skipping WhatsAppFlowService for channel={channel}, next_node_id={next_node_id}"
                )
                # Return success without calling WhatsAppFlowService
                # Other channel services should handle node processing separately
            
            # STEP 9: Note - User state update is handled by UserStateService, not here
            # This service only processes nodes and returns the next_node_id
            
            # STEP 10: Auto-chain logic for message nodes (only for WhatsApp)
            if next_node_data.get("type") == "message" and channel == "whatsapp":
                chain_result = await self.whatsapp_flow_service.detect_and_chain_nodes(
                    flow=flow,
                    current_processed_node_id=next_node_id,
                    current_processed_node_data=next_node_data,
                    edges=edges
                )
                
                if chain_result.get("should_chain"):
                    chained_node_id = chain_result.get("next_node_id")
                    
                    # Recursively process next message node
                    return await self.identify_and_process_node(
                        metadata=metadata,
                        data=data,
                        is_validation_error=False,
                        fallback_message=None,
                        node_id_to_process=None,
                        current_node_id=chained_node_id,
                        flow_id=flow_id,
                        user_detail=user_detail,
                        lead_id=lead_id  # Pass lead_id through recursive calls
                    )
            
            # Send processed data to user transaction service for regular nodes
            if self.user_transaction_service:
                await self.user_transaction_service.process_node_transaction(
                    metadata=metadata,
                    data=data,
                    node_id=next_node_id,
                    node_type=next_node_data.get("type"),
                    flow_id=flow_id,
                    processed_value=None,
                    node_data=next_node_data,
                    user_detail=user_detail
                    )
            
            return {
                "status": "success",
                "message": "Node identified and processed successfully",
                "next_node_id": next_node_id
            }
            
        except Exception as e:
            self.log_util.error(
                service_name="NodeIdentificationService",
                message=f"[IDENTIFY_NODE] ❌ Error identifying and processing node: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="NodeIdentificationService",
                message=f"[IDENTIFY_NODE] Traceback: {traceback.format_exc()}"
            )
            return {
                "status": "error",
                "message": f"Error identifying and processing node: {str(e)}",
                "next_node_id": None
            }

