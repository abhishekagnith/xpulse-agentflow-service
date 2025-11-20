from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

# Utils
from utils.log_utils import LogUtil
from utils.environment_utils import EnvironmentUtils

# Database
from database.flow_db import FlowDB

# Services (for multitenancy validation)
from services.internal.user_service import UserService
from services.internal.brand_service import BrandService

# Models
from models.flow_data import FlowData
from models.flow_trigger_data import FlowTriggerData

# Exceptions
from exceptions.flow_exception import FlowServiceException

class FlowService:
    def __init__(self, log_util: LogUtil, environment_utils: EnvironmentUtils, flow_db: FlowDB, 
                 user_service: UserService, brand_service: BrandService):
        self.log_util = log_util
        self.environment_utils = environment_utils
        self.flow_db = flow_db
        self.user_service = user_service
        self.brand_service = brand_service
    
    async def create_flow(self, user_id: int, flow_data: dict) -> FlowData:
        """
        Create a new flow with multitenancy validation
        """
        try:
            # Validate user exists
            user_data = await self.user_service.get_user_info(user_id)
            if user_data is None:
                raise FlowServiceException(message="User not found")
            
            # Validate brand exists
            brand_data = await self.brand_service.get_brand_info(user_data.brand_id)
            if brand_data is None:
                raise FlowServiceException(message="Brand not found")
            
            # Create FlowData from the request
            flow = FlowData(
                id=flow_data.get("id"),
                name=flow_data.get("name"),
                created=datetime.utcnow() if flow_data.get("created") is None else flow_data.get("created"),
                flowNodes=flow_data.get("flowNodes", []),
                flowEdges=flow_data.get("flowEdges", []),
                lastUpdated=flow_data.get("lastUpdated"),
                transform=flow_data.get("transform"),
                isPro=flow_data.get("isPro", False),
                brand_id=brand_data.id,
                user_id=user_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Save to database
            saved_flow = await self.flow_db.create_flow(flow)
            
            # Save flow nodes separately
            if flow.flowNodes:
                nodes_list = []
                for node in flow.flowNodes:
                    if hasattr(node, 'model_dump'):
                        nodes_list.append(node.model_dump())
                    elif isinstance(node, dict):
                        nodes_list.append(node)
                    else:
                        nodes_list.append(dict(node))
                await self.flow_db.save_flow_nodes(saved_flow.id, nodes_list)
            
            # Save flow edges separately
            if flow.flowEdges:
                edges_list = []
                for edge in flow.flowEdges:
                    if hasattr(edge, 'model_dump'):
                        edges_list.append(edge.model_dump())
                    elif isinstance(edge, dict):
                        edges_list.append(edge)
                    else:
                        edges_list.append(dict(edge))
                await self.flow_db.save_flow_edges(saved_flow.id, edges_list)
            
            # Save flow triggers separately - find the start node
            if flow.flowNodes:
                start_node = None
                for node in flow.flowNodes:
                    node_dict = None
                    if hasattr(node, 'model_dump'):
                        node_dict = node.model_dump()
                    elif isinstance(node, dict):
                        node_dict = node
                    else:
                        node_dict = dict(node)
                    
                    if node_dict.get("isStartNode") is True:
                        start_node = node_dict
                        break
                
                if start_node:
                    trigger_type = None
                    trigger_values = []
                    
                    node_type = start_node.get("type")
                    if node_type == "trigger_keyword":
                        trigger_type = "keyword"
                        trigger_values = start_node.get("triggerKeywords", [])
                    elif node_type == "trigger_template":
                        trigger_type = "template"
                        expected_answers = start_node.get("expectedAnswers", [])
                        trigger_values = [answer.get("expectedInput", "") for answer in expected_answers if answer.get("expectedInput")]
                    
                    if trigger_type:
                        triggers_list = [{
                            "node_id": start_node.get("id"),
                            "trigger_type": trigger_type,
                            "trigger_values": trigger_values
                        }]
                        await self.flow_db.save_flow_triggers(saved_flow.id, triggers_list)
            
            self.log_util.info(
                service_name="WhatsAppFlowService",
                message=f"Flow '{flow.name}' created successfully with ID: {saved_flow.id}"
            )
            
            return saved_flow
            
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppFlowService",
                message=f"Error creating flow: {str(e)}"
            )
            raise FlowServiceException(message=f"Error creating flow: {str(e)}")
    
    async def get_flows_list(self, user_id: int) -> List[FlowData]:
        """
        Get list of flows for a user
        """
        try:
            # Get user info
            user_data: Optional[UserData] = await self.user_service.get_user_info(user_id)
            if user_data is None:
                raise FlowServiceException(message="User not found")
            
            # Get brand info
            brand_data: Optional[BrandInfo] = await self.brand_service.get_brand_info(user_data.brand_id)
            if brand_data is None:
                raise FlowServiceException(message="Brand not found")
            
            # Get flows from database
            flows = await self.flow_db.get_flows(brand_id=brand_data.id, user_id=user_id)
            
            if flows is None:
                return []
            
            return flows
            
        except FlowServiceException:
            raise
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppFlowService",
                message=f"Error getting flows list: {str(e)}"
            )
            raise FlowServiceException(message=f"Error getting flows list: {str(e)}")
    
    async def get_flow_detail(self, flow_id: str) -> FlowData:
        """
        Get flow detail by MongoDB ID
        """
        try:
            flow = await self.flow_db.get_flow_by_id(flow_id)
            
            if flow is None:
                raise FlowServiceException(message="Flow not found")
            
            return flow
            
        except FlowServiceException:
            raise
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppFlowService",
                message=f"Error getting flow detail: {str(e)}"
            )
            raise FlowServiceException(message=f"Error getting flow detail: {str(e)}")
    
    async def update_flow(self, user_id: int, flow_id: str, flow_data: dict) -> FlowData:
        """
        Update an existing flow by MongoDB ID
        """
        try:
            # Get user info
            user_data: Optional[UserData] = await self.user_service.get_user_info(user_id)
            if user_data is None:
                raise FlowServiceException(message="User not found")
            
            # Get brand info
            brand_data: Optional[BrandInfo] = await self.brand_service.get_brand_info(user_data.brand_id)
            if brand_data is None:
                raise FlowServiceException(message="Brand not found")
            
            # Check if flow exists and belongs to the user
            existing_flow = await self.flow_db.get_flow_by_id(flow_id)
            if existing_flow is None:
                raise FlowServiceException(message="Flow not found")
            
            # Verify the flow belongs to the user's brand
            if existing_flow.brand_id != brand_data.id or existing_flow.user_id != user_id:
                raise FlowServiceException(message="Unauthorized: Flow does not belong to this user")
            
            # Create FlowData from the request
            # Note: If flowNodes/flowEdges are provided, they REPLACE the entire array
            # - To delete nodes: send flowNodes with only the nodes you want to keep
            # - To keep all nodes: omit flowNodes from the request
            # - To delete all nodes: send flowNodes as an empty array []
            flow = FlowData(
                id=flow_id,  # Keep the same ID
                name=flow_data.get("name", existing_flow.name),
                created=existing_flow.created,  # Keep original created date
                flowNodes=flow_data.get("flowNodes", existing_flow.flowNodes),  # Replaces entire array if provided
                flowEdges=flow_data.get("flowEdges", existing_flow.flowEdges),  # Replaces entire array if provided
                lastUpdated=flow_data.get("lastUpdated"),
                transform=flow_data.get("transform", existing_flow.transform),
                isPro=flow_data.get("isPro", existing_flow.isPro),
                brand_id=brand_data.id,
                user_id=user_id,
                created_at=existing_flow.created_at,  # Keep original created_at
                updated_at=datetime.utcnow()
            )
            
            # Update in database
            updated_flow = await self.flow_db.update_flow(flow_id, flow)
            
            if updated_flow is None:
                raise FlowServiceException(message="Failed to update flow")
            
            # Update flow nodes separately (if provided in request)
            if "flowNodes" in flow_data:
                nodes_list = []
                for node in flow.flowNodes:
                    if hasattr(node, 'model_dump'):
                        nodes_list.append(node.model_dump())
                    elif isinstance(node, dict):
                        nodes_list.append(node)
                    else:
                        nodes_list.append(dict(node))
                await self.flow_db.save_flow_nodes(flow_id, nodes_list)
            
            # Update flow edges separately (if provided in request)
            if "flowEdges" in flow_data:
                edges_list = []
                for edge in flow.flowEdges:
                    if hasattr(edge, 'model_dump'):
                        edges_list.append(edge.model_dump())
                    elif isinstance(edge, dict):
                        edges_list.append(edge)
                    else:
                        edges_list.append(dict(edge))
                await self.flow_db.save_flow_edges(flow_id, edges_list)
            
            # Update flow triggers separately - find the start node (if flowNodes are provided)
            if "flowNodes" in flow_data and flow.flowNodes:
                start_node = None
                for node in flow.flowNodes:
                    node_dict = None
                    if hasattr(node, 'model_dump'):
                        node_dict = node.model_dump()
                    elif isinstance(node, dict):
                        node_dict = node
                    else:
                        node_dict = dict(node)
                    
                    if node_dict.get("isStartNode") is True:
                        start_node = node_dict
                        break
                
                if start_node:
                    trigger_type = None
                    trigger_values = []
                    
                    node_type = start_node.get("type")
                    if node_type == "trigger_keyword":
                        trigger_type = "keyword"
                        trigger_values = start_node.get("triggerKeywords", [])
                    elif node_type == "trigger_template":
                        trigger_type = "template"
                        expected_answers = start_node.get("expectedAnswers", [])
                        trigger_values = [answer.get("expectedInput", "") for answer in expected_answers if answer.get("expectedInput")]
                    
                    if trigger_type:
                        triggers_list = [{
                            "node_id": start_node.get("id"),
                            "trigger_type": trigger_type,
                            "trigger_values": trigger_values
                        }]
                        await self.flow_db.save_flow_triggers(flow_id, triggers_list)
            
            self.log_util.info(
                service_name="WhatsAppFlowService",
                message=f"Flow '{flow.name}' updated successfully with ID: {flow_id}"
            )
            
            return updated_flow
            
        except FlowServiceException:
            raise
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppFlowService",
                message=f"Error updating flow: {str(e)}"
            )
            raise FlowServiceException(message=f"Error updating flow: {str(e)}")
    
    async def check_and_get_flow_for_trigger(self, brand_id: int, message_type: str, message_body: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        """
        Check user message against available triggers and return flow_id and node_id if match found
        Returns: (flow_id, node_id) tuple if match found, None otherwise
        """
        try:
            self.log_util.info(
                service_name="WhatsAppFlowService",
                message=f"[TRIGGER_CHECK] Starting trigger check for brand_id: {brand_id}, message_type: {message_type}"
            )
            # Extract text content from message body based on message type
            text_content = None
            
            if message_type == "text":
                # Extract text from text message
                if message_body.get("type") == "text" and "text" in message_body:
                    text_content = message_body["text"].get("body", "").strip()
                    self.log_util.info(
                        service_name="WhatsAppFlowService",
                        message=f"[TRIGGER_CHECK] Extracted text content: '{text_content}'"
                    )
            
            elif message_type == "button":
                # Extract text from button message (button text or payload)
                if message_body.get("type") == "button" and "button" in message_body:
                    button_data = message_body["button"]
                    # Prefer text over payload, but use payload if text is not available
                    text_content = button_data.get("text", button_data.get("payload", "")).strip()
                    self.log_util.info(
                        service_name="WhatsAppFlowService",
                        message=f"[TRIGGER_CHECK] Extracted button content: '{text_content}'"
                    )
            
            if not text_content:
                self.log_util.warning(
                    service_name="WhatsAppFlowService",
                    message=f"[TRIGGER_CHECK] ❌ No text content extracted from message_body: {message_body}"
                )
                return None
            
            # Get all triggers for this brand
            self.log_util.info(
                service_name="WhatsAppFlowService",
                message=f"[TRIGGER_CHECK] Fetching triggers for brand_id: {brand_id}"
            )
            triggers = await self.flow_db.get_flow_triggers_by_brand_id(brand_id)
            if triggers is None or len(triggers) == 0:
                self.log_util.warning(
                    service_name="WhatsAppFlowService",
                    message=f"[TRIGGER_CHECK] ❌ No triggers found for brand_id: {brand_id}"
                )
                return None
            
            self.log_util.info(
                service_name="WhatsAppFlowService",
                message=f"[TRIGGER_CHECK] Found {len(triggers)} triggers to check against text: '{text_content}'"
            )
            
            # Check each trigger
            for trigger in triggers:
                self.log_util.info(
                    service_name="WhatsAppFlowService",
                    message=f"[TRIGGER_CHECK] Checking trigger: type={trigger.trigger_type}, flow_id={trigger.flow_id}, node_id={trigger.node_id}, values={trigger.trigger_values}"
                )
                if trigger.trigger_type == "keyword":
                    # Keyword triggers only work with text messages
                    if message_type == "text":
                        # Check if message text contains any keyword (case-insensitive)
                        for keyword in trigger.trigger_values:
                            self.log_util.info(
                                service_name="WhatsAppFlowService",
                                message=f"[TRIGGER_CHECK] Comparing keyword '{keyword}' (lower: '{keyword.lower()}') with text '{text_content}' (lower: '{text_content.lower()}')"
                            )
                            if keyword.lower() in text_content.lower():
                                self.log_util.info(
                                    service_name="WhatsAppFlowService",
                                    message=f"[TRIGGER_CHECK] ✅ Keyword trigger matched: '{keyword}' in message '{text_content}' for flow_id: {trigger.flow_id}, node_id: {trigger.node_id}"
                                )
                                return (trigger.flow_id, trigger.node_id)
                            else:
                                self.log_util.info(
                                    service_name="WhatsAppFlowService",
                                    message=f"[TRIGGER_CHECK] ❌ Keyword '{keyword}' not found in '{text_content}'"
                                )
                    else:
                        self.log_util.info(
                            service_name="WhatsAppFlowService",
                            message=f"[TRIGGER_CHECK] Skipping keyword trigger (message_type is '{message_type}', not 'text')"
                        )
                
                elif trigger.trigger_type == "template":
                    # Template triggers work with both text and button messages
                    # Check if message text/button exactly matches any expected button text (case-insensitive)
                    for button_text in trigger.trigger_values:
                        self.log_util.info(
                            service_name="WhatsAppFlowService",
                            message=f"[TRIGGER_CHECK] Comparing template button '{button_text}' (lower: '{button_text.lower()}') with text '{text_content}' (lower: '{text_content.lower()}')"
                        )
                        if button_text.lower() == text_content.lower():
                            self.log_util.info(
                                service_name="WhatsAppFlowService",
                                message=f"[TRIGGER_CHECK] ✅ Template trigger matched: '{button_text}' matches message '{text_content}' (type: {message_type}) for flow_id: {trigger.flow_id}, node_id: {trigger.node_id}"
                            )
                            return (trigger.flow_id, trigger.node_id)
                        else:
                            self.log_util.info(
                                service_name="WhatsAppFlowService",
                                message=f"[TRIGGER_CHECK] ❌ Template button '{button_text}' does not match '{text_content}'"
                            )
            
            self.log_util.info(
                service_name="WhatsAppFlowService",
                message=f"[TRIGGER_CHECK] ❌ No trigger matched for text: '{text_content}'"
            )
            return None
            
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppFlowService",
                message=f"[TRIGGER_CHECK] ❌ Error checking triggers: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="WhatsAppFlowService",
                message=f"[TRIGGER_CHECK] Traceback: {traceback.format_exc()}"
            )
            return None

