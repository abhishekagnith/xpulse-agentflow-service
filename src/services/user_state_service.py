from typing import Optional, Dict, Any, List
import httpx

# Utils
from utils.log_utils import LogUtil

# Database
from database.flow_db import FlowDB

# Services
from services.flow_service import FlowService

# Models
from models.user_data import UserData
from models.flow_data import FlowData
from models.request.process_node_request import ProcessNodeRequest
from models.response.process_node_response import ProcessNodeResponse


class UserStateService:
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB,
        flow_service: Optional[FlowService] = None,
        node_process_service: Optional[Any] = None,  # Channel-specific, made optional
        node_process_api_url: Optional[str] = None,  # API endpoint URL
    ):
        self.log_util = log_util
        self.flow_db = flow_db
        self.flow_service = flow_service
        self.node_process_service = node_process_service  # Kept for backward compatibility, but will use API
        # Default to localhost, but can be overridden for different deployments
        self.node_process_api_url = node_process_api_url or "http://localhost:8017/whatsapp/node/process"

    async def update_user_automation_state_after_message(
        self, 
        user_phone_number: str, 
        brand_id: int, 
        flow_id: str, 
        next_node_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update WhatsApp user table with automation state after successful message send
        Returns updated user state JSON or None
        """
        try:
            # Update user automation state with next node
            updated_user = await self.flow_db.update_user_automation_state(
                user_identifier=user_phone_number,
                brand_id=brand_id,
                is_in_automation=True,
                current_flow_id=flow_id,
                current_node_id=next_node_id
            )
            
            if updated_user:
                self.log_util.info(
                    service_name="WhatsAppUserStateService",
                    message=f"Updated user automation state: flow_id={flow_id}, current_node_id={next_node_id} for {user_phone_number}"
                )
                return updated_user.model_dump()
            else:
                self.log_util.warning(
                    service_name="WhatsAppUserStateService",
                    message=f"Failed to update user automation state for {user_phone_number}"
                )
                return None
                
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppUserStateService",
                message=f"Error updating user automation state: {str(e)}"
            )
            return None

    def _extract_user_input(self, message_type: str, message_body: Dict[str, Any]) -> Optional[str]:
        """
        Extract user input from different message types.
        """
        user_input = None
        if message_type == "button" and "button" in message_body:
            user_input = message_body["button"].get("text", message_body["button"].get("payload", ""))
        elif message_type == "text" and "text" in message_body:
            user_input = message_body["text"].get("body", "")
        elif message_type == "interactive" and "interactive" in message_body:
            interactive_data = message_body.get("interactive", {})
            if interactive_data.get("type") == "button_reply":
                button_reply = interactive_data.get("button_reply", {})
                user_input = button_reply.get("title", button_reply.get("id", ""))
            elif interactive_data.get("type") == "list_reply":
                list_reply = interactive_data.get("list_reply", {})
                user_input = list_reply.get("title", list_reply.get("id", ""))
        return user_input

    async def process_reply_match(
        self,
        source_node: Dict[str, Any],
        message_type: str,
        message_body: Dict[str, Any],
        edges: List[Any]
    ) -> Optional[str]:
        """
        Process when user reply matches the current node's expected answers in list and button questions.
        Returns the next_node_id if a match is found, None otherwise.
        """
        try:
            node_type = source_node.get("type")
            
            # Only process nodes that have expected answers
            if node_type not in ("trigger_template", "button_question", "list_question"):
                return None
            
            expected_answers = source_node.get("expectedAnswers", [])
            if not expected_answers:
                return None
            
            # Extract user input from different message types
            user_input = self._extract_user_input(message_type, message_body)
            if not user_input:
                return None
            
            # Match user input to expected answers
            for answer in expected_answers:
                expected_input = answer.get("expectedInput", "")
                if expected_input and expected_input.lower() == user_input.lower():
                    # Find the edge that connects from this answer to the next node
                    answer_id = answer.get("id")
                    for edge in edges:
                        if edge.source_node_id == answer_id:
                            return edge.target_node_id
            
            return None
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppUserStateService",
                message=f"Error processing reply match: {str(e)}"
            )
            return None

    async def _handle_question_node_reply(
        self,
        question_node: Dict[str, Any],
        message_type: str,
        message_body: Dict[str, Any],
        user_phone_number: str,
        brand_id: int,
        flow_id: str,
        node_id: str
    ) -> bool:
        """
        Handle user reply to a question node.
        ONLY extracts user's answer and saves to flow context table as a separate record.
        Does NOT change user state or find next node.
        
        Returns:
            bool: True if answer was saved successfully, False otherwise
        """
        try:
            # Extract user's answer
            user_answer = self._extract_user_input(message_type, message_body)
            
            if not user_answer:
                self.log_util.warning(
                    service_name="WhatsAppUserStateService",
                    message=f"Could not extract user answer from message for user {user_phone_number}"
                )
                user_answer = ""
            
            print(f"DEBUG: Extracted user answer: '{user_answer}'")
            
            # Get the variable name to store the answer
            user_input_variable = question_node.get("userInputVariable", "")
            
            # Only save if userInputVariable is provided
            if not user_input_variable:
                print(f"DEBUG: No userInputVariable defined, skipping save")
                self.log_util.info(
                    service_name="WhatsAppUserStateService",
                    message=f"Question node has no userInputVariable, skipping answer save for user {user_phone_number}"
                )
                return True
            
            print(f"DEBUG: Saving variable '{user_input_variable}' = '{user_answer}' as separate record")
            
            # Save this variable as its own record
            await self.flow_db.save_or_update_flow_variable(
                user_identifier=user_phone_number,
                brand_id=brand_id,
                flow_id=flow_id,
                variable_name=user_input_variable,
                variable_value=user_answer,
                node_id=node_id
            )
            
            print(f"DEBUG: Flow variable saved as new record in DB successfully")
            self.log_util.info(
                service_name="WhatsAppUserStateService",
                message=f"Saved user answer '{user_answer}' to {user_input_variable} (node: {node_id}) for user {user_phone_number} in flow {flow_id}"
            )
            return True
            
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppUserStateService",
                message=f"Error handling question node reply: {str(e)}"
            )
            return False

    async def _call_node_process_api(
        self,
        flow: FlowData,
        current_node_id: str,
        next_node_id: str,
        next_node_data: Dict[str, Any],
        user_identifier: str,
        brand_id: int,
        user_id: int,
        channel: str = "whatsapp",
        fallback_message: Optional[str] = None,
        user_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call the node process API endpoint to send node to channel service
        """
        try:
            # Convert datetime objects in user_state to strings for JSON serialization
            serializable_user_state = None
            if user_state:
                import json
                from datetime import datetime
                serializable_user_state = {}
                for key, value in user_state.items():
                    if isinstance(value, datetime):
                        serializable_user_state[key] = value.isoformat()
                    else:
                        serializable_user_state[key] = value
            
            request_data = ProcessNodeRequest(
                flow_id=flow.id,
                current_node_id=current_node_id,
                next_node_id=next_node_id,
                next_node_data=next_node_data,
                user_identifier=user_identifier,
                brand_id=brand_id,
                user_id=user_id,
                channel=channel,
                fallback_message=fallback_message,
                user_state=serializable_user_state
            )
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.node_process_api_url,
                    json=request_data.model_dump(mode='json'),
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    return ProcessNodeResponse(**response_data).model_dump()
                else:
                    self.log_util.error(
                        service_name="UserStateService",
                        message=f"Node process API returned error: {response.status_code} - {response.text}"
                    )
                    return {
                        "status": "error",
                        "message": f"Node process API error: {response.text}",
                        "flow_id": flow.id,
                        "next_node_id": next_node_id,
                        "automation_exited": False
                    }
                    
        except httpx.TimeoutException:
            self.log_util.error(
                service_name="UserStateService",
                message=f"Timeout calling node process API"
            )
            return {
                "status": "error",
                "message": "Timeout calling node process API",
                "flow_id": flow.id,
                "next_node_id": next_node_id,
                "automation_exited": False
            }
        except Exception as e:
            self.log_util.error(
                service_name="UserStateService",
                message=f"Error calling node process API: {str(e)}"
            )
            return {
                "status": "error",
                "message": f"Error calling node process API: {str(e)}",
                "flow_id": flow.id,
                "next_node_id": next_node_id,
                "automation_exited": False
            }

    async def _check_and_handle_validation(
        self,
        current_node_id: str,
        next_node_id: str,
        current_node_data: Dict[str, Any],
        user_state: Dict[str, Any],
        user_identifier: str,
        brand_id: int,
        user_id: int,
        channel: str = "whatsapp"
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
            # Reset validation on successful progression
            await self.flow_db.update_validation_state(
                user_identifier=user_identifier,
                brand_id=brand_id,
                validation_failed=False,
                failure_message=None
            )
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
        current_validation_count = user_state.get("validation_failure_count", 0)
        
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
                failure_message=fallback_message
            )
            
            self.log_util.info(
                service_name="UserStateService",
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
            error_message = "We cannot currently process your request. Please try again later"
            
            # Exit automation
            await self.flow_db.update_user_automation_state(
                user_identifier=user_identifier,
                brand_id=brand_id,
                is_in_automation=False,
                current_flow_id=None,
                current_node_id=None
            )
            
            # Reset validation state
            await self.flow_db.update_validation_state(
                user_identifier=user_identifier,
                brand_id=brand_id,
                validation_failed=False,
                failure_message=None
            )
            
            self.log_util.warning(
                service_name="UserStateService",
                message=f"Validation limit exceeded ({current_validation_count}/{max_fallback_count}) for user {user_identifier}, exiting automation"
            )
            
            return {
                "should_process": False,
                "should_exit": True,
                "validation_count": current_validation_count,
                "fallback_message": error_message
            }


    async def find_next_node_details(
        self,
        flow: FlowData,
        source_node_id: str,
        message_type: str,
        message_body: Dict[str, Any],
        user_phone_number: str,
        brand_id: int,
        user_id: int,
        existing_user: UserData
    ) -> Dict[str, Any]:
        """
        Orchestrator function that:
        1. Calls reply match/mismatch to identify next node
        2. Calls process_flow_node with node JSON, fallback message, and user state
        3. Returns success/failure with updated user state JSON
        """
        def _node_to_dict(node: Any) -> Dict[str, Any]:
            if hasattr(node, "model_dump"):
                return node.model_dump()
            if isinstance(node, dict):
                return node
            return dict(node)

        try:
            self.log_util.info(
                service_name="UserStateService",
                message=f"[FIND_NEXT_NODE] Starting find_next_node_details for user {user_phone_number}, flow_id: {flow.id}, source_node_id: {source_node_id}"
            )
            # Get edges
            edges = await self.flow_db.get_flow_edges(flow.id)
            self.log_util.info(
                service_name="UserStateService",
                message=f"[FIND_NEXT_NODE] Retrieved {len(edges) if edges else 0} edges for flow {flow.id}"
            )
            if not edges:
                self.log_util.error(
                    service_name="UserStateService",
                    message=f"[FIND_NEXT_NODE] ❌ No edges found for flow {flow.id}"
                )
                return {
                    "status": "error",
                    "message": "No edges found for flow",
                    "user_state": None
                }

            # Get source node
            source_node = None
            for node in flow.flowNodes:
                node_dict = _node_to_dict(node)
                if node_dict.get("id") == source_node_id:
                    source_node = node_dict
                    break

            if not source_node:
                return {
                    "status": "error",
                    "message": f"Source node {source_node_id} not found",
                    "user_state": None
                }

            node_type = source_node.get("type")
            
            # STEP 0: Special handling for question nodes - save user answer and continue
            if node_type == "question":
                print(f"\n{'='*80}")
                print(f"DEBUG: Source node is QUESTION type, saving answer to flow_context")
                print(f"Question Node ID: {source_node_id}")
                print(f"{'='*80}\n")
                
                # Save user's answer to flow_context (doesn't change user state)
                answer_saved = await self._handle_question_node_reply(
                    question_node=source_node,
                    message_type=message_type,
                    message_body=message_body,
                    user_phone_number=user_phone_number,
                    brand_id=brand_id,
                    flow_id=flow.id,
                    node_id=source_node_id
                )
                
                if not answer_saved:
                    self.log_util.warning(
                        service_name="WhatsAppUserStateService",
                        message=f"Failed to save question answer for user {user_phone_number}"
                    )
                
                print(f"DEBUG: Answer saved, now finding next node via default edge...")
                # Continue with normal flow - find default edge and process next node
                # Fall through to find next node using default edge logic
            
            # STEP 1: Try to match reply with expected answers
            matched_next_node_id = await self.process_reply_match(
                source_node=source_node,
                message_type=message_type,
                message_body=message_body,
                edges=edges
            )
            
            next_node_id = None
            next_node_data = None
            fallback_message = None
            should_update_validation = False
            
            # STEP 2: Determine flow based on match/mismatch
            if matched_next_node_id:
                # ✅ REPLY MATCHED
                next_node_id = matched_next_node_id
                
                # Get next node data
                for node in flow.flowNodes:
                    node_dict = _node_to_dict(node)
                    if node_dict.get("id") == next_node_id:
                        next_node_data = node_dict
                        break

            else:
                # ❌ REPLY DID NOT MATCH
                # ALWAYS check if reply matches any button/list node in flow (even from message nodes)
                mismatch_result = await self._handle_reply_mismatch_internal(
                    flow=flow,
                    current_node=source_node,
                    message_type=message_type,
                    message_body=message_body,
                    user_phone_number=user_phone_number,
                    brand_id=brand_id,
                    user_id=user_id,
                    existing_user=existing_user,
                    edges=edges
                )
                
                if mismatch_result["status"] == "handled":
                    # Mismatch was fully handled (matched other node or sent error)
                    return mismatch_result
                elif node_type in ("button_question", "list_question"):
                    # For button/list questions, retry current node with fallback
                    next_node_id = source_node_id
                    next_node_data = source_node
                    fallback_message = mismatch_result.get("fallback_message")
                    
                    # ⭐ CHECK VALIDATION - Reply didn't match, check validation count
                    user_state_dict = existing_user.model_dump() if existing_user else {}
                    validation_result = await self._check_and_handle_validation(
                        current_node_id=source_node_id,
                        next_node_id=next_node_id,
                        current_node_data=source_node,
                        user_state=user_state_dict,
                        user_identifier=user_phone_number,
                        brand_id=brand_id,
                        user_id=user_id,
                        channel="whatsapp"  # TODO: Get channel from context
                    )
                    
                    if validation_result["should_exit"]:
                        # Validation limit exceeded - exit automation
                        self.log_util.warning(
                            service_name="UserStateService",
                            message=f"Validation limit exceeded for user {user_phone_number}, exiting automation"
                        )
                        # Send exit message via node process API
                        if validation_result.get("fallback_message"):
                            try:
                                # Create a simple message node for exit message
                                exit_node_data = {
                                    "id": "exit_message",
                                    "type": "message",
                                    "flowReplies": [{
                                        "flowReplyType": "text",
                                        "data": validation_result["fallback_message"]
                                    }]
                                }
                                await self._call_node_process_api(
                                    flow=flow,
                                    current_node_id=source_node_id,
                                    next_node_id="exit_message",
                                    next_node_data=exit_node_data,
                                    user_identifier=user_phone_number,
                                    brand_id=brand_id,
                                    user_id=user_id,
                                    channel="whatsapp",  # TODO: Get channel from context
                                    fallback_message=None,
                                    user_state=user_state_dict
                                )
                            except Exception as e:
                                self.log_util.error(
                                    service_name="UserStateService",
                                    message=f"Error sending exit message: {str(e)}"
                                )
                        
                        # Get updated user state
                        updated_user = await self.flow_db.get_user_data(
                            user_identifier=user_phone_number,
                            brand_id=brand_id
                        )
                        return {
                            "status": "validation_exit",
                            "message": "Validation limit exceeded, automation exited",
                            "user_state": updated_user.model_dump() if updated_user else None
                        }
                    
                    # Update fallback message from validation result
                    if validation_result.get("fallback_message"):
                        fallback_message = validation_result["fallback_message"]
                    
                    # Refresh user state after validation update
                    existing_user = await self.flow_db.get_user_data(
                        user_phone_number=user_phone_number,
                        brand_id=brand_id
                    )
                    user_state_dict = existing_user.model_dump() if existing_user else {}
                    
                else:
                    # For other node types (message, question, etc.), use default edge
                    self.log_util.info(
                        service_name="UserStateService",
                        message=f"[FIND_NEXT_NODE] Looking for default edge from source_node_id: {source_node_id} (node_type: {node_type})"
                    )
                    for edge in edges:
                        self.log_util.info(
                            service_name="UserStateService",
                            message=f"[FIND_NEXT_NODE] Checking edge: source={edge.source_node_id}, target={edge.target_node_id}"
                        )
                        if edge.source_node_id == source_node_id:
                            next_node_id = edge.target_node_id
                            self.log_util.info(
                                service_name="UserStateService",
                                message=f"[FIND_NEXT_NODE] ✅ Found default edge: {source_node_id} -> {next_node_id}"
                            )
                            break
                    
                    if next_node_id:
                        self.log_util.info(
                            service_name="UserStateService",
                            message=f"[FIND_NEXT_NODE] Looking for next node data for node_id: {next_node_id}"
                        )
                        for node in flow.flowNodes:
                            node_dict = _node_to_dict(node)
                            if node_dict.get("id") == next_node_id:
                                next_node_data = node_dict
                                self.log_util.info(
                                    service_name="UserStateService",
                                    message=f"[FIND_NEXT_NODE] ✅ Found next node data: type={node_dict.get('type')}, id={next_node_id}"
                                )
                                break
                    else:
                        self.log_util.error(
                            service_name="UserStateService",
                            message=f"[FIND_NEXT_NODE] ❌ No default edge found from source_node_id: {source_node_id}. Available edges: {[(e.source_node_id, e.target_node_id) for e in edges]}"
                        )

            # STEP 3: Process the node if we have next node details
            if not next_node_id or not next_node_data:
                self.log_util.error(
                    service_name="UserStateService",
                    message=f"[FIND_NEXT_NODE] ❌ No next node found: next_node_id={next_node_id}, next_node_data={next_node_data is not None}"
                )
                return {
                    "status": "error",
                    "message": "No next node found",
                    "user_state": None
                }
            
            self.log_util.info(
                service_name="UserStateService",
                message=f"[FIND_NEXT_NODE] Calling node process API: current_node_id={source_node_id}, next_node_id={next_node_id}, node_type={next_node_data.get('type') if next_node_data else None}"
            )
            # STEP 3: Call node process API to send node to channel service
            user_state_dict = existing_user.model_dump() if existing_user else {}
            node_result = await self._call_node_process_api(
                    flow=flow,
                    current_node_id=source_node_id,
                    next_node_id=next_node_id,
                    next_node_data=next_node_data,
                user_identifier=user_phone_number,
                brand_id=brand_id,
                user_id=user_id,
                channel="whatsapp",  # TODO: Get channel from context or user state
                    fallback_message=fallback_message,
                user_state=user_state_dict
                )
            self.log_util.info(
                service_name="UserStateService",
                message=f"[FIND_NEXT_NODE] Node process API returned: status={node_result.get('status')}, message={node_result.get('message')}, automation_exited={node_result.get('automation_exited')}"
            )
                
            # Check if automation was exited (shouldn't happen from API, but handle it)
            if node_result.get("automation_exited") or node_result.get("status") == "validation_exit":
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"Automation exited for user {user_phone_number}"
                )
                # Get updated user state from DB
                updated_user = await self.flow_db.get_user_data(
                    user_identifier=user_phone_number,
                    brand_id=brand_id
                )
                return {
                    "status": "validation_exit",
                    "message": node_result.get("message", "Automation exited"),
                    "user_state": updated_user.model_dump() if updated_user else None
                }
                
            # Check if node processing was successful
            if node_result.get("status") != "success":
                return {
                    "status": "error",
                    "message": node_result.get("message", "Node processing failed"),
                    "user_state": None
                }
            
            # STEP 4: Update user state after successful node processing
            self.log_util.info(
                service_name="UserStateService",
                message=f"[FIND_NEXT_NODE] Updating user automation state: flow_id={flow.id}, next_node_id={next_node_id}"
            )
            updated_user_state = await self.update_user_automation_state_after_message(
                user_phone_number=user_phone_number,
                brand_id=brand_id,
                flow_id=flow.id,
                next_node_id=next_node_id
            )
            if updated_user_state:
                self.log_util.info(
                    service_name="UserStateService",
                    message=f"[FIND_NEXT_NODE] ✅ User state updated successfully: is_in_automation={updated_user_state.get('is_in_automation')}, current_flow_id={updated_user_state.get('current_flow_id')}, current_node_id={updated_user_state.get('current_node_id')}"
                )
            else:
                self.log_util.error(
                    service_name="UserStateService",
                    message=f"[FIND_NEXT_NODE] ❌ Failed to update user state"
                )
            
            print(f"\n{'='*80}")
            print(f"DEBUG: Reached STEP 4.5 - Chaining Logic")
            print(f"User: {user_phone_number}")
            print(f"Next Node ID: {next_node_id}")
            print(f"Next Node Type: {next_node_data.get('type')}")
            print(f"{'='*80}\n")
            
            # STEP 4.5: Auto-chain logic for transactional nodes (messages)
            # Continue processing nodes until we reach one that requires user input
            processed_node_type = next_node_data.get("type")
            
            if processed_node_type == "message":
                print(f"DEBUG: Processed node IS a message, checking chaining...")
                
                # Check what the next node is
                chain_result = await self.detect_and_chain_nodes(
                    flow=flow,
                    current_processed_node_id=next_node_id,
                    current_processed_node_data=next_node_data,
                    edges=edges
                )
                
                print(f"DEBUG: Chain result: {chain_result}")
                
                # If next node is also a message, chain recursively
                if chain_result.get("should_chain"):
                    chained_node_id = chain_result.get("next_node_id")
                    
                    print(f"DEBUG: Should chain to next message: {chained_node_id}")
                    
                    self.log_util.info(
                        service_name="WhatsAppUserStateService",
                        message=f"Auto-chaining from message {next_node_id} to message {chained_node_id}"
                    )
                    
                    # Get updated user data
                    updated_user = await self.flow_db.get_user_data(
                        user_phone_number=user_phone_number,
                        brand_id=brand_id
                    )
                    
                    # Recursively process next message node
                    return await self.find_next_node_details(
                        flow=flow,
                        source_node_id=chained_node_id,
                        message_type=message_type,
                        message_body=message_body,
                        user_phone_number=user_phone_number,
                        brand_id=brand_id,
                        user_id=user_id,
                        existing_user=updated_user
                    )
                
                # If next node requires user input (question/button/list), process it and stop
                elif chain_result.get("reason") == "next_node_requires_user_input":
                    print(f"DEBUG: Next node requires user input, processing it now...")
                    
                    next_edge_after_message = None
                    for edge in edges:
                        if edge.source_node_id == next_node_id:
                            next_edge_after_message = edge
                            break
                    
                    print(f"DEBUG: Found edge after message: {next_edge_after_message is not None}")
                    
                    if next_edge_after_message:
                        final_node_id = next_edge_after_message.target_node_id
                        final_node_data = None
                        
                        for node in flow.flowNodes:
                            node_dict = _node_to_dict(node)
                            if node_dict.get("id") == final_node_id:
                                final_node_data = node_dict
                                break
                        
                        print(f"DEBUG: Final node data found: {final_node_data is not None}")
                        print(f"DEBUG: Final node type: {final_node_data.get('type') if final_node_data else 'None'}")
                        
                        if final_node_data:
                            print(f"DEBUG: Processing final node {final_node_id}...")
                            
                            self.log_util.info(
                                service_name="UserStateService",
                                message=f"Processing user-input node {final_node_id} after message {next_node_id}, stopping chain"
                            )
                            
                            # Process the node that requires user input via API
                            final_node_result = await self._call_node_process_api(
                                flow=flow,
                                current_node_id=next_node_id,
                                next_node_id=final_node_id,
                                next_node_data=final_node_data,
                                user_identifier=user_phone_number,
                                brand_id=brand_id,
                                user_id=user_id,
                                channel="whatsapp",  # TODO: Get channel from context
                                fallback_message=None,
                                user_state=updated_user_state
                            )
                            
                            print(f"DEBUG: Final node result: {final_node_result}")
                            
                            if final_node_result["status"] == "success":
                                print(f"DEBUG: Final node processed successfully, updating state...")
                                
                                # Update user state to the node requiring input
                                final_user_state = await self.update_user_automation_state_after_message(
                                    user_phone_number=user_phone_number,
                                    brand_id=brand_id,
                                    flow_id=flow.id,
                                    next_node_id=final_node_id
                                )
                                
                                print(f"DEBUG: Chain complete! User state updated to {final_node_id}")
                                
                                return {
                                    "status": "success",
                                    "message": "Chain complete, waiting for user input",
                                    "user_state": final_user_state,
                                    "next_node_id": final_node_id,
                                    "processed_node_type": final_node_data.get("type")
                                }
            
            # STEP 5: Check if automation is still active and if there's a next node
            if updated_user_state and updated_user_state.get("is_in_automation"):
                # Check if there's a next node available in the flow
                has_next_node = False
                
                # For question nodes (button/list), check if they have expected answers
                # The edges are from answer IDs, not the node ID itself
                if next_node_data.get("type") in ("button_question", "list_question"):
                    expected_answers = next_node_data.get("expectedAnswers", [])
                    if expected_answers and len(expected_answers) > 0:
                        # Question nodes with answers are waiting for user response
                        has_next_node = True
                else:
                    # For other node types, check edges directly from the node
                    for edge in edges:
                        if edge.source_node_id == next_node_id:
                            has_next_node = True
                            break

                # If no next node, exit automation
                if not has_next_node:
                    self.log_util.info(
                        service_name="WhatsAppUserStateService",
                        message=f"No next node found after {next_node_id}, exiting automation for user {user_phone_number}"
                    )
                    # Set is_in_automation to False
                    await self.flow_db.update_user_automation_state(
                        user_identifier=user_phone_number,
                        brand_id=brand_id,
                        is_in_automation=False
                    )
                    
                    # Get updated user state
                    updated_user = await self.flow_db.get_user_data(
                        user_phone_number=user_phone_number,
                        brand_id=brand_id
                    )
                    
                    return {
                        "status": "success",
                        "message": "Flow completed, automation exited",
                        "user_state": updated_user.model_dump() if updated_user else None,
                        "next_node_id": next_node_id,
                        "processed_node_type": next_node_data.get("type"),
                        "flow_completed": True
                    }
            
            return {
                "status": "success",
                "message": "Node processed successfully",
                "user_state": updated_user_state,
                "next_node_id": next_node_id,
                "processed_node_type": next_node_data.get("type")
            }
            
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppUserStateService",
                message=f"Error in find_next_node_details: {str(e)}"
            )
            return {
                "status": "error",
                "message": str(e),
                "user_state": None
            }

    async def detect_and_chain_nodes(
        self,
        flow: FlowData,
        current_processed_node_id: str,
        current_processed_node_data: Dict[str, Any],
        edges: List[Any]
    ) -> Dict[str, Any]:
        """
        Detect if the currently processed node should automatically chain to the next node.
        This handles transactional nodes (like message nodes) that don't require user input.
        
        Args:
            flow: Complete flow object
            current_processed_node_id: The node that was just processed
            current_processed_node_data: The complete node JSON that was just processed
            edges: List of flow edges
            
        Returns:
            Dict with keys:
                - should_chain: bool - whether to chain to next node
                - next_node_id: str - next node to process (if should_chain=True)
                - next_node_data: dict - next node JSON (if should_chain=True)
                - reason: str - reason for decision
        """
        try:
            # Get the type of node that was just processed
            processed_node_type = current_processed_node_data.get("type")
            
            # Only message nodes should auto-chain
            if processed_node_type != "message":
                return {
                    "should_chain": False,
                    "reason": "node_not_message_type"
                }
            
            # Find the next edge from the current processed node
            next_edge = None
            for edge in edges:
                if edge.source_node_id == current_processed_node_id:
                    next_edge = edge
                    break
            
            # If no next edge, stop chaining
            if not next_edge:
                return {
                    "should_chain": False,
                    "reason": "no_next_edge"
                }
            
            # Get the next node data
            def _node_to_dict(node: Any) -> Dict[str, Any]:
                if hasattr(node, "model_dump"):
                    return node.model_dump()
                if isinstance(node, dict):
                    return node
                return dict(node)
            
            next_node_id = next_edge.target_node_id
            next_node_data = None
            
            for node in flow.flowNodes:
                node_dict = _node_to_dict(node)
                if node_dict.get("id") == next_node_id:
                    next_node_data = node_dict
                    break
            
            if not next_node_data:
                return {
                    "should_chain": False,
                    "reason": "next_node_not_found"
                }
            
            # Get next node type
            next_node_type = next_node_data.get("type")
            
            # If next node requires user input, stop chaining
            if next_node_type in ("button_question", "list_question", "question"):
                return {
                    "should_chain": False,
                    "reason": "next_node_requires_user_input"
                }
            
            # If next node is a message, chain to it
            if next_node_type == "message":
                return {
                    "should_chain": True,
                    "next_node_id": next_node_id,
                    "next_node_data": next_node_data,
                    "reason": "next_node_is_message"
                }
            
            # Unknown node type - stop chaining
            return {
                "should_chain": False,
                "reason": "unknown_next_node_type"
            }
            
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppUserStateService",
                message=f"Error in detect_and_chain_nodes: {str(e)}"
            )
            return {
                "should_chain": False,
                "reason": "error",
                "error": str(e)
            }

    async def _handle_reply_mismatch_internal(
        self,
        flow: FlowData,
        current_node: Dict[str, Any],
        message_type: str,
        message_body: Dict[str, Any],
        user_phone_number: str,
        brand_id: int,
        user_id: int,
        existing_user: UserData,
        edges: List[Any]
    ) -> Dict[str, Any]:
        """
        Internal handler for reply mismatch. Returns status and instructions.
        """
        try:
            # Extract user input
            user_input = self._extract_user_input(message_type, message_body)
            if not user_input:
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
                        if expected_input and expected_input.lower() == user_input.lower():
                            matched_node_id = node_dict.get("id")
                            matched_answer_id = answer.get("id")
                            break
                    if matched_node_id:
                        break
            
            # If match found in another node, process that node's next edge
            if matched_node_id and matched_answer_id:
                next_node_id = None
                for edge in edges:
                    if edge.source_node_id == matched_answer_id:
                        next_node_id = edge.target_node_id
                        break

                if next_node_id:
                    next_node_data = None
                    for node in flow.flowNodes:
                        node_dict = _node_to_dict(node)
                        if node_dict.get("id") == next_node_id:
                            next_node_data = node_dict
                            break

                if next_node_data:
                    self.log_util.info(
                        service_name="UserStateService",
                        message=f"User input '{user_input}' matched node {matched_node_id}, processing next node {next_node_id}"
                    )
                    node_result = await self._call_node_process_api(
                        flow=flow,
                        current_node_id=matched_node_id,
                        next_node_id=next_node_id,
                        next_node_data=next_node_data,
                        user_identifier=user_phone_number,
                        brand_id=brand_id,
                        user_id=user_id,
                        channel="whatsapp",  # TODO: Get channel from context
                        fallback_message=None,
                        user_state=existing_user.model_dump() if existing_user else None
                    )
                    
                    # Update user state after successful node processing
                    if node_result["status"] == "success":
                        updated_user_state = await self.update_user_automation_state_after_message(
                            user_phone_number=user_phone_number,
                            brand_id=brand_id,
                            flow_id=flow.id,
                            next_node_id=next_node_id
                        )
                        
                        return {
                            "status": "handled",
                            "message": "Matched in another node",
                            "user_state": updated_user_state
                        }
                    else:
                        return {
                            "status": "error",
                            "message": node_result["message"]
                        }
            
            # No match found anywhere in flow - return retry status
            # The node processor will handle validation count and send appropriate message
            return {
                "status": "retry",
                "fallback_message": None,  # Let node processor handle the message
                "message": "Reply did not match, retrying current node"
            }
                
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppUserStateService",
                message=f"Error handling reply mismatch: {str(e)}"
            )
            return {
                "status": "error",
                "message": str(e)
            }

    async def check_and_process_user_with_flow(
        self,
        sender: str,
        brand_id: int,
        user_id: int,
        waba_id: str,
        phone_number_id: str,
        message_type: str,
        message_body: Dict[str, Any],
        channel: str = "whatsapp",
    ) -> None:
        """
        Check/create user and process flow automation based on user state
        1. If user doesn't exist: create user → check triggers → if match, initiate flow
        2. If user exists: check current_node_id → find next node from edges → process next node
        """
        try:
            existing_user = await self.flow_db.get_user_data(
                user_identifier=sender,
                brand_id=brand_id
            )

            if existing_user is None:
                new_user = UserData(
                    user_phone_number=sender,
                    brand_id=brand_id,
                    user_id=user_id,
                    channel=channel,
                    channel_identifier=waba_id,
                    phone_number_id=phone_number_id
                )
                saved_user = await self.flow_db.save_user_data(new_user)
                if not saved_user:
                    self.log_util.error(
                        service_name="WhatsAppUserStateService",
                        message=f"Failed to create user record for phone number: {sender}, brand_id: {brand_id}"
                    )
                    return
                self.log_util.info(
                    service_name="WhatsAppUserStateService",
                    message=f"Created new user record for phone number: {sender}, brand_id: {brand_id}"
                )

                if self.flow_service:
                    self.log_util.info(
                        service_name="WhatsAppUserStateService",
                        message=f"[TRIGGER_FLOW] Checking triggers for new user {sender}, brand_id: {brand_id}, message_type: {message_type}"
                    )
                    trigger_result = await self.flow_service.check_and_get_flow_for_trigger(
                        brand_id=brand_id,
                        message_type=message_type,
                        message_body=message_body
                    )

                    if trigger_result:
                        flow_id, trigger_node_id = trigger_result
                        self.log_util.info(
                            service_name="WhatsAppUserStateService",
                            message=f"[TRIGGER_FLOW] ✅ Trigger matched! flow_id: {flow_id}, trigger_node_id: {trigger_node_id}"
                        )
                        flow = await self.flow_db.get_flow_by_id(flow_id)
                        if flow:
                            self.log_util.info(
                                service_name="WhatsAppUserStateService",
                                message=f"[TRIGGER_FLOW] ✅ Flow retrieved successfully: {flow.name} (id: {flow_id})"
                            )
                            # Get the newly created user to pass as existing_user
                            new_user_data = await self.flow_db.get_user_data(
                                user_identifier=sender,
                                brand_id=brand_id
                            )
                            self.log_util.info(
                                service_name="WhatsAppUserStateService",
                                message=f"[TRIGGER_FLOW] ✅ User data retrieved for {sender}"
                            )
                            
                            # Find the edge from trigger node to get the first processable node
                            # Trigger nodes are not processable - we need to find the next node via edge
                            self.log_util.info(
                                service_name="WhatsAppUserStateService",
                                message=f"[TRIGGER_FLOW] Looking for edge from trigger node {trigger_node_id} to first processable node"
                            )
                            edges = await self.flow_db.get_flow_edges(flow_id)
                            self.log_util.info(
                                service_name="WhatsAppUserStateService",
                                message=f"[TRIGGER_FLOW] Retrieved {len(edges)} edges for flow {flow_id}"
                            )
                            first_processable_node_id = None
                            
                            for edge in edges:
                                self.log_util.info(
                                    service_name="WhatsAppUserStateService",
                                    message=f"[TRIGGER_FLOW] Checking edge: source={edge.source_node_id}, target={edge.target_node_id}"
                                )
                                if edge.source_node_id == trigger_node_id:
                                    first_processable_node_id = edge.target_node_id
                                    self.log_util.info(
                                        service_name="WhatsAppUserStateService",
                                        message=f"[TRIGGER_FLOW] ✅ Found first processable node {first_processable_node_id} from trigger node {trigger_node_id}"
                                    )
                                    break
                            
                            if not first_processable_node_id:
                                self.log_util.error(
                                    service_name="WhatsAppUserStateService",
                                    message=f"[TRIGGER_FLOW] ❌ No edge found from trigger node {trigger_node_id} to first processable node. Available edges: {[(e.source_node_id, e.target_node_id) for e in edges]}"
                                )
                                return
                            
                            # Call find_next_node_details orchestrator with the first processable node (not the trigger node)
                            self.log_util.info(
                                service_name="WhatsAppUserStateService",
                                message=f"[TRIGGER_FLOW] Calling find_next_node_details with source_node_id: {first_processable_node_id}"
                            )
                            result = await self.find_next_node_details(
                                flow=flow,
                                source_node_id=first_processable_node_id,
                                message_type=message_type,
                                message_body=message_body,
                                    user_phone_number=sender,
                                    brand_id=brand_id,
                                    user_id=user_id,
                                existing_user=new_user_data
                            )
                            
                            self.log_util.info(
                                service_name="WhatsAppUserStateService",
                                message=f"[TRIGGER_FLOW] find_next_node_details returned: status={result.get('status')}, message={result.get('message')}, next_node_id={result.get('next_node_id')}"
                            )
                            
                            # Log result
                            if result["status"] == "success":
                                self.log_util.info(
                                    service_name="WhatsAppUserStateService",
                                    message=f"[TRIGGER_FLOW] ✅ Successfully initiated flow for new user {sender}. Next node: {result.get('next_node_id')}"
                                )
                            elif result["status"] == "handled":
                                self.log_util.info(
                                    service_name="WhatsAppUserStateService",
                                    message=f"[TRIGGER_FLOW] ✅ Handled special case for new user {sender}: {result.get('message')}"
                                )
                            else:
                                self.log_util.error(
                                    service_name="WhatsAppUserStateService",
                                    message=f"[TRIGGER_FLOW] ❌ Error initiating flow for new user {sender}: status={result.get('status')}, message={result.get('message')}"
                                )
                        else:
                            self.log_util.error(
                                service_name="WhatsAppUserStateService",
                                message=f"[TRIGGER_FLOW] ❌ Failed to retrieve flow with id: {flow_id}"
                            )
                    else:
                        self.log_util.info(
                            service_name="WhatsAppUserStateService",
                            message=f"[TRIGGER_FLOW] ❌ No trigger matched for user {sender}, brand_id: {brand_id}, message_type: {message_type}"
                        )
                else:
                    self.log_util.warning(
                        service_name="WhatsAppUserStateService",
                        message=f"[TRIGGER_FLOW] ⚠️ FlowService is not initialized, cannot check triggers"
                    )
            else:
                # Existing user - check if in automation
                self.log_util.info(
                    service_name="WhatsAppUserStateService",
                    message=f"[EXISTING_USER] Processing existing user {sender}, is_in_automation: {existing_user.is_in_automation}, current_flow_id: {existing_user.current_flow_id}, current_node_id: {existing_user.current_node_id}"
                )
                if (
                    existing_user.is_in_automation
                    and existing_user.current_flow_id
                    and existing_user.current_node_id
                ):
                    self.log_util.info(
                        service_name="WhatsAppUserStateService",
                        message=f"[EXISTING_USER] User is in automation, retrieving flow {existing_user.current_flow_id}"
                    )
                    flow = await self.flow_db.get_flow_by_id(existing_user.current_flow_id)
                    if flow:
                        self.log_util.info(
                            service_name="WhatsAppUserStateService",
                            message=f"[EXISTING_USER] ✅ Flow retrieved: {flow.name}, calling find_next_node_details with source_node_id: {existing_user.current_node_id}"
                        )
                        # STEP 1: Call find_next_node_details orchestrator
                        result = await self.find_next_node_details(
                            flow=flow,
                            source_node_id=existing_user.current_node_id,
                            message_type=message_type,
                            message_body=message_body,
                                user_phone_number=sender,
                                brand_id=brand_id,
                                user_id=user_id,
                            existing_user=existing_user
                        )
                        self.log_util.info(
                            service_name="WhatsAppUserStateService",
                            message=f"[EXISTING_USER] find_next_node_details returned: status={result.get('status')}, message={result.get('message')}, next_node_id={result.get('next_node_id')}"
                        )
                        
                        # STEP 5: Update user state in DB based on result
                        if result["status"] == "success":
                            self.log_util.info(
                                service_name="WhatsAppUserStateService",
                                message=f"[EXISTING_USER] ✅ Successfully processed node for user {sender}. Next node: {result.get('next_node_id')}"
                            )
                            # User state already updated by find_next_node_details
                        elif result["status"] == "handled":
                            self.log_util.info(
                                service_name="WhatsAppUserStateService",
                                message=f"[EXISTING_USER] ✅ Handled special case for user {sender}: {result.get('message')}"
                            )
                            # User state already updated (e.g., validation limit exceeded)
                        else:
                            self.log_util.error(
                                service_name="WhatsAppUserStateService",
                                message=f"[EXISTING_USER] ❌ Error processing node for user {sender}: status={result.get('status')}, message={result.get('message')}"
                            )
                    else:
                        self.log_util.error(
                            service_name="WhatsAppUserStateService",
                            message=f"[EXISTING_USER] ❌ Failed to retrieve flow with id: {existing_user.current_flow_id}"
                        )
                else:
                    # User exists but not in automation - check for triggers
                    self.log_util.info(
                        service_name="WhatsAppUserStateService",
                        message=f"[EXISTING_USER] User exists but not in automation, checking for triggers"
                    )
                    if self.flow_service:
                        trigger_result = await self.flow_service.check_and_get_flow_for_trigger(
                            brand_id=brand_id,
                            message_type=message_type,
                            message_body=message_body
                        )

                        if trigger_result:
                            flow_id, trigger_node_id = trigger_result
                            flow = await self.flow_db.get_flow_by_id(flow_id)
                            if flow:
                                # Call find_next_node_details orchestrator (same as in-automation flow)
                                result = await self.find_next_node_details(
                                    flow=flow,
                                    source_node_id=trigger_node_id,
                                    message_type=message_type,
                                    message_body=message_body,
                                        user_phone_number=sender,
                                        brand_id=brand_id,
                                        user_id=user_id,
                                    existing_user=existing_user
                                )
                                
                                # Log result
                                if result["status"] == "success":
                                    self.log_util.info(
                                        service_name="WhatsAppUserStateService",
                                        message=f"Successfully initiated flow for user {sender}. Next node: {result.get('next_node_id')}"
                                    )
                                elif result["status"] == "handled":
                                    self.log_util.info(
                                        service_name="WhatsAppUserStateService",
                                        message=f"Handled special case for user {sender}: {result.get('message')}"
                                    )
                                else:
                                    self.log_util.error(
                                        service_name="WhatsAppUserStateService",
                                        message=f"Error initiating flow for user {sender}: {result.get('message')}"
                                    )
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppUserStateService",
                message=f"Error in check_and_process_user_with_flow: {str(e)}"
            )

