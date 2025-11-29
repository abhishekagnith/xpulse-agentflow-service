from typing import Optional, Dict, Any, List
import httpx

# Utils
from utils.log_utils import LogUtil

# Database
from database.flow_db import FlowDB

# Models
from models.flow_data import FlowData
from models.request.process_node_request import ProcessNodeRequest
from models.response.process_node_response import ProcessNodeResponse


class WhatsAppFlowService:
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB,
        node_process_api_url: Optional[str] = None,
    ):
        self.log_util = log_util
        self.flow_db = flow_db
        # Default to localhost, but can be overridden for different deployments
        self.node_process_api_url = node_process_api_url or "http://localhost:8017/whatsapp/node/process"

    def _extract_user_input(self, message_type: str, message_body: Dict[str, Any]) -> Optional[str]:
        """
        Extract user input from different message types.
        First checks for normalized 'user_reply' key, then falls back to raw message structure.
        """
        # First check for normalized user_reply (from webhook adapter)
        if "user_reply" in message_body:
            return message_body["user_reply"]
        
        # Fall back to raw message structure
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

    async def handle_question_node_reply(
        self,
        question_node: Dict[str, Any],
        message_type: str,
        message_body: Dict[str, Any],
        user_identifier: str,
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
                    service_name="WhatsAppFlowService",
                    message=f"Could not extract user answer from message for user {user_identifier}"
                )
                user_answer = ""
            
            print(f"DEBUG: Extracted user answer: '{user_answer}'")
            
            # Get the variable name to store the answer
            user_input_variable = question_node.get("userInputVariable", "")
            
            # Only save if userInputVariable is provided
            if not user_input_variable:
                print(f"DEBUG: No userInputVariable defined, skipping save")
                self.log_util.info(
                    service_name="WhatsAppFlowService",
                    message=f"Question node has no userInputVariable, skipping answer save for user {user_identifier}"
                )
                return True
            
            print(f"DEBUG: Saving variable '{user_input_variable}' = '{user_answer}' as separate record")
            
            # Save this variable as its own record
            await self.flow_db.save_or_update_flow_variable(
                user_identifier=user_identifier,
                brand_id=brand_id,
                flow_id=flow_id,
                variable_name=user_input_variable,
                variable_value=user_answer,
                node_id=node_id
            )
            
            print(f"DEBUG: Flow variable saved as new record in DB successfully")
            self.log_util.info(
                service_name="WhatsAppFlowService",
                message=f"Saved user answer '{user_answer}' to {user_input_variable} (node: {node_id}) for user {user_identifier} in flow {flow_id}"
            )
            return True
            
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppFlowService",
                message=f"Error handling question node reply: {str(e)}"
            )
            return False

    async def call_node_process_api(
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
        is_validation_error: bool = False,
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
                is_validation_error=is_validation_error,
                user_state=serializable_user_state
            )
            
            # Log the request being sent to node process API
            request_json = request_data.model_dump(mode='json')
            self.log_util.info(
                service_name="WhatsAppFlowService",
                message=f"[NODE_PROCESS_API] Sending request to {self.node_process_api_url}: "
                        f"flow_id={flow.id}, current_node_id={current_node_id}, "
                        f"next_node_id={next_node_id}, next_node_type={next_node_data.get('type') if next_node_data else None}, "
                        f"is_validation_error={is_validation_error}, fallback_message={'present' if fallback_message else 'None'}"
            )
            self.log_util.debug(
                service_name="WhatsAppFlowService",
                message=f"[NODE_PROCESS_API] Full request payload: {request_json}"
            )
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.node_process_api_url,
                    json=request_json,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    return ProcessNodeResponse(**response_data).model_dump()
                else:
                    self.log_util.error(
                        service_name="WhatsAppFlowService",
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
                service_name="WhatsAppFlowService",
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
                service_name="WhatsAppFlowService",
                message=f"Error calling node process API: {str(e)}"
            )
            return {
                "status": "error",
                "message": f"Error calling node process API: {str(e)}",
                "flow_id": flow.id,
                "next_node_id": next_node_id,
                "automation_exited": False
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
                service_name="WhatsAppFlowService",
                message=f"Error in detect_and_chain_nodes: {str(e)}"
            )
            return {
                "should_chain": False,
                "reason": "error",
                "error": str(e)
            }

