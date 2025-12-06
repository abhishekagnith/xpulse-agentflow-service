from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import urllib.parse
import threading
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
import weakref
from pymongo.errors import NetworkTimeout, ServerSelectionTimeoutError, ConnectionFailure

# Utils
from utils.log_utils import LogUtil
from utils.environment_utils import EnvironmentUtils

# Exceptions
from exceptions.flow_exception import FlowDBException

# Models
from models.flow_data import FlowData
from models.flow_trigger_data import FlowTriggerData
from models.flow_user_context import FlowUserContext
from models.user_data import UserData
from models.webhook_message_data import WebhookMessageData
from models.webhook_adapter_processed_data import WebhookAdapterProcessedData
from models.node_detail_data import NodeDetailData
from models.user_detail import UserDetail

"""
Database class for flow operations
"""
class FlowDB:
    def __init__(self, log_util: LogUtil, environment_utils: EnvironmentUtils):

        # Initialize logger
        self.log_util = log_util

        # Initialize environment utils
        self.environment_utils = environment_utils

        # Mongo credentials
        self.username = urllib.parse.quote_plus(self.environment_utils.get_env_variable("MONGO_USERNAME"))
        self.password = urllib.parse.quote_plus(self.environment_utils.get_env_variable("MONGO_PASSWORD"))
        self.auth_source = self.environment_utils.get_env_variable("MONGO_AUTH_SOURCE")
        self.host = self.environment_utils.get_env_variable("MONGO_HOST")
        self.port = int(self.environment_utils.get_env_variable("MONGO_PORT"))
        self.db_name = self.environment_utils.get_env_variable("MONGO_DB_NAME")

        # Mongo Connection Pool Configs
        self.max_pool_size = 50
        self.min_pool_size = 0  # Create connections on-demand instead of at startup
        self.max_idle_time_ms = 30000
        self.wait_queue_timeout_ms = 10000  # Reduced from 30000ms for faster failure detection
        self.connect_timeout_ms = 10000  # Reduced from 20000ms for faster failure detection
        self.server_selection_timeout_ms = 10000  # Increased from 5000ms for consistency
        self.socket_timeout_ms = 10000  # Added for socket-level timeout

        # MongoDB client - will be initialized lazily on first use
        # Use a dictionary keyed by event loop ID to support multiple event loops
        self._clients = {}  # {loop_id: (client, db, collections_dict)}
        self.client = None  # Current client (for backward compatibility)
        self.db = None
        
        # Collections - will be initialized after client is created
        self.flows = None
        self.flow_nodes = None
        self.flow_edges = None
        self.flow_triggers = None
        self.users = None
        self.flow_user_context = None
        self.flow_webhook_messages = None
        self.webhook_adapter_processed = None
        self.node_details = None
        self.user_transactions = None
        self.delays = None
        self.flow_settings = None
        
        # Thread-safe initialization lock
        self._client_lock = threading.Lock()

    def _get_client_for_current_loop(self):
        """
        Thread-safe method to get the MongoDB client and collections for the current event loop.
        Returns a dictionary with 'client', 'db', and 'collections' for the current event loop.
        This ensures each thread/event loop gets its own client instance without overwriting others.
        """
        # Get the current event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop - try to get any event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop at all - this shouldn't happen if called from async methods
                raise RuntimeError("No event loop available. Database methods must be called from an async context.")
        
        loop_id = id(loop)
        
        # Check if we already have a client for this event loop
        if loop_id in self._clients:
            return self._clients[loop_id]
        
        # Need to create a new client for this event loop
        with self._client_lock:
            # Double-check after acquiring lock (another thread might have created it)
            if loop_id in self._clients:
                return self._clients[loop_id]
            
            # Create MongoDB client for this specific event loop
            # Added retry mechanisms and optimized timeout values to reduce connection issues
            client = AsyncIOMotorClient(
                f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/?authSource={self.auth_source}",
                maxPoolSize=self.max_pool_size,
                minPoolSize=self.min_pool_size,
                maxIdleTimeMS=self.max_idle_time_ms,
                waitQueueTimeoutMS=self.wait_queue_timeout_ms,
                connectTimeoutMS=self.connect_timeout_ms,
                serverSelectionTimeoutMS=self.server_selection_timeout_ms,
                socketTimeoutMS=self.socket_timeout_ms,
                retryWrites=True,  # Enable retry for write operations
                retryReads=True  # Enable retry for read operations
            )
            db = client[self.db_name]
            
            # Initialize collections for this client
            collections = self._initialize_collections_for_client(db)
            
            # Store client data for this event loop
            client_data = {
                'client': client,
                'db': db,
                'collections': collections,
                'loop': weakref.ref(loop)  # Weak reference to avoid circular references
            }
            self._clients[loop_id] = client_data
            
            self.log_util.info(
                service_name="FlowDB",
                message=f"MongoDB client initialized for event loop {loop_id} (lazy initialization)"
            )
            
            return client_data
    
    def _initialize_collections_for_client(self, db):
        """
        Initialize MongoDB collections for a given database instance
        Returns a dictionary of collections
        """
        return {
            'flows': db.flows,
            'flow_nodes': db.flow_nodes,
            'flow_edges': db.flow_edges,
            'flow_triggers': db.flow_triggers,
            'users': db.users,
            'flow_user_context': db.flow_user_context,
            'flow_webhook_messages': db.flow_webhook_messages,
            'webhook_adapter_processed': db.webhook_adapter_processed,
            'node_details': db.node_details,
            'user_transactions': db.user_transactions,
            'delays': db.delays,
            'flow_settings': db.flow_settings
        }
    
    
    def close(self):
        """
        Close all MongoDB clients and cleanup resources
        """
        with self._client_lock:
            for loop_id, client_data in self._clients.items():
                try:
                    client_data['client'].close()
                except Exception as e:
                    self.log_util.warning(
                        service_name="FlowDB",
                        message=f"Error closing client for loop {loop_id}: {str(e)}"
                    )
            
            self._clients.clear()
            self.client = None
            self.db = None
            
            # Clear collections
            self.flows = None
            self.flow_nodes = None
            self.flow_edges = None
            self.flow_triggers = None
            self.users = None
            self.flow_user_context = None
            self.flow_webhook_messages = None
            self.webhook_adapter_processed = None
            self.node_details = None
            self.flow_settings = None
            
            self.log_util.info(
                service_name="FlowDB",
                message="All MongoDB clients closed"
            )
    
    def _handle_db_operation(self, operation_name: str, error: Exception) -> None:
        """
        Handle database operation errors with appropriate logging and exception wrapping.
        
        Args:
            operation_name: Name of the operation that failed
            error: The exception that occurred
        """
        if isinstance(error, (NetworkTimeout, ServerSelectionTimeoutError, ConnectionFailure)):
            self.log_util.error(
                service_name="FlowDB",
                message=f"Database connection error in {operation_name}: {str(error)}"
            )
            raise FlowDBException(
                message=f"Database connection error: {str(error)}",
                status_code=503  # Service Unavailable
            )
        else:
            self.log_util.error(
                service_name="FlowDB",
                message=f"Error in {operation_name}: {str(error)}"
            )
            raise FlowDBException(
                message=f"Database error: {str(error)}",
                status_code=500
            )

    # Flow CRUD operations
    async def create_flow(self, flow: FlowData, original_flow_nodes: Optional[List[Dict[str, Any]]] = None) -> Optional[FlowData]:
        """
        Create a new flow
        
        Args:
            flow: FlowData object (Pydantic model)
            original_flow_nodes: Optional original flowNodes as dicts (to preserve channel field)
        """
        client_data = self._get_client_for_current_loop()
        try:
            flow_dict = flow.model_dump(exclude={"id"})
            # Remove channel field if present (channel is saved at node level, not flow level)
            flow_dict.pop("channel", None)
            
            # Replace flowNodes with original nodes to preserve channel field
            if original_flow_nodes is not None:
                flow_dict["flowNodes"] = original_flow_nodes
            
            result = await client_data['collections']['flows'].insert_one(flow_dict)
            flow_dict["id"] = str(result.inserted_id)
            flow_dict["_id"] = result.inserted_id
            return FlowData.model_validate(flow_dict)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error creating flow: {str(e)}")
            return None

    async def get_flow(self, flow_id: str) -> Optional[FlowData]:
        """
        Get a flow by ID
        """
        client_data = self._get_client_for_current_loop()
        try:
            result = await client_data['collections']['flows'].find_one({"_id": ObjectId(flow_id)})
            if result is None:
                return None
            result["id"] = str(result["_id"])
            return FlowData.model_validate(result)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting flow: {str(e)}")
            return None

    async def get_flow_by_id(self, flow_id: str) -> Optional[FlowData]:
        """
        Get a flow by ID (alias for get_flow for consistency)
        """
        return await self.get_flow(flow_id)

    async def get_flows_by_brand(self, brand_id: int) -> List[FlowData]:
        """
        Get all flows for a brand
        """
        client_data = self._get_client_for_current_loop()
        try:
            cursor = client_data['collections']['flows'].find({"brand_id": brand_id})
            flows = []
            async for flow_dict in cursor:
                flow_dict["id"] = str(flow_dict["_id"])
                flows.append(FlowData.model_validate(flow_dict))
            return flows
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting flows by brand: {str(e)}")
            return []

    async def get_flows(self, brand_id: int, user_id: Optional[int] = None) -> List[FlowData]:
        """
        Get flows filtered by brand only (user_id is ignored - all flows for the brand are returned)
        """
        client_data = self._get_client_for_current_loop()
        try:
            # Only filter by brand_id - do not filter by user_id
            # All users within a brand should see all flows for that brand
            query: Dict[str, Any] = {"brand_id": brand_id}

            cursor = client_data['collections']['flows'].find(query)
            flows: List[FlowData] = []
            async for flow_dict in cursor:
                flow_dict["id"] = str(flow_dict["_id"])
                flows.append(FlowData.model_validate(flow_dict))
            return flows
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting flows: {str(e)}")
            return []

    async def update_flow(self, flow_id: str, flow: FlowData, original_flow_nodes: Optional[List[Dict[str, Any]]] = None) -> Optional[FlowData]:
        """
        Update a flow
        
        Args:
            flow_id: Flow ID
            flow: FlowData object (Pydantic model)
            original_flow_nodes: Optional original flowNodes as dicts (to preserve channel field)
        """
        client_data = self._get_client_for_current_loop()
        try:
            flow_dict = flow.model_dump(exclude={"id"})
            # Remove channel field if present (channel is saved at node level, not flow level)
            flow_dict.pop("channel", None)
            
            # Replace flowNodes with original nodes to preserve channel field
            if original_flow_nodes is not None:
                flow_dict["flowNodes"] = original_flow_nodes
            
            flow_dict["updated_at"] = datetime.utcnow()
            result = await client_data['collections']['flows'].find_one_and_update(
                {"_id": ObjectId(flow_id)},
                {"$set": flow_dict},
                return_document=True
            )
            if result is None:
                return None
            result["id"] = str(result["_id"])
            return FlowData.model_validate(result)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error updating flow: {str(e)}")
            return None

    async def update_flow_status(self, flow_id: str, status: str) -> Optional[FlowData]:
        """
        Update only the status field of a flow
        
        Args:
            flow_id: Flow ID
            status: New status value (e.g., "draft", "published")
        """
        client_data = self._get_client_for_current_loop()
        try:
            result = await client_data['collections']['flows'].find_one_and_update(
                {"_id": ObjectId(flow_id)},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.utcnow()
                    }
                },
                return_document=True
            )
            if result is None:
                return None
            result["id"] = str(result["_id"])
            return FlowData.model_validate(result)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error updating flow status: {str(e)}")
            return None

    async def save_flow_nodes(self, flow_id: str, nodes: List[Dict[str, Any]]) -> bool:
        """
        Save nodes for a flow. Replaces existing nodes for the flow_id.
        """
        client_data = self._get_client_for_current_loop()
        try:
            collection = client_data['collections']['flow_nodes']
            await collection.delete_many({"flow_id": flow_id})

            if not nodes:
                return True

            node_documents = []
            for node in nodes:
                # Convert node to dict if it's a Pydantic model
                if hasattr(node, "model_dump"):
                    node_dict = node.model_dump()
                elif isinstance(node, dict):
                    node_dict = node
                else:
                    node_dict = dict(node)
                
                # Extract channel from node dict
                channel = node_dict.get("channel")
                
                node_document = {
                    "flow_id": flow_id,
                    "node_id": node_dict.get("id"),
                    "node_type": node_dict.get("type"),
                    "flow_node_type": node_dict.get("flowNodeType"),
                    "channel": channel,  # Extract channel field separately
                    "node_data": node_dict,  # Save the full node as dict
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                node_documents.append(node_document)

            if node_documents:
                await collection.insert_many(node_documents)

            return True
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error saving flow nodes: {str(e)}")
            return False

    async def save_flow_edges(self, flow_id: str, edges: List[Dict[str, Any]]) -> bool:
        """
        Save edges for a flow. Replaces existing edges for the flow_id.
        """
        client_data = self._get_client_for_current_loop()
        try:
            collection = client_data['collections']['flow_edges']
            await collection.delete_many({"flow_id": flow_id})

            if not edges:
                return True

            edge_documents = []
            for edge in edges:
                edge_document = {
                    "flow_id": flow_id,
                    "edge_id": edge.get("id"),
                    "source_node_id": edge.get("sourceNodeId"),
                    "target_node_id": edge.get("targetNodeId"),
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                edge_documents.append(edge_document)

            if edge_documents:
                await collection.insert_many(edge_documents)

            return True
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error saving flow edges: {str(e)}")
            return False

    async def get_flow_edges(self, flow_id: str) -> List[Any]:
        """
        Get all edges for a flow.
        Returns a list of edge objects with source_node_id and target_node_id attributes.
        """
        client_data = self._get_client_for_current_loop()
        try:
            cursor = client_data['collections']['flow_edges'].find({"flow_id": flow_id})
            edges = []
            async for edge_dict in cursor:
                # Create a simple object with the required attributes
                class Edge:
                    def __init__(self, source_node_id: str, target_node_id: str):
                        self.source_node_id = source_node_id
                        self.target_node_id = target_node_id
                
                edges.append(Edge(
                    source_node_id=edge_dict.get("source_node_id", ""),
                    target_node_id=edge_dict.get("target_node_id", "")
                ))
            
            return edges
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting flow edges: {str(e)}")
            return []

    async def save_flow_triggers(self, flow_id: str, triggers: List[Dict[str, Any]]) -> bool:
        """
        Save triggers for a flow. Existing triggers are replaced.
        """
        client_data = self._get_client_for_current_loop()
        try:
            await client_data['collections']['flow_triggers'].delete_many({"flow_id": flow_id})

            if not triggers:
                return True

            trigger_docs = []
            for trigger in triggers:
                trigger_data = FlowTriggerData(
                    flow_id=flow_id,
                    node_id=trigger.get("node_id", ""),
                    trigger_type=trigger.get("trigger_type", ""),
                    trigger_values=trigger.get("trigger_values", []),
                ).model_dump(exclude={"id"})
                trigger_docs.append(trigger_data)

            if trigger_docs:
                await client_data['collections']['flow_triggers'].insert_many(trigger_docs)

            return True
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error saving flow triggers: {str(e)}")
            return False

    async def get_flow_triggers_by_brand_id(self, brand_id: int) -> List[FlowTriggerData]:
        """
        Get all flow triggers for a brand.
        Since triggers are linked to flows, we need to:
        1. Get all flows for this brand with status="published"
        2. Get all triggers for those flows
        """
        client_data = self._get_client_for_current_loop()
        try:
            # First, get all published flow IDs for this brand
            query: Dict[str, Any] = {"brand_id": brand_id, "status": "published"}
            cursor = client_data['collections']['flows'].find(query)
            flow_ids = []
            async for flow_dict in cursor:
                flow_ids.append(str(flow_dict["_id"]))
            
            if not flow_ids:
                return []
            
            # Get all triggers for these published flows
            cursor = client_data['collections']['flow_triggers'].find({"flow_id": {"$in": flow_ids}})
            triggers = []
            async for trigger_dict in cursor:
                trigger_dict["id"] = str(trigger_dict["_id"])
                triggers.append(FlowTriggerData.model_validate(trigger_dict))
            
            return triggers
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting flow triggers by brand_id: {str(e)}")
            return []

    async def delete_flow(self, flow_id: str) -> bool:
        """
        Delete a flow
        """
        client_data = self._get_client_for_current_loop()
        try:
            result = await client_data['collections']['flows'].delete_one({"_id": ObjectId(flow_id)})
            return result.deleted_count > 0
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error deleting flow: {str(e)}")
            return False

    def _build_user_query(self, user_identifier: str, brand_id: int, channel: str, channel_account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build MongoDB query to find user by identifier based on channel.
        Also includes channel_account_id to ensure same user with different channel accounts are treated as separate users.
        Returns a query dict that searches in the appropriate user_detail field.
        """
        channel_lower = channel.lower()
        query = {"brand_id": brand_id}
        
        if channel_lower == "whatsapp" or channel_lower == "sms":
            query["user_detail.phone_number"] = user_identifier
        elif channel_lower == "gmail" or channel_lower == "email":
            query["user_detail.email"] = user_identifier
        elif channel_lower == "instagram":
            query["user_detail.instagram_user_id"] = user_identifier
        elif channel_lower == "facebook":
            query["user_detail.facebook_user_id"] = user_identifier
        elif channel_lower == "telegram":
            query["user_detail.telegram_user_id"] = user_identifier
        else:
            # For unknown channels, try custom_identifier or search in all fields
            query["$or"] = [
                {"user_detail.custom_identifier": user_identifier},
                {"user_detail.phone_number": user_identifier},
                {"user_detail.email": user_identifier}
            ]
        
        # Add channel_account_id to query if provided
        # This ensures same user_detail with different channel_account_id creates separate user states
        if channel_account_id:
            query["channel_account_id"] = channel_account_id
        
        return query

    # User operations
    async def save_user_data(self, user_data: UserData) -> Optional[UserData]:
        """
        Save or create a new user (generic, channel-agnostic)
        """
        client_data = self._get_client_for_current_loop()
        try:
            user_dict = user_data.model_dump(exclude={"id"})
            result = await client_data['collections']['users'].insert_one(user_dict)
            if result.inserted_id is None:
                self.log_util.error(service_name="FlowDB", message="Failed to save user data")
                return None
            user_dict["id"] = str(result.inserted_id)
            user_dict["_id"] = result.inserted_id
            return UserData.model_validate(user_dict)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error saving user data: {str(e)}")
            return None

    async def get_user_data(self, user_identifier: str, brand_id: int, channel: str = "whatsapp", channel_account_id: Optional[str] = None) -> Optional[UserData]:
        """
        Get user data by identifier, channel, and channel_account_id.
        channel_account_id is required to distinguish between same user_detail with different channel accounts.
        """
        client_data = self._get_client_for_current_loop()
        try:
            query = self._build_user_query(user_identifier, brand_id, channel, channel_account_id)
            result = await client_data['collections']['users'].find_one(query)
            if result is None:
                return None
            result["id"] = str(result["_id"])
            return UserData.model_validate(result)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting user data: {str(e)}")
            return None

    async def update_user_automation_state(self, user_identifier: str, brand_id: int, is_in_automation: bool, 
                                          current_flow_id: Optional[str] = None, current_node_id: Optional[str] = None, 
                                          channel: str = "whatsapp", channel_account_id: Optional[str] = None,
                                          delay_node_data: Optional[Dict[str, Any]] = None) -> Optional[UserData]:
        """
        Update user automation state
        """
        client_data = self._get_client_for_current_loop()
        try:
            update_dict = {
                "is_in_automation": is_in_automation,
                "channel": channel,
                "updated_at": datetime.utcnow()
            }
            
            if current_flow_id is not None:
                update_dict["current_flow_id"] = current_flow_id
            if current_node_id is not None:
                update_dict["current_node_id"] = current_node_id
            if channel_account_id is not None:
                update_dict["channel_account_id"] = channel_account_id
            if delay_node_data is not None:
                # Save delay node data
                update_dict["delay_node_data"] = delay_node_data
            elif not is_in_automation:
                # Clear delay_node_data when exiting automation
                update_dict["delay_node_data"] = None
            
            query = self._build_user_query(user_identifier, brand_id, channel, channel_account_id)
            result = await client_data['collections']['users'].find_one_and_update(
                query,
                {"$set": update_dict},
                return_document=True
            )
            if result is None:
                return None
            result["id"] = str(result["_id"])
            return UserData.model_validate(result)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error updating user automation state: {str(e)}")
            return None

    async def update_validation_state(self, user_identifier: str, brand_id: int, validation_failed: bool, 
                                     failure_message: Optional[str] = None, channel: str = "whatsapp", 
                                     channel_account_id: Optional[str] = None) -> Optional[UserData]:
        """
        Update user validation state
        """
        client_data = self._get_client_for_current_loop()
        try:
            # Get current user to access validation state
            current_user = await self.get_user_data(user_identifier, brand_id, channel, channel_account_id)
            if not current_user:
                return None
            
            # Import ValidationData here to avoid circular imports
            from models.validation_data import ValidationData
            
            if validation_failed:
                # Increment failure count
                new_validation = ValidationData(
                    failed=True,
                    failure_count=current_user.validation.failure_count + 1,
                    failure_message=failure_message
                )
            else:
                # Reset on success
                new_validation = ValidationData(
                    failed=False,
                    failure_count=0,
                    failure_message=None
                )
            
            # Update validation object
            query = self._build_user_query(user_identifier, brand_id, channel, channel_account_id)
            update_dict = {
                        "validation": new_validation.model_dump(),
                "channel": channel,
                        "updated_at": datetime.utcnow()
                    }
            if channel_account_id is not None:
                update_dict["channel_account_id"] = channel_account_id
            
            result = await client_data['collections']['users'].find_one_and_update(
                query,
                {"$set": update_dict},
                return_document=True
            )
            
            if result is None:
                return None
            result["id"] = str(result["_id"])
            return UserData.model_validate(result)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error updating validation state: {str(e)}")
            return None

    # Flow User Context operations
    async def get_all_flow_user_context(self, user_identifier: str, brand_id: int, flow_id: str) -> List[FlowUserContext]:
        """
        Get all context variables for a user's flow
        """
        client_data = self._get_client_for_current_loop()
        try:
            cursor = client_data['collections']['flow_user_context'].find({
                "user_identifier": user_identifier,
                "brand_id": brand_id,
                "flow_id": flow_id
            })
            
            contexts = []
            async for result in cursor:
                context_dict = dict(result)
                if "_id" in context_dict:
                    # Convert ObjectId to string for both id and _id (model uses alias)
                    context_dict["id"] = str(context_dict["_id"])
                    context_dict["_id"] = str(context_dict["_id"])
                contexts.append(FlowUserContext(**context_dict))
            
            return contexts
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting flow user contexts: {str(e)}")
            return []

    async def save_or_update_flow_variable(self, user_identifier: str, brand_id: int, flow_id: str, 
                                          variable_name: str, variable_value: str, node_id: Optional[str] = None) -> Optional[FlowUserContext]:
        """
        Save or update a single variable in the flow context
        """
        client_data = self._get_client_for_current_loop()
        try:
            result = await client_data['collections']['flow_user_context'].find_one_and_update(
                {
                    "user_identifier": user_identifier,
                    "brand_id": brand_id,
                    "flow_id": flow_id,
                    "variable_name": variable_name
                },
                {
                    "$set": {
                        "variable_value": variable_value,
                        "node_id": node_id,
                        "updated_at": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "user_identifier": user_identifier,
                        "brand_id": brand_id,
                        "flow_id": flow_id,
                        "variable_name": variable_name,
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True,
                return_document=True
            )
            if result is None:
                return None
            context_dict = dict(result)
            if "_id" in context_dict:
                # Convert ObjectId to string for Pydantic validation
                # The model uses alias="_id" but expects string, so convert both
                context_dict["id"] = str(context_dict["_id"])
                context_dict["_id"] = str(context_dict["_id"])
            return FlowUserContext.model_validate(context_dict)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error saving/updating flow variable: {str(e)}")
            return None
    
    async def delete_flow_user_context(self, user_identifier: str, brand_id: int, flow_id: str) -> bool:
        """
        Delete all user's flow context data
        """
        client_data = self._get_client_for_current_loop()
        try:
            result = await client_data['collections']['flow_user_context'].delete_many({
                "user_identifier": user_identifier,
                "brand_id": brand_id,
                "flow_id": flow_id
            })
            return result.deleted_count > 0
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error deleting flow user context: {str(e)}")
            return False

    # Webhook Message operations
    async def save_webhook_message(self, webhook_message: WebhookMessageData) -> Optional[WebhookMessageData]:
        """
        Save a webhook message received from channel services
        """
        client_data = self._get_client_for_current_loop()
        try:
            webhook_dict = webhook_message.model_dump(exclude={"id"})
            result = await client_data['collections']['flow_webhook_messages'].insert_one(webhook_dict)
            if result.inserted_id is None:
                self.log_util.error(service_name="FlowDB", message="Failed to save webhook message")
                return None
            webhook_dict["id"] = str(result.inserted_id)
            webhook_dict["_id"] = result.inserted_id
            return WebhookMessageData.model_validate(webhook_dict)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error saving webhook message: {str(e)}")
            return None

    async def update_webhook_message(self, webhook_id: str, webhook_message: WebhookMessageData) -> Optional[WebhookMessageData]:
        """
        Update a webhook message
        """
        client_data = self._get_client_for_current_loop()
        try:
            webhook_dict = webhook_message.model_dump(exclude={"id"})
            result = await client_data['collections']['flow_webhook_messages'].find_one_and_update(
                {"_id": ObjectId(webhook_id)},
                {"$set": webhook_dict},
                return_document=True
            )
            if result is None:
                return None
            result["id"] = str(result["_id"])
            return WebhookMessageData.model_validate(result)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error updating webhook message: {str(e)}")
            return None

    # Webhook Adapter Processed CRUD operations
    async def save_webhook_adapter_processed(self, webhook_adapter_data: WebhookAdapterProcessedData) -> Optional[WebhookAdapterProcessedData]:
        """
        Save a webhook message after adapter processing (normalization).
        This stores the normalized webhook data for tracking and debugging.
        """
        client_data = self._get_client_for_current_loop()
        try:
            webhook_dict = webhook_adapter_data.model_dump(exclude={"id"})
            result = await client_data['collections']['webhook_adapter_processed'].insert_one(webhook_dict)
            if result.inserted_id is None:
                self.log_util.error(service_name="FlowDB", message="Failed to save webhook adapter processed data")
                return None
            webhook_dict["id"] = str(result.inserted_id)
            webhook_dict["_id"] = result.inserted_id
            return WebhookAdapterProcessedData.model_validate(webhook_dict)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error saving webhook adapter processed data: {str(e)}")
            return None

    # Node Details CRUD operations
    async def create_node_detail(self, node_detail: NodeDetailData) -> Optional[NodeDetailData]:
        """
        Create a new node detail
        """
        client_data = self._get_client_for_current_loop()
        try:
            node_dict = node_detail.model_dump(exclude={"id"})
            result = await client_data['collections']['node_details'].insert_one(node_dict)
            if result.inserted_id:
                node_dict["_id"] = result.inserted_id
                node_dict["id"] = str(result.inserted_id)
                return NodeDetailData.model_validate(node_dict)
            return None
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error creating node detail: {str(e)}")
            return None

    async def get_node_detail_by_id(self, node_id: str) -> Optional[NodeDetailData]:
        """
        Get node detail by node_id (e.g., "trigger-keyword", "message", etc.)
        """
        client_data = self._get_client_for_current_loop()
        try:
            result = await client_data['collections']['node_details'].find_one({"node_id": node_id})
            if result is None:
                return None
            result["id"] = str(result["_id"])
            return NodeDetailData.model_validate(result)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting node detail: {str(e)}")
            return None

    async def get_all_node_details(self) -> List[NodeDetailData]:
        """
        Get all node details
        """
        client_data = self._get_client_for_current_loop()
        try:
            cursor = client_data['collections']['node_details'].find({})
            results = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                results.append(NodeDetailData.model_validate(doc))
            return results
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting all node details: {str(e)}")
            return []

    async def get_node_details_by_category(self, category: str) -> List[NodeDetailData]:
        """
        Get node details by category (Trigger, Action, Condition, Delay)
        """
        client_data = self._get_client_for_current_loop()
        try:
            cursor = client_data['collections']['node_details'].find({"category": category})
            results = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                results.append(NodeDetailData.model_validate(doc))
            return results
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting node details by category: {str(e)}")
            return []

    async def update_node_detail(self, node_id: str, node_detail: NodeDetailData) -> Optional[NodeDetailData]:
        """
        Update a node detail by node_id
        """
        client_data = self._get_client_for_current_loop()
        try:
            node_dict = node_detail.model_dump(exclude={"id"})
            node_dict["updated_at"] = datetime.utcnow()
            result = await client_data['collections']['node_details'].find_one_and_update(
                {"node_id": node_id},
                {"$set": node_dict},
                return_document=True
            )
            if result is None:
                return None
            result["id"] = str(result["_id"])
            return NodeDetailData.model_validate(result)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error updating node detail: {str(e)}")
            return None

    async def delete_node_detail(self, node_id: str) -> bool:
        """
        Delete a node detail by node_id
        """
        client_data = self._get_client_for_current_loop()
        try:
            result = await client_data['collections']['node_details'].delete_one({"node_id": node_id})
            return result.deleted_count > 0
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error deleting node detail: {str(e)}")
            return False

    async def upsert_node_detail(self, node_detail: NodeDetailData) -> Optional[NodeDetailData]:
        """
        Insert or update a node detail (upsert operation)
        """
        client_data = self._get_client_for_current_loop()
        try:
            node_dict = node_detail.model_dump(exclude={"id"})
            node_dict["updated_at"] = datetime.utcnow()
            
            # Check if node exists
            existing = await client_data['collections']['node_details'].find_one({"node_id": node_detail.node_id})
            if existing:
                # Update existing
                result = await client_data['collections']['node_details'].find_one_and_update(
                    {"node_id": node_detail.node_id},
                    {"$set": node_dict},
                    return_document=True
                )
            else:
                # Insert new
                node_dict["created_at"] = datetime.utcnow()
                result = await client_data['collections']['node_details'].insert_one(node_dict)
                if result.inserted_id:
                    node_dict["_id"] = result.inserted_id
                    result = node_dict
            
            if result:
                result["id"] = str(result["_id"])
                return NodeDetailData.model_validate(result)
            return None
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error upserting node detail: {str(e)}")
            return None
    
    # User Transaction CRUD operations
    async def save_user_transaction(self, transaction: "UserTransactionData") -> Optional["UserTransactionData"]:
        """
        Save a user transaction to the database.
        
        Args:
            transaction: UserTransactionData object to save
        
        Returns:
            Saved UserTransactionData with ID, or None if save failed
        """
        from models.user_transaction_data import UserTransactionData
        
        client_data = self._get_client_for_current_loop()
        try:
            transaction_dict = transaction.model_dump(exclude={"id"})
            result = await client_data['collections']['user_transactions'].insert_one(transaction_dict)
            if result.inserted_id is None:
                self.log_util.error(service_name="FlowDB", message="Failed to save user transaction")
                return None
            transaction_dict["id"] = str(result.inserted_id)
            transaction_dict["_id"] = result.inserted_id
            return UserTransactionData.model_validate(transaction_dict)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error saving user transaction: {str(e)}")
            return None
    
    async def get_transaction_counts_by_node(self, flow_id: str) -> Dict[str, int]:
        """
        Get transaction counts grouped by node_id for a specific flow_id.
        
        Args:
            flow_id: Flow ID to get transaction counts for
        
        Returns:
            Dictionary mapping node_id to transaction count
        """
        client_data = self._get_client_for_current_loop()
        try:
            # Use MongoDB aggregation to group by node_id and count
            pipeline = [
                {"$match": {"flow_id": flow_id}},
                {"$group": {
                    "_id": "$node_id",
                    "count": {"$sum": 1}
                }}
            ]
            
            cursor = client_data['collections']['user_transactions'].aggregate(pipeline)
            counts = {}
            async for doc in cursor:
                node_id = doc["_id"]
                count = doc["count"]
                counts[node_id] = count
            
            return counts
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting transaction counts by node: {str(e)}")
            return {}
    
    # Delay CRUD operations
    async def save_delay(self, delay: "DelayData") -> Optional["DelayData"]:
        """
        Save a delay record to the database.
        
        Args:
            delay: DelayData object to save
        
        Returns:
            Saved DelayData with ID, or None if save failed
        """
        from models.delay_data import DelayData
        
        client_data = self._get_client_for_current_loop()
        try:
            delay_dict = delay.model_dump(exclude={"id"})
            result = await client_data['collections']['delays'].insert_one(delay_dict)
            if result.inserted_id is None:
                self.log_util.error(service_name="FlowDB", message="Failed to save delay")
                return None
            delay_dict["id"] = str(result.inserted_id)
            delay_dict["_id"] = result.inserted_id
            return DelayData.model_validate(delay_dict)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error saving delay: {str(e)}")
            return None
    
    async def get_pending_delays(self) -> List["DelayData"]:
        """
        Get all pending delays that need to be processed (not processed and delay_completes_at <= now).
        
        Returns:
            List of DelayData objects that are ready to be processed
        """
        from models.delay_data import DelayData
        
        client_data = self._get_client_for_current_loop()
        try:
            now = datetime.utcnow()
            cursor = client_data['collections']['delays'].find({
                "processed": False,
                "delay_completes_at": {"$lte": now}
            })
            results = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                results.append(DelayData.model_validate(doc))
            return results
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting pending delays: {str(e)}")
            return []
    
    async def mark_delay_as_processed(self, delay_id: str) -> bool:
        """
        Mark a delay as processed after delay_complete webhook is sent.
        
        Args:
            delay_id: Delay record ID
        
        Returns:
            True if updated successfully, False otherwise
        """
        client_data = self._get_client_for_current_loop()
        try:
            from bson import ObjectId
            result = await client_data['collections']['delays'].update_one(
                {"_id": ObjectId(delay_id)},
                {
                    "$set": {
                        "processed": True,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error marking delay as processed: {str(e)}")
            return False
    
    # Flow Settings CRUD operations
    async def save_flow_settings(self, flow_settings: "FlowSettingsData") -> Optional["FlowSettingsData"]:
        """
        Save or update flow settings for a specific flow and node.
        If settings exist for the flow_id and node_id combination, updates them.
        Otherwise, creates new settings.
        
        Args:
            flow_settings: FlowSettingsData object to save
        
        Returns:
            Saved FlowSettingsData with ID, or None if save failed
        """
        from models.flow_settings_data import FlowSettingsData
        
        client_data = self._get_client_for_current_loop()
        try:
            flow_settings_dict = flow_settings.model_dump(exclude={"id"})
            flow_settings_dict["updated_at"] = datetime.utcnow()
            
            # Check if settings already exist for this flow_id and node_id
            existing = await client_data['collections']['flow_settings'].find_one({
                "flow_id": flow_settings.flow_id,
                "node_id": flow_settings.node_id
            })
            
            if existing:
                # Update existing settings
                result = await client_data['collections']['flow_settings'].find_one_and_update(
                    {
                        "flow_id": flow_settings.flow_id,
                        "node_id": flow_settings.node_id
                    },
                    {"$set": flow_settings_dict},
                    return_document=True
                )
            else:
                # Create new settings
                flow_settings_dict["created_at"] = datetime.utcnow()
                result = await client_data['collections']['flow_settings'].insert_one(flow_settings_dict)
                if result.inserted_id:
                    flow_settings_dict["_id"] = result.inserted_id
                    result = flow_settings_dict
            
            if result:
                result["id"] = str(result["_id"])
                return FlowSettingsData.model_validate(result)
            return None
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error saving flow settings: {str(e)}")
            return None
    
    async def get_flow_settings(self, flow_id: str, node_id: str) -> Optional["FlowSettingsData"]:
        """
        Get flow settings for a specific flow and node.
        
        Args:
            flow_id: Flow ID
            node_id: Node ID
        
        Returns:
            FlowSettingsData if found, None otherwise
        """
        from models.flow_settings_data import FlowSettingsData
        
        client_data = self._get_client_for_current_loop()
        try:
            result = await client_data['collections']['flow_settings'].find_one({
                "flow_id": flow_id,
                "node_id": node_id
            })
            if result is None:
                return None
            result["id"] = str(result["_id"])
            return FlowSettingsData.model_validate(result)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting flow settings: {str(e)}")
            return None
    
    async def get_flow_settings_by_flow_id(self, flow_id: str) -> List["FlowSettingsData"]:
        """
        Get all flow settings for a specific flow.
        
        Args:
            flow_id: Flow ID
        
        Returns:
            List of FlowSettingsData objects
        """
        from models.flow_settings_data import FlowSettingsData
        
        client_data = self._get_client_for_current_loop()
        try:
            cursor = client_data['collections']['flow_settings'].find({"flow_id": flow_id})
            results = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                results.append(FlowSettingsData.model_validate(doc))
            return results
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting flow settings by flow_id: {str(e)}")
            return []
    
    async def delete_flow_settings(self, flow_id: str, node_id: str) -> bool:
        """
        Delete flow settings for a specific flow and node.
        
        Args:
            flow_id: Flow ID
            node_id: Node ID
        
        Returns:
            True if deleted successfully, False otherwise
        """
        client_data = self._get_client_for_current_loop()
        try:
            result = await client_data['collections']['flow_settings'].delete_one({
                "flow_id": flow_id,
                "node_id": node_id
            })
            return result.deleted_count > 0
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error deleting flow settings: {str(e)}")
            return False

