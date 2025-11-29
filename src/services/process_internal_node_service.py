"""
Process Internal Node Service
Handles processing of internal nodes (condition, delay, etc.)
"""
from typing import Dict, Any, TYPE_CHECKING, Optional
from utils.log_utils import LogUtil
from database.flow_db import FlowDB

if TYPE_CHECKING:
    from models.webhook_message_data import WebhookMetadata


class ProcessInternalNodeService:
    """
    Service for processing internal nodes (condition, delay, etc.)
    """
    
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB
    ):
        self.log_util = log_util
        self.flow_db = flow_db
    
    async def process_internal_node(
        self,
        metadata: "WebhookMetadata",
        data: Dict[str, Any],
        node_id: str,
        flow_id: str
    ) -> Dict[str, Any]:
        """
        Process an internal node (condition, delay, etc.)
        
        Args:
            metadata: WebhookMetadata from saved webhook
            data: Normalized data from saved webhook
            node_id: Internal node ID to process
            flow_id: Flow ID
        
        Returns:
            Dict with status, message, next_node_id
        """
        try:
            self.log_util.info(
                service_name="ProcessInternalNodeService",
                message=f"[PROCESS_INTERNAL] Processing internal node {node_id} for flow {flow_id}"
            )
            
            # Get flow
            flow = await self.flow_db.get_flow_by_id(flow_id)
            if not flow:
                return {
                    "status": "error",
                    "message": f"Flow {flow_id} not found",
                    "next_node_id": None
                }
            
            # Get node from flow
            def _node_to_dict(node: Any) -> Dict[str, Any]:
                if hasattr(node, "model_dump"):
                    return node.model_dump()
                if isinstance(node, dict):
                    return node
                return dict(node)
            
            node_data = None
            for node in flow.flowNodes:
                node_dict = _node_to_dict(node)
                if node_dict.get("id") == node_id:
                    node_data = node_dict
                    break
            
            if not node_data:
                return {
                    "status": "error",
                    "message": f"Internal node {node_id} not found in flow",
                    "next_node_id": None
                }
            
            node_type = node_data.get("type")
            
            # Process based on node type
            if node_type == "condition":
                return await self._process_condition_node(
                    node_data=node_data,
                    node_id=node_id,
                    flow_id=flow_id,
                    metadata=metadata
                )
            
            elif node_type == "delay":
                return await self._process_delay_node(
                    node_data=node_data,
                    node_id=node_id
                )
            
            else:
                return {
                    "status": "error",
                    "message": f"Unknown internal node type: {node_type}",
                    "next_node_id": None
                }
                
        except Exception as e:
            self.log_util.error(
                service_name="ProcessInternalNodeService",
                message=f"Error processing internal node: {str(e)}"
            )
            return {
                "status": "error",
                "message": f"Error processing internal node: {str(e)}",
                "next_node_id": None
            }
    
    async def _process_condition_node(
        self,
        node_data: Dict[str, Any],
        node_id: str,
        flow_id: str,
        metadata: "WebhookMetadata"
    ) -> Dict[str, Any]:
        """
        Process condition node - evaluate conditions and return yes/no node ID.
        
        Returns:
            processed_value: The node ID for yes or no result (e.g., "condition-node-xxx__true" or "condition-node-xxx__false")
        """
        try:
            self.log_util.info(
                service_name="ProcessInternalNodeService",
                message=f"[PROCESS_INTERNAL] Processing condition node {node_id}"
            )
            
            # Get condition data
            flow_node_conditions = node_data.get("flowNodeConditions", [])
            condition_result = node_data.get("conditionResult", [])  # Now an array
            condition_operator = node_data.get("conditionOperator", "None")
            
            if not flow_node_conditions:
                return {
                    "status": "error",
                    "message": "No conditions found in condition node",
                    "processed_value": None
                }
            
            # Extract condition result IDs (the id field, not nodeResultId)
            # These IDs are used as source_node_id in edges (e.g., "condition-node-xxx__true" or "condition-node-xxx__false")
            y_result_node_id = None
            n_result_node_id = None
            if isinstance(condition_result, list):
                for item in condition_result:
                    if isinstance(item, dict):
                        item_id = item.get("id", "")
                        if "__true" in item_id:
                            y_result_node_id = item_id  # Use the condition result ID itself, not nodeResultId
                        elif "__false" in item_id:
                            n_result_node_id = item_id  # Use the condition result ID itself, not nodeResultId
            
            # Get user identifier and brand_id from metadata
            user_identifier = metadata.sender
            brand_id = metadata.brand_id
            
            # Get user's flow context variables
            flow_contexts = await self.flow_db.get_all_flow_user_context(
                user_identifier=user_identifier,
                brand_id=brand_id,
                flow_id=flow_id
            )
            
            # Create a dict of variable_name -> variable_value
            context_dict = {}
            for ctx in flow_contexts:
                context_dict[ctx.variable_name] = ctx.variable_value
            
            # Evaluate conditions
            condition_results = []
            for condition in flow_node_conditions:
                condition_variable = condition.get("variable", "")
                variable_name_with_at = condition_variable if condition_variable.startswith("@") else f"@{condition_variable}"
                variable_name_without_at = condition_variable.lstrip("@")
                condition_type = condition.get("flowConditionType", "")
                expected_value = condition.get("value", "")
                
                # Get actual value from context - try both with and without @
                actual_value = context_dict.get(variable_name_with_at) or context_dict.get(variable_name_without_at) or ""
                
                # Handle None values - convert to empty string for consistent comparison
                if actual_value is None:
                    actual_value = ""
                if expected_value is None:
                    expected_value = ""
                
                # Convert to strings for comparison
                actual_value_str = str(actual_value)
                expected_value_str = str(expected_value)
                
                # Log condition evaluation details
                self.log_util.info(
                    service_name="ProcessInternalNodeService",
                    message=f"[PROCESS_INTERNAL] Evaluating condition: variable='{condition_variable}' (with @: '{variable_name_with_at}', without @: '{variable_name_without_at}'), "
                            f"condition_type='{condition_type}', expected_value='{expected_value_str}', "
                            f"actual_value='{actual_value_str}', context_dict_keys={list(context_dict.keys())}"
                )
                
                # Evaluate condition
                condition_met = False
                if condition_type == "Equal":
                    condition_met = (actual_value_str.lower() == expected_value_str.lower())
                    self.log_util.info(
                        service_name="ProcessInternalNodeService",
                        message=f"[PROCESS_INTERNAL] Equal comparison: '{actual_value_str.lower()}' == '{expected_value_str.lower()}' = {condition_met}"
                    )
                elif condition_type == "NotEqual":
                    condition_met = (actual_value_str.lower() != expected_value_str.lower())
                    self.log_util.info(
                        service_name="ProcessInternalNodeService",
                        message=f"[PROCESS_INTERNAL] NotEqual comparison: '{actual_value_str.lower()}' != '{expected_value_str.lower()}' = {condition_met}"
                    )
                elif condition_type == "Contains":
                    # Check if actual_value contains expected_value
                    condition_met = (expected_value_str.lower() in actual_value_str.lower())
                    self.log_util.info(
                        service_name="ProcessInternalNodeService",
                        message=f"[PROCESS_INTERNAL] Contains check: '{expected_value_str.lower()}' in '{actual_value_str.lower()}' = {condition_met}"
                    )
                elif condition_type == "NotContains":
                    # Check if actual_value does NOT contain expected_value
                    condition_met = (expected_value_str.lower() not in actual_value_str.lower())
                    self.log_util.info(
                        service_name="ProcessInternalNodeService",
                        message=f"[PROCESS_INTERNAL] NotContains check: '{expected_value_str.lower()}' not in '{actual_value_str.lower()}' = {condition_met}"
                    )
                elif condition_type == "GreaterThan":
                    try:
                        condition_met = (float(actual_value_str) > float(expected_value_str))
                        self.log_util.info(
                            service_name="ProcessInternalNodeService",
                            message=f"[PROCESS_INTERNAL] GreaterThan comparison: {float(actual_value_str)} > {float(expected_value_str)} = {condition_met}"
                        )
                    except (ValueError, TypeError) as e:
                        condition_met = False
                        self.log_util.warning(
                            service_name="ProcessInternalNodeService",
                            message=f"[PROCESS_INTERNAL] GreaterThan comparison failed (non-numeric values): actual='{actual_value_str}', expected='{expected_value_str}', error={str(e)}"
                        )
                elif condition_type == "LessThan":
                    try:
                        condition_met = (float(actual_value_str) < float(expected_value_str))
                        self.log_util.info(
                            service_name="ProcessInternalNodeService",
                            message=f"[PROCESS_INTERNAL] LessThan comparison: {float(actual_value_str)} < {float(expected_value_str)} = {condition_met}"
                        )
                    except (ValueError, TypeError) as e:
                        condition_met = False
                        self.log_util.warning(
                            service_name="ProcessInternalNodeService",
                            message=f"[PROCESS_INTERNAL] LessThan comparison failed (non-numeric values): actual='{actual_value_str}', expected='{expected_value_str}', error={str(e)}"
                        )
                else:
                    # Unknown condition type
                    self.log_util.warning(
                        service_name="ProcessInternalNodeService",
                        message=f"[PROCESS_INTERNAL] Unknown condition type: '{condition_type}', defaulting to False"
                    )
                    condition_met = False
                
                condition_results.append(condition_met)
            
            # Apply operator (AND/OR/None)
            final_result = False
            if condition_operator == "AND" or condition_operator == "None":
                final_result = all(condition_results)
            elif condition_operator == "OR":
                final_result = any(condition_results)
            
            # Get result node ID from extracted values
            if final_result:
                processed_value = y_result_node_id
                result_type = "true"
            else:
                processed_value = n_result_node_id
                result_type = "false"
            
            if not processed_value:
                return {
                    "status": "error",
                    "message": f"Condition result node ID not found for {result_type} result",
                    "processed_value": None
                }
            
            self.log_util.info(
                service_name="ProcessInternalNodeService",
                message=f"[PROCESS_INTERNAL] Condition evaluated to {result_type}, returning node ID: {processed_value}"
            )
            
            return {
                "status": "success",
                "message": f"Condition node processed, result: {result_type}",
                "processed_value": processed_value  # The yes/no node ID
            }
            
        except Exception as e:
            self.log_util.error(
                service_name="ProcessInternalNodeService",
                message=f"Error processing condition node: {str(e)}"
            )
            return {
                "status": "error",
                "message": f"Error processing condition node: {str(e)}",
                "processed_value": None
            }
    
    async def _process_delay_node(
        self,
        node_data: Dict[str, Any],
        node_id: str
    ) -> Dict[str, Any]:
        """
        Process delay node - return delay information.
        
        Returns:
            processed_value: Dict with delayDuration, delayUnit, waitForReply
        """
        try:
            self.log_util.info(
                service_name="ProcessInternalNodeService",
                message=f"[PROCESS_INTERNAL] Processing delay node {node_id}"
            )
            
            delay_duration = node_data.get("delayDuration", 0)
            delay_unit = node_data.get("delayUnit", "minutes")
            wait_for_reply = node_data.get("waitForReply", False)
            
            # Calculate wait time in seconds
            wait_time_seconds = delay_duration
            if delay_unit == "minutes":
                wait_time_seconds = delay_duration * 60
            elif delay_unit == "hours":
                wait_time_seconds = delay_duration * 3600
            elif delay_unit == "days":
                wait_time_seconds = delay_duration * 86400
            
            processed_value = {
                "delay_duration": delay_duration,
                "delay_unit": delay_unit,
                "wait_time_seconds": wait_time_seconds,
                "wait_for_reply": wait_for_reply
            }
            
            self.log_util.info(
                service_name="ProcessInternalNodeService",
                message=f"[PROCESS_INTERNAL] Delay node processed: {wait_time_seconds} seconds"
            )
            
            return {
                "status": "success",
                "message": "Delay node processed",
                "processed_value": processed_value
            }
            
        except Exception as e:
            self.log_util.error(
                service_name="ProcessInternalNodeService",
                message=f"Error processing delay node: {str(e)}"
            )
            return {
                "status": "error",
                "message": f"Error processing delay node: {str(e)}",
                "processed_value": None
            }

