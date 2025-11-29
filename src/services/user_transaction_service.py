"""
User Transaction Service
Handles user transaction data processing and storage.
Receives processed node data from NodeIdentificationService.
"""
from typing import Optional, Dict, Any, TYPE_CHECKING
from utils.log_utils import LogUtil

if TYPE_CHECKING:
    from models.webhook_message_data import WebhookMetadata
    from database.flow_db import FlowDB


class UserTransactionService:
    """
    Service for processing and storing user transaction data.
    Receives processed node information from node identification service.
    """
    
    def __init__(self, log_util: LogUtil, flow_db: Optional["FlowDB"] = None):
        self.log_util = log_util
        self.flow_db = flow_db
    
    async def process_node_transaction(
        self,
        metadata: "WebhookMetadata",
        data: Dict[str, Any],
        node_id: str,
        node_type: str,
        flow_id: str,
        processed_value: Optional[Any] = None,
        node_data: Optional[Dict[str, Any]] = None,
        user_detail: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process and store transaction data for a processed node.
        
        Args:
            metadata: WebhookMetadata containing user and channel information
            data: Normalized webhook data
            node_id: Node ID that was processed
            node_type: Type of node (condition, delay, message, etc.)
            flow_id: Flow ID
            processed_value: Processed value from node (e.g., yes/no node ID for condition, delay info for delay)
            node_data: Complete node data dictionary
            user_detail: User detail object from user table (contains channel-specific identifiers)
        
        Returns:
            Dict with status and message
        """
        try:
            user_identifier = metadata.sender
            brand_id = metadata.brand_id
            channel = metadata.channel
            
            self.log_util.info(
                service_name="UserTransactionService",
                message=f"Processing transaction for node {node_id} (type: {node_type}) for user {user_identifier} in flow {flow_id}"
            )
            
            # TODO: Implement transaction processing logic
            # This is a basic structure - add your transaction logic here
            # Examples:
            # - Save transaction to database
            # - Track user interactions
            # - Log analytics data
            # - Update user statistics
            
            # Create UserTransactionData object
            from models.user_transaction_data import UserTransactionData
            
            transaction = UserTransactionData(
                node_id=node_id,
                flow_id=flow_id,
                user_detail=user_detail if user_detail else {},
                channel=channel,
                channel_identifier_id=metadata.channel_identifier,
                processed_status="success",
                node_type=node_type,
                processed_value=processed_value,
                node_data=node_data,
                user_identifier=user_identifier,
                brand_id=brand_id
            )
            
            # Save to database if flow_db is available
            if self.flow_db:
                saved_transaction = await self.flow_db.save_user_transaction(transaction)
                if saved_transaction:
                    self.log_util.info(
                        service_name="UserTransactionService",
                        message=f"Transaction saved successfully with ID: {saved_transaction.id} for node {node_id}"
                    )
                else:
                    self.log_util.warning(
                        service_name="UserTransactionService",
                        message=f"Failed to save transaction for node {node_id}"
                    )
            else:
                self.log_util.warning(
                    service_name="UserTransactionService",
                    message=f"FlowDB not initialized, transaction not saved for node {node_id}"
                )
            
            return {
                "status": "success",
                "message": "Transaction processed successfully"
            }
            
        except Exception as e:
            self.log_util.error(
                service_name="UserTransactionService",
                message=f"Error processing transaction: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="UserTransactionService",
                message=f"Traceback: {traceback.format_exc()}"
            )
            return {
                "status": "error",
                "message": f"Error processing transaction: {str(e)}"
            }

