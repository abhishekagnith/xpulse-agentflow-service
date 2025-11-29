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
from models.response.user.user_data import UserData
from models.response.brand.brand_info import BrandInfo

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
            # Note: Channel is saved at node level, not flow level
            # Status is always set to "draft" for create operations
            flow = FlowData(
                id=flow_data.get("id"),
                name=flow_data.get("name"),
                created=datetime.utcnow() if flow_data.get("created") is None else flow_data.get("created"),
                flowNodes=flow_data.get("flowNodes", []),
                flowEdges=flow_data.get("flowEdges", []),
                lastUpdated=flow_data.get("lastUpdated"),
                transform=flow_data.get("transform"),
                isPro=flow_data.get("isPro", False),
                status="draft",  # Always set to draft for create operations
                brand_id=brand_data.id,
                user_id=user_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Save to database - pass original flowNodes to preserve channel field
            original_flow_nodes = flow_data.get("flowNodes", [])
            saved_flow = await self.flow_db.create_flow(flow, original_flow_nodes=original_flow_nodes)
            
            # Save flow nodes separately
            # Use original flow_data nodes to preserve channel field (before Pydantic conversion)
            if flow_data.get("flowNodes"):
                nodes_list = flow_data.get("flowNodes", [])
                # Ensure all nodes are dicts
                processed_nodes = []
                for node in nodes_list:
                    if isinstance(node, dict):
                        processed_nodes.append(node)
                    elif hasattr(node, 'model_dump'):
                        # For Pydantic models, use model_dump with exclude_unset=False to preserve extra fields
                        node_dict = node.model_dump(exclude_unset=False, mode='json')
                        processed_nodes.append(node_dict)
                    else:
                        processed_nodes.append(dict(node))
                await self.flow_db.save_flow_nodes(saved_flow.id, processed_nodes)
            
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
        Get flow detail by MongoDB ID with transaction counts for each node.
        Transaction counts are only included if flow status is "published" or "stop".
        Draft flows do not include transaction counts.
        """
        try:
            flow = await self.flow_db.get_flow_by_id(flow_id)
            
            if flow is None:
                raise FlowServiceException(message="Flow not found")
            
            # Only get transaction counts if flow is published or stopped
            if flow.status == "published" or flow.status == "stop":
                # Get transaction counts grouped by node_id for this flow
                transaction_counts = await self.flow_db.get_transaction_counts_by_node(flow_id)
                
                # Add transaction count to each node in the flow
                updated_nodes = []
                for node in flow.flowNodes:
                    # Convert node to dict to add extra field
                    node_dict = None
                    if hasattr(node, 'model_dump'):
                        node_dict = node.model_dump(exclude_unset=False, mode='json')
                    elif isinstance(node, dict):
                        node_dict = node.copy()
                    else:
                        node_dict = dict(node)
                    
                    # Add transaction count for this node_id
                    node_id = node_dict.get("id")
                    transaction_count = transaction_counts.get(node_id, 0)
                    node_dict["transactionCount"] = transaction_count
                    
                    updated_nodes.append(node_dict)
                
                # Create a new FlowData with updated nodes
                flow_dict = flow.model_dump(exclude_unset=False, mode='json')
                flow_dict["flowNodes"] = updated_nodes
                
                # Return FlowData with transaction counts
                return FlowData.model_validate(flow_dict)
            else:
                # For draft flows, return flow without transaction counts
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
            
            # Create FlowData from the request
            # Note: Channel is saved at node level, not flow level
            # Status is always set to "draft" for update operations
            flow = FlowData(
                id=flow_id,  # Keep the same ID
                name=flow_data.get("name", existing_flow.name),
                created=existing_flow.created,  # Keep original created date
                flowNodes=flow_data.get("flowNodes", existing_flow.flowNodes),  # Replaces entire array if provided
                flowEdges=flow_data.get("flowEdges", existing_flow.flowEdges),  # Replaces entire array if provided
                lastUpdated=flow_data.get("lastUpdated"),
                transform=flow_data.get("transform", existing_flow.transform),
                isPro=flow_data.get("isPro", existing_flow.isPro),
                status="draft",  # Always set to draft for update operations
                brand_id=brand_data.id,
                user_id=user_id,
                created_at=existing_flow.created_at,  # Keep original created_at
                updated_at=datetime.utcnow()
            )
            
            # Update in database - pass original flowNodes to preserve channel field
            original_flow_nodes = flow_data.get("flowNodes") if "flowNodes" in flow_data else None
            updated_flow = await self.flow_db.update_flow(flow_id, flow, original_flow_nodes=original_flow_nodes)
            
            if updated_flow is None:
                raise FlowServiceException(message="Failed to update flow")
            
            # Update flow nodes separately (if provided in request)
            # Use original flow_data nodes to preserve channel field (before Pydantic conversion)
            if "flowNodes" in flow_data:
                nodes_list = flow_data.get("flowNodes", [])
                # Ensure all nodes are dicts
                processed_nodes = []
                for node in nodes_list:
                    if isinstance(node, dict):
                        processed_nodes.append(node)
                    elif hasattr(node, 'model_dump'):
                        # For Pydantic models, use model_dump with exclude_unset=False to preserve extra fields
                        node_dict = node.model_dump(exclude_unset=False, mode='json')
                        processed_nodes.append(node_dict)
                    else:
                        processed_nodes.append(dict(node))
                await self.flow_db.save_flow_nodes(flow_id, processed_nodes)
            
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
    
    async def update_flow_status(self, user_id: int, flow_id: str, status: str) -> FlowData:
        """
        Update flow status. Valid statuses: "draft", "published", "stop"
        
        Status transition rules:
        - draft -> published: Allowed
        - published -> stop: Allowed
        - stop -> published: Allowed (resume)
        - Any -> draft: Not allowed (use update API instead)
        """
        try:
            # Validate status
            valid_statuses = ["draft", "published", "stop"]
            if status not in valid_statuses:
                raise FlowServiceException(
                    message=f"Invalid status: {status}. Valid statuses are: {', '.join(valid_statuses)}"
                )
            
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
            
            # Validate status transitions
            current_status = existing_flow.status or "draft"
            
            # Don't allow changing to draft via status API (use update API instead)
            if status == "draft":
                raise FlowServiceException(
                    message="Cannot set status to 'draft' using status API. Use update API to modify flow content."
                )
            
            # Update the status field
            updated_flow = await self.flow_db.update_flow_status(flow_id, status)
            
            if updated_flow is None:
                raise FlowServiceException(message=f"Failed to update flow status to {status}")
            
            status_action = {
                "published": "published",
                "stop": "stopped"
            }.get(status, status)
            
            self.log_util.info(
                service_name="WhatsAppFlowService",
                message=f"Flow '{updated_flow.name}' {status_action} successfully with ID: {flow_id} (status: {current_status} -> {status})"
            )
            
            return updated_flow
            
        except FlowServiceException:
            raise
        except Exception as e:
            self.log_util.error(
                service_name="WhatsAppFlowService",
                message=f"Error updating flow status: {str(e)}"
            )
            raise FlowServiceException(message=f"Error updating flow status: {str(e)}")
    

