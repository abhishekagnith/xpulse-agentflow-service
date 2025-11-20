from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import urllib.parse
import threading
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
import weakref

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
        self.min_pool_size = 10
        self.max_idle_time_ms = 30000
        self.wait_queue_timeout_ms = 10000
        self.connect_timeout_ms = 20000
        self.server_selection_timeout_ms = 5000

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
            client = AsyncIOMotorClient(
                f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/?authSource={self.auth_source}",
                maxPoolSize=self.max_pool_size,
                minPoolSize=self.min_pool_size,
                maxIdleTimeMS=self.max_idle_time_ms,
                waitQueueTimeoutMS=self.wait_queue_timeout_ms,
                connectTimeoutMS=self.connect_timeout_ms,
                serverSelectionTimeoutMS=self.server_selection_timeout_ms
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
            'flow_webhook_messages': db.flow_webhook_messages
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
            
            self.log_util.info(
                service_name="FlowDB",
                message="All MongoDB clients closed"
            )

    # Flow CRUD operations
    async def create_flow(self, flow: FlowData) -> Optional[FlowData]:
        """
        Create a new flow
        """
        client_data = self._get_client_for_current_loop()
        try:
            flow_dict = flow.model_dump(exclude={"id"})
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
        Get flows filtered by brand (and optionally user)
        """
        client_data = self._get_client_for_current_loop()
        try:
            query: Dict[str, Any] = {"brand_id": brand_id}
            if user_id is not None:
                query["user_id"] = user_id

            cursor = client_data['collections']['flows'].find(query)
            flows: List[FlowData] = []
            async for flow_dict in cursor:
                flow_dict["id"] = str(flow_dict["_id"])
                flows.append(FlowData.model_validate(flow_dict))
            return flows
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting flows: {str(e)}")
            return []

    async def update_flow(self, flow_id: str, flow: FlowData) -> Optional[FlowData]:
        """
        Update a flow
        """
        client_data = self._get_client_for_current_loop()
        try:
            flow_dict = flow.model_dump(exclude={"id"})
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
                node_document = {
                    "flow_id": flow_id,
                    "node_id": node.get("id"),
                    "node_type": node.get("type"),
                    "flow_node_type": node.get("flowNodeType"),
                    "node_data": node,
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
        1. Get all flows for this brand
        2. Get all triggers for those flows
        """
        client_data = self._get_client_for_current_loop()
        try:
            # First, get all flow IDs for this brand
            flows = await self.get_flows(brand_id=brand_id)
            if not flows:
                return []
            
            flow_ids = [flow.id for flow in flows]
            
            # Get all triggers for these flows
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

    async def get_user_data(self, user_identifier: str, brand_id: int) -> Optional[UserData]:
        """
        Get user data
        """
        client_data = self._get_client_for_current_loop()
        try:
            result = await client_data['collections']['users'].find_one({
                "user_phone_number": user_identifier,
                "brand_id": brand_id
            })
            if result is None:
                return None
            result["id"] = str(result["_id"])
            return UserData.model_validate(result)
        except Exception as e:
            self.log_util.error(service_name="FlowDB", message=f"Error getting user data: {str(e)}")
            return None

    async def update_user_automation_state(self, user_identifier: str, brand_id: int, is_in_automation: bool, 
                                          current_flow_id: Optional[str] = None, current_node_id: Optional[str] = None) -> Optional[UserData]:
        """
        Update user automation state
        """
        client_data = self._get_client_for_current_loop()
        try:
            update_dict = {
                "is_in_automation": is_in_automation,
                "updated_at": datetime.utcnow()
            }
            
            if current_flow_id is not None:
                update_dict["current_flow_id"] = current_flow_id
            if current_node_id is not None:
                update_dict["current_node_id"] = current_node_id
            
            result = await client_data['collections']['users'].find_one_and_update(
                {
                    "user_phone_number": user_identifier,
                    "brand_id": brand_id
                },
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
                                     failure_message: Optional[str] = None) -> Optional[UserData]:
        """
        Update user validation state
        """
        client_data = self._get_client_for_current_loop()
        try:
            if validation_failed:
                # Increment failure count
                result = await client_data['collections']['users'].find_one_and_update(
                    {
                        "user_phone_number": user_identifier,
                        "brand_id": brand_id
                    },
                    {
                        "$set": {
                            "validation_failed": True,
                            "validation_failure_message": failure_message,
                            "updated_at": datetime.utcnow()
                        },
                        "$inc": {"validation_failure_count": 1}
                    },
                    return_document=True
                )
            else:
                # Reset on success
                result = await client_data['collections']['users'].find_one_and_update(
                    {
                        "user_phone_number": user_identifier,
                        "brand_id": brand_id
                    },
                    {
                        "$set": {
                            "validation_failed": False,
                            "validation_failure_count": 0,
                            "validation_failure_message": None,
                            "updated_at": datetime.utcnow()
                        }
                    },
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
                "user_phone_number": user_identifier,
                "brand_id": brand_id,
                "flow_id": flow_id
            })
            
            contexts = []
            async for result in cursor:
                context_dict = dict(result)
                if "_id" in context_dict:
                    context_dict["id"] = str(context_dict["_id"])
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
                    "user_phone_number": user_identifier,
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
                        "user_phone_number": user_identifier,
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
                "user_phone_number": user_identifier,
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

