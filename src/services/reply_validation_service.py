"""
Reply Validation Service
Handles reply matching, validation checks, and mismatch handling.
"""
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable
    from models.webhook_message_data import WebhookMetadata
from utils.log_utils import LogUtil
from database.flow_db import FlowDB
from models.flow_data import FlowData
from models.user_data import UserData


class ReplyValidationService:
    """
    Service for validating user replies, matching them against expected answers,
    and handling validation failures.
    """
    
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB
    ):
        self.log_util = log_util
        self.flow_db = flow_db
    
    async def process_reply_match(
        self,
        source_node: Dict[str, Any],
        user_reply: str,
        edges: List[Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Process when user reply matches the current node's expected answers in list and button questions.
        Returns dict with matched_answer_id if a match is found, None otherwise.
        Node service will use this answer_id to find next node via edges.
        """
        try:
            node_type = source_node.get("type")
            
            # Only process nodes that have expected answers
            if node_type not in ("trigger_template", "button_question", "list_question"):
                return None
            
            expected_answers = source_node.get("expectedAnswers", [])
            if not expected_answers:
                return None
            
            if not user_reply:
                return None
            
            # Match user input to expected answers
            self.log_util.info(
                service_name="ReplyValidationService",
                message=f"[PROCESS_REPLY_MATCH] Checking {len(expected_answers)} expected answers for user_reply='{user_reply}'"
            )
            for answer in expected_answers:
                expected_input = answer.get("expectedInput", "")
                answer_id = answer.get("id")
                self.log_util.info(
                    service_name="ReplyValidationService",
                    message=f"[PROCESS_REPLY_MATCH] Comparing expected_input='{expected_input}' (lower: '{expected_input.lower()}') with user_reply='{user_reply}' (lower: '{user_reply.lower()}')"
                )
                if expected_input and expected_input.lower() == user_reply.lower():
                    # Return the matched answer ID - node service will find next node via edges
                    self.log_util.info(
                        service_name="ReplyValidationService",
                        message=f"[PROCESS_REPLY_MATCH] ✅ Match found! Returning matched_answer_id={answer_id}"
                    )
                    return {
                        "matched_answer_id": answer_id
                    }
            
            self.log_util.info(
                service_name="ReplyValidationService",
                message=f"[PROCESS_REPLY_MATCH] ❌ No match found for user_reply='{user_reply}'"
            )
            return None
        except Exception as e:
            self.log_util.error(
                service_name="ReplyValidationService",
                message=f"Error processing reply match: {str(e)}"
            )
            return None
    
    async def check_and_handle_validation(
        self,
        current_node_id: str,
        next_node_id: str,
        current_node_data: Dict[str, Any],
        user_state: Dict[str, Any],
        user_identifier: str,
        brand_id: int,
        channel: str = "whatsapp",
        channel_account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check validation count when reply doesn't match expected answers.
        Applies when current_node_id == next_node_id (retry scenario) OR when no match found anywhere.
        
        Returns:
            Dict with:
                - should_process: bool - Whether to process the node normally
                - should_exit: bool - Whether to exit automation
                - validation_count: int - Updated validation count
                - fallback_message: Optional[str] - Fallback message to send
        """
        # Check if current_node_id == next_node_id (retry scenario)
        if current_node_id != next_node_id:
            # Different nodes - normal flow, reset validation count
            # Note: UserStateService will handle validation state updates, not this service
            return {
                "should_process": True,
                "should_exit": False,
                "validation_count": 0,
                "fallback_message": None
            }
        
        # Same node - retry scenario, check validation count
        # Get fallback count from current node (default 3)
        max_fallback_count = 3
        answer_validation = current_node_data.get("answerValidation")
        
        if answer_validation:
            if isinstance(answer_validation, dict):
                fails_count_str = answer_validation.get("failsCount", "3")
            else:
                fails_count_str = getattr(answer_validation, "failsCount", "3")
            
            try:
                max_fallback_count = int(fails_count_str) if fails_count_str else 3
            except (ValueError, TypeError):
                max_fallback_count = 3
        
        # Get current validation count from user state
        validation = user_state.get("validation", {})
        if isinstance(validation, dict):
            current_validation_count = validation.get("failure_count", 0)
        else:
            # Handle case where validation might be a ValidationData object
            current_validation_count = getattr(validation, "failure_count", 0) if validation else 0
        
        # Get fallback message from node or use default
        fallback_message = "This is not the valid response. Please try again below"
        if answer_validation:
            if isinstance(answer_validation, dict):
                node_fallback = answer_validation.get("fallback", "")
            else:
                node_fallback = getattr(answer_validation, "fallback", "")
            
            if node_fallback and node_fallback.strip():
                fallback_message = node_fallback.strip()
        
        # Check if within limit
        if current_validation_count < max_fallback_count:
            # Within limit - increment validation count and allow retry
            await self.flow_db.update_validation_state(
                user_identifier=user_identifier,
                brand_id=brand_id,
                validation_failed=True,
                failure_message=fallback_message,
                channel=channel,
                channel_account_id=channel_account_id
            )
            
            self.log_util.info(
                service_name="ReplyValidationService",
                message=f"Validation failure {current_validation_count + 1}/{max_fallback_count} for user {user_identifier} on node {current_node_id}"
            )
            
            return {
                "should_process": True,
                "should_exit": False,
                "validation_count": current_validation_count + 1,
                "fallback_message": fallback_message
            }
        else:
            # Exceeded limit - exit automation
            # Note: UserStateService will handle exiting automation and validation state updates, not this service
            error_message = "We cannot currently process your request. Please try again later"
            
            self.log_util.warning(
                service_name="ReplyValidationService",
                message=f"Validation limit exceeded ({current_validation_count}/{max_fallback_count}) for user {user_identifier}, exiting automation"
            )
            
            return {
                "should_process": False,
                "should_exit": True,
                "validation_count": current_validation_count,
                "fallback_message": error_message
            }
    
    async def handle_reply_mismatch(
        self,
        flow: FlowData,
        current_node: Dict[str, Any],
        user_reply: str,
        user_identifier: str,
        brand_id: int,
        edges: List[Any]
    ) -> Dict[str, Any]:
        """
        Handle reply mismatch - check if reply matches any button/list node in the flow.
        Returns status and instructions.
        """
        try:
            if not user_reply:
                return {
                    "status": "error",
                    "message": "Could not extract user input"
                }
            
            def _node_to_dict(node: Any) -> Dict[str, Any]:
                if hasattr(node, "model_dump"):
                    return node.model_dump()
                if isinstance(node, dict):
                    return node
                return dict(node)
            
            # Check if reply matches any button/list node in the flow
            matched_node_id = None
            matched_answer_id = None
            
            for node in flow.flowNodes:
                node_dict = _node_to_dict(node)
                check_node_type = node_dict.get("type")
                
                if check_node_type in ("button_question", "list_question"):
                    expected_answers = node_dict.get("expectedAnswers", [])
                    for answer in expected_answers:
                        expected_input = answer.get("expectedInput", "")
                        if expected_input and expected_input.lower() == user_reply.lower():
                            matched_node_id = node_dict.get("id")
                            matched_answer_id = answer.get("id")
                            break
                    if matched_node_id:
                        break
            
            # If match found in another node, return match info
            if matched_node_id and matched_answer_id:
                next_node_id = None
                for edge in edges:
                    if edge.source_node_id == matched_answer_id:
                        next_node_id = edge.target_node_id
                        break

                if next_node_id:
                    return {
                        "status": "matched_other_node",
                        "message": "Matched in another node",
                        "matched_node_id": matched_node_id,
                        "next_node_id": next_node_id
                    }
            
            # No match found anywhere in flow - return retry status
            return {
                "status": "retry",
                "fallback_message": None,  # Let node processor handle the message
                "message": "Reply did not match, retrying current node"
            }
                
        except Exception as e:
            self.log_util.error(
                service_name="ReplyValidationService",
                message=f"Error handling reply mismatch: {str(e)}"
            )
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def validate_and_match_reply(
        self,
        metadata: "WebhookMetadata",
        data: Dict[str, Any],
        current_node_id: str,
        flow_id: str,
        is_text: bool = False,
        current_validation_count: int = 0
    ) -> Dict[str, Any]:
        """
        Main validation and matching function.
        Checks if reply matches expected answers in current node, handles validation, and returns result.
        If not matched in current node, checks all nodes in the flow (unless is_text=True).
        
        Args:
            metadata: WebhookMetadata from saved webhook
            data: Normalized data from saved webhook (contains user_reply)
            current_node_id: Current node ID to check validation against
            flow_id: Flow ID to fetch flow and check all nodes
            is_text: If True, skip checking expected answers in flow (for text questions)
            current_validation_count: Current validation failure count from user state
        
        Returns:
            Dict with:
                - status: "matched" | "mismatch_retry" | "validation_exit" | "matched_other_node" | "use_default_edge" | "error"
                - matched_answer_id: Optional[str] - Answer ID if matched in current node
                - matched_node_id: Optional[str] - Node ID if matched in another node
                - fallback_message: Optional[str] - Fallback message if validation failed
                - message: Optional[str] - Error message if status is "error"
        """
        try:
            # Log data received in validation service for debugging
            self.log_util.info(
                service_name="ReplyValidationService",
                message=f"[VALIDATE_REPLY] Data received - keys: {list(data.keys()) if data else 'None'}, user_reply: '{data.get('user_reply') if data else None}', data_type: {type(data)}, full_data: {data}"
            )
            
            # Extract user_reply from data
            user_reply = data.get("user_reply")
            if not user_reply:
                self.log_util.warning(
                    service_name="ReplyValidationService",
                    message=f"[VALIDATE_REPLY] ❌ user_reply not found in data. Data keys: {list(data.keys()) if data else 'None'}, data value: {data}"
                )
                return {
                    "status": "error",
                    "message": "user_reply not found in data",
                    "matched_answer_id": None,
                    "matched_node_id": None,
                    "fallback_message": None
                }
            
            # Extract user info from metadata
            user_identifier = metadata.sender
            brand_id = metadata.brand_id
            channel = metadata.channel
            channel_account_id = metadata.channel_identifier
            
            # Step 1: Fetch flow and edges
            self.log_util.info(
                service_name="ReplyValidationService",
                message=f"[VALIDATE_REPLY] Step 1: Fetching flow with flow_id={flow_id}"
            )
            flow = await self.flow_db.get_flow_by_id(flow_id)
            if not flow:
                self.log_util.error(
                    service_name="ReplyValidationService",
                    message=f"[VALIDATE_REPLY] ❌ Flow {flow_id} not found"
                )
                return {
                    "status": "error",
                    "message": f"Flow {flow_id} not found",
                    "matched_answer_id": None,
                    "matched_node_id": None,
                    "fallback_message": None
                }
            
            self.log_util.info(
                service_name="ReplyValidationService",
                message=f"[VALIDATE_REPLY] Step 1: Flow found, fetching edges for flow_id={flow_id}"
            )
            edges = await self.flow_db.get_flow_edges(flow_id)
            if not edges:
                self.log_util.error(
                    service_name="ReplyValidationService",
                    message=f"[VALIDATE_REPLY] ❌ No edges found for flow {flow_id}"
                )
                return {
                    "status": "error",
                    "message": "No edges found for flow",
                    "matched_answer_id": None,
                    "matched_node_id": None,
                    "fallback_message": None
                }
            
            self.log_util.info(
                service_name="ReplyValidationService",
                message=f"[VALIDATE_REPLY] Step 1: Found {len(edges)} edges"
            )
            
            # Step 2: Get current node
            self.log_util.info(
                service_name="ReplyValidationService",
                message=f"[VALIDATE_REPLY] Step 2: Looking for current_node_id={current_node_id} in flow with {len(flow.flowNodes)} nodes"
            )
            def _node_to_dict(node: Any) -> Dict[str, Any]:
                if hasattr(node, "model_dump"):
                    return node.model_dump()
                if isinstance(node, dict):
                    return node
                return dict(node)
            
            current_node = None
            for node in flow.flowNodes:
                node_dict = _node_to_dict(node)
                if node_dict.get("id") == current_node_id:
                    current_node = node_dict
                    break
            
            if not current_node:
                self.log_util.error(
                    service_name="ReplyValidationService",
                    message=f"[VALIDATE_REPLY] ❌ Current node {current_node_id} not found in flow. Available node IDs: {[(_node_to_dict(n).get('id')) for n in flow.flowNodes]}"
                )
                return {
                    "status": "error",
                    "message": f"Current node {current_node_id} not found in flow",
                    "matched_answer_id": None,
                    "matched_node_id": None,
                    "fallback_message": None
                }
            
            self.log_util.info(
                service_name="ReplyValidationService",
                message=f"[VALIDATE_REPLY] Step 2: Current node found, type={current_node.get('type')}"
            )
            
            # Step 3: Try to match reply with expected answers in current node FIRST
            # This doesn't require user data, so we do it before fetching user
            self.log_util.info(
                service_name="ReplyValidationService",
                message=f"[VALIDATE_REPLY] Checking reply match for current_node_id={current_node_id}, user_reply='{user_reply}', node_type={current_node.get('type')}"
            )
            
            matched_result = await self.process_reply_match(
                source_node=current_node,
                user_reply=user_reply,
                edges=edges
            )
            
            self.log_util.info(
                service_name="ReplyValidationService",
                message=f"[VALIDATE_REPLY] process_reply_match result: {matched_result}"
            )
            
            if matched_result and matched_result.get("matched_answer_id"):
                # ✅ REPLY MATCHED in current node
                # If is_text is true, save flow context value
                if is_text:
                    user_input_variable = current_node.get("userInputVariable", "")
                    if user_input_variable:
                        # Save flow context variable
                        await self.flow_db.save_or_update_flow_variable(
                            user_identifier=user_identifier,
                            brand_id=brand_id,
                            flow_id=flow_id,
                            variable_name=user_input_variable,
                            variable_value=user_reply,
                            node_id=current_node_id
                        )
                        self.log_util.info(
                            service_name="ReplyValidationService",
                            message=f"Saved flow context variable {user_input_variable} = {user_reply} for user {user_identifier}"
                        )
                
                # Return matched_answer_id - UserStateService will use this as current_node_id for flow service
                matched_answer_id = matched_result.get("matched_answer_id")
                self.log_util.info(
                    service_name="ReplyValidationService",
                    message=f"[VALIDATE_REPLY] ✅ Reply matched in current node! Returning status='matched', matched_answer_id={matched_answer_id}"
                )
                return {
                    "status": "matched",
                    "matched_answer_id": matched_answer_id,
                    "matched_node_id": None,
                    "fallback_message": None
                }
            
            # ❌ REPLY DID NOT MATCH in current node
            # For text questions (is_text=True), validate against answerValidation rules
            if is_text:
                # Step 4.5: Validate text reply against answerValidation (regex, minValue, maxValue)
                answer_validation = current_node.get("answerValidation")
                validation_passed = True
                validation_error_message = None
                
                if answer_validation:
                    # Extract validation rules
                    if isinstance(answer_validation, dict):
                        validation_type = answer_validation.get("type", "")
                        regex_pattern = answer_validation.get("regex", "")
                        min_value = answer_validation.get("minValue", "")
                        max_value = answer_validation.get("maxValue", "")
                    else:
                        validation_type = getattr(answer_validation, "type", "")
                        regex_pattern = getattr(answer_validation, "regex", "")
                        min_value = getattr(answer_validation, "minValue", "")
                        max_value = getattr(answer_validation, "maxValue", "")
                    
                    # Helper function to check if string is numeric
                    def is_numeric_string(s: str) -> bool:
                        """Check if string represents a valid number (integer or float)"""
                        if not s or not s.strip():
                            return False
                        try:
                            float(s.strip())
                            return True
                        except (ValueError, TypeError):
                            return False
                    
                    # Validate based on validation type
                    if validation_type == "Number":
                        # Number validation: validate as numeric values
                        if not is_numeric_string(user_reply):
                            validation_passed = False
                            validation_error_message = "Input must be a number"
                            self.log_util.info(
                                service_name="ReplyValidationService",
                                message=f"[VALIDATE_REPLY] Text reply '{user_reply}' failed Number validation: not a valid number"
                            )
                        else:
                            # Validate minValue for numbers
                            if validation_passed and min_value and min_value.strip():
                                try:
                                    user_num = float(user_reply.strip())
                                    min_num = float(min_value.strip())
                                    if user_num < min_num:
                                        validation_passed = False
                                        validation_error_message = f"Number below minimum: {min_value}"
                                        self.log_util.info(
                                            service_name="ReplyValidationService",
                                            message=f"[VALIDATE_REPLY] Number '{user_reply}' failed minValue validation: {min_value} (user: {user_num})"
                                        )
                                except (ValueError, TypeError) as e:
                                    validation_passed = False
                                    validation_error_message = f"Invalid minimum value: {min_value}"
                                    self.log_util.warning(
                                        service_name="ReplyValidationService",
                                        message=f"[VALIDATE_REPLY] Invalid minValue '{min_value}': {str(e)}"
                                    )
                            
                            # Validate maxValue for numbers
                            if validation_passed and max_value and max_value.strip():
                                try:
                                    user_num = float(user_reply.strip())
                                    max_num = float(max_value.strip())
                                    if user_num > max_num:
                                        validation_passed = False
                                        validation_error_message = f"Number above maximum: {max_value}"
                                        self.log_util.info(
                                            service_name="ReplyValidationService",
                                            message=f"[VALIDATE_REPLY] Number '{user_reply}' failed maxValue validation: {max_value} (user: {user_num})"
                                        )
                                except (ValueError, TypeError) as e:
                                    validation_passed = False
                                    validation_error_message = f"Invalid maximum value: {max_value}"
                                    self.log_util.warning(
                                        service_name="ReplyValidationService",
                                        message=f"[VALIDATE_REPLY] Invalid maxValue '{max_value}': {str(e)}"
                                    )
                    
                    elif validation_type == "Text":
                        # Text validation: validate as text length
                        if validation_passed and min_value and min_value.strip():
                            try:
                                min_len = int(min_value.strip())
                                if len(user_reply) < min_len:
                                    validation_passed = False
                                    validation_error_message = f"Text length below minimum: {min_value} characters"
                                    self.log_util.info(
                                        service_name="ReplyValidationService",
                                        message=f"[VALIDATE_REPLY] Text reply '{user_reply}' (length: {len(user_reply)}) failed minValue validation: {min_value}"
                                    )
                            except (ValueError, TypeError):
                                self.log_util.warning(
                                    service_name="ReplyValidationService",
                                    message=f"[VALIDATE_REPLY] Invalid minValue for Text validation: {min_value}"
                                )
                        
                        if validation_passed and max_value and max_value.strip():
                            try:
                                max_len = int(max_value.strip())
                                if len(user_reply) > max_len:
                                    validation_passed = False
                                    validation_error_message = f"Text length above maximum: {max_value} characters"
                                    self.log_util.info(
                                        service_name="ReplyValidationService",
                                        message=f"[VALIDATE_REPLY] Text reply '{user_reply}' (length: {len(user_reply)}) failed maxValue validation: {max_value}"
                                    )
                            except (ValueError, TypeError):
                                self.log_util.warning(
                                    service_name="ReplyValidationService",
                                    message=f"[VALIDATE_REPLY] Invalid maxValue for Text validation: {max_value}"
                                )
                    
                    elif validation_type == "Email":
                        # Email validation: basic email format check
                        import re
                        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                        if not re.match(email_pattern, user_reply.strip()):
                            validation_passed = False
                            validation_error_message = "Invalid email format"
                            self.log_util.info(
                                service_name="ReplyValidationService",
                                message=f"[VALIDATE_REPLY] Text reply '{user_reply}' failed Email validation"
                            )
                    
                    elif validation_type == "Phone":
                        # Phone validation: basic phone format check (digits, may include +, -, spaces, parentheses)
                        import re
                        # Remove common phone formatting characters and check if remaining are digits
                        phone_cleaned = re.sub(r'[\s\-\(\)\+]', '', user_reply.strip())
                        if not phone_cleaned.isdigit() or len(phone_cleaned) < 7:
                            validation_passed = False
                            validation_error_message = "Invalid phone format"
                            self.log_util.info(
                                service_name="ReplyValidationService",
                                message=f"[VALIDATE_REPLY] Text reply '{user_reply}' failed Phone validation"
                            )
                    
                    # Validate regex pattern (applies to all validation types if provided)
                    if validation_passed and regex_pattern and regex_pattern.strip():
                        import re
                        try:
                            if not re.search(regex_pattern, user_reply):
                                validation_passed = False
                                validation_error_message = "Regex validation failed"
                                self.log_util.info(
                                    service_name="ReplyValidationService",
                                    message=f"[VALIDATE_REPLY] Text reply '{user_reply}' failed regex validation: {regex_pattern}"
                                )
                        except re.error as e:
                            self.log_util.warning(
                                service_name="ReplyValidationService",
                                message=f"[VALIDATE_REPLY] Invalid regex pattern '{regex_pattern}': {str(e)}"
                            )
                
                # If validation failed, check failsCount limit
                if not validation_passed:
                    # Get max fallback count from current node (default 3)
                    max_fallback_count = 3
                    if answer_validation:
                        if isinstance(answer_validation, dict):
                            fails_count_str = answer_validation.get("failsCount", "3")
                        else:
                            fails_count_str = getattr(answer_validation, "failsCount", "3")
                        
                        try:
                            max_fallback_count = int(fails_count_str) if fails_count_str else 3
                        except (ValueError, TypeError):
                            max_fallback_count = 3
                    
                    # Get fallback message from node or use default
                    fallback_message = "This is not the valid response. Please try again below"
                    if answer_validation:
                        if isinstance(answer_validation, dict):
                            node_fallback = answer_validation.get("fallback", "")
                        else:
                            node_fallback = getattr(answer_validation, "fallback", "")
                        
                        if node_fallback and node_fallback.strip():
                            fallback_message = node_fallback.strip()
                    
                    # Check if current validation count >= max limit
                    if current_validation_count >= max_fallback_count:
                        # Validation limit exceeded - exit automation
                        self.log_util.warning(
                            service_name="ReplyValidationService",
                            message=f"[VALIDATE_REPLY] Text validation limit exceeded ({current_validation_count}/{max_fallback_count}) for user {user_identifier}"
                        )
                        return {
                            "status": "validation_exit",
                            "message": "Validation limit exceeded, automation exited",
                            "matched_answer_id": None,
                            "matched_node_id": None,
                            "fallback_message": fallback_message
                        }
                    
                    # Validation failed but within limit - return retry
                    self.log_util.info(
                        service_name="ReplyValidationService",
                        message=f"[VALIDATE_REPLY] Text validation failed ({current_validation_count + 1}/{max_fallback_count}) for user {user_identifier}: {validation_error_message}"
                    )
                    return {
                        "status": "mismatch_retry",
                        "matched_answer_id": None,
                        "matched_node_id": None,
                        "fallback_message": fallback_message
                    }
                
                # Validation passed - save flow context variable and use default edge
                user_input_variable = current_node.get("userInputVariable", "")
                if user_input_variable:
                    # Save flow context variable for text question (validation passed)
                    await self.flow_db.save_or_update_flow_variable(
                        user_identifier=user_identifier,
                        brand_id=brand_id,
                        flow_id=flow_id,
                        variable_name=user_input_variable,
                        variable_value=user_reply,
                        node_id=current_node_id
                    )
                    self.log_util.info(
                        service_name="ReplyValidationService",
                        message=f"Saved flow context variable {user_input_variable} = {user_reply} for text question (validation passed)"
                    )
                
                # For text questions with passed validation, use default edge
                return {
                    "status": "use_default_edge",
                    "matched_answer_id": None,
                    "matched_node_id": None,
                    "fallback_message": None
                }
            
            # Step 4: Check if reply matches any button/list node in the entire flow (skip if is_text=True)
            if not is_text:
                mismatch_result = await self.handle_reply_mismatch(
                    flow=flow,
                    current_node=current_node,
                    user_reply=user_reply,
                    user_identifier=user_identifier,
                    brand_id=brand_id,
                    edges=edges
                )
                
                if mismatch_result["status"] == "matched_other_node":
                    # Matched in another node in the flow
                    return {
                        "status": "matched_other_node",
                        "matched_node_id": mismatch_result.get("matched_node_id"),
                        "matched_answer_id": None,
                        "fallback_message": None
                    }
            
            # Step 5: Check validation for button/list questions in current node (only reached if reply didn't match)
            node_type = current_node.get("type")
            if node_type in ("button_question", "list_question"):
                # Get max fallback count from current node (default 3)
                max_fallback_count = 3
                answer_validation = current_node.get("answerValidation")
                
                if answer_validation:
                    if isinstance(answer_validation, dict):
                        fails_count_str = answer_validation.get("failsCount", "3")
                    else:
                        fails_count_str = getattr(answer_validation, "failsCount", "3")
                    
                    try:
                        max_fallback_count = int(fails_count_str) if fails_count_str else 3
                    except (ValueError, TypeError):
                        max_fallback_count = 3
                
                # Get fallback message from node or use default
                fallback_message = "This is not the valid response. Please try again below"
                if answer_validation:
                    if isinstance(answer_validation, dict):
                        node_fallback = answer_validation.get("fallback", "")
                    else:
                        node_fallback = getattr(answer_validation, "fallback", "")
                    
                    if node_fallback and node_fallback.strip():
                        fallback_message = node_fallback.strip()
                
                # Check if current validation count >= max limit
                if current_validation_count >= max_fallback_count:
                    # Validation limit exceeded - exit automation
                    # Note: UserStateService will handle exiting automation and call node service
                    return {
                        "status": "validation_exit",
                        "message": "Validation limit exceeded, automation exited",
                        "matched_answer_id": None,
                        "matched_node_id": None,
                        "fallback_message": fallback_message  # Use node fallback message
                    }
                
                # For button/list questions, return retry with fallback message
                # Note: UserStateService will handle validation state updates
                return {
                    "status": "mismatch_retry",
                    "matched_answer_id": None,
                    "matched_node_id": None,
                    "fallback_message": fallback_message
                }
            else:
                # For other node types, use default edge (no validation needed)
                return {
                    "status": "use_default_edge",
                    "matched_answer_id": None,
                    "matched_node_id": None,
                    "fallback_message": None
                }
                
        except Exception as e:
            self.log_util.error(
                service_name="ReplyValidationService",
                message=f"[VALIDATE_REPLY] ❌ Exception in validate_and_match_reply: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="ReplyValidationService",
                message=f"[VALIDATE_REPLY] Traceback: {traceback.format_exc()}"
            )
            return {
                "status": "error",
                "message": str(e),
                "matched_answer_id": None,
                "matched_node_id": None,
                "fallback_message": None
            }

