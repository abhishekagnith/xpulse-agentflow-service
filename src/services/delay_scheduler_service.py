"""
Delay Scheduler Service
Background service that monitors delay records and triggers delay_complete webhooks.
"""
import asyncio
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from utils.log_utils import LogUtil
from database.flow_db import FlowDB
from models.request.webhook_message_request import WebhookMessageRequest

if TYPE_CHECKING:
    from services.webhook_service import WebhookService
    from models.delay_data import DelayData


class DelaySchedulerService:
    """
    Background service that monitors delay records and triggers delay_complete webhooks
    when delay time expires.
    """
    
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB,
        webhook_service: Optional["WebhookService"] = None,
        check_interval_seconds: int = 60
    ):
        self.log_util = log_util
        self.flow_db = flow_db
        self.webhook_service = webhook_service
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task = None
    
    async def start(self):
        """
        Start the background scheduler task.
        """
        if self._running:
            self.log_util.warning(
                service_name="DelaySchedulerService",
                message="Scheduler is already running"
            )
            return
        
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        self.log_util.info(
            service_name="DelaySchedulerService",
            message=f"Delay scheduler started, checking every {self.check_interval_seconds} seconds"
        )
    
    async def stop(self):
        """
        Stop the background scheduler task.
        """
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.log_util.info(
            service_name="DelaySchedulerService",
            message="Delay scheduler stopped"
        )
    
    async def _scheduler_loop(self):
        """
        Main scheduler loop that checks for expired delays and triggers webhooks.
        """
        while self._running:
            try:
                await self._process_expired_delays()
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log_util.error(
                    service_name="DelaySchedulerService",
                    message=f"Error in scheduler loop: {str(e)}"
                )
                import traceback
                self.log_util.error(
                    service_name="DelaySchedulerService",
                    message=f"Traceback: {traceback.format_exc()}"
                )
                # Wait before retrying to avoid tight error loop
                await asyncio.sleep(self.check_interval_seconds)
    
    async def _process_expired_delays(self):
        """
        Process all expired delays and send delay_complete webhooks.
        """
        try:
            # Get all pending delays that have expired
            pending_delays = await self.flow_db.get_pending_delays()
            
            if not pending_delays:
                return
            
            self.log_util.info(
                service_name="DelaySchedulerService",
                message=f"Found {len(pending_delays)} expired delay(s) to process"
            )
            
            for delay in pending_delays:
                try:
                    await self._trigger_delay_complete_webhook(delay)
                    # Mark delay as processed
                    await self.flow_db.mark_delay_as_processed(delay.id)
                    self.log_util.info(
                        service_name="DelaySchedulerService",
                        message=f"Delay {delay.id} processed and marked as complete for user {delay.user_identifier}"
                    )
                except Exception as e:
                    self.log_util.error(
                        service_name="DelaySchedulerService",
                        message=f"Error processing delay {delay.id}: {str(e)}"
                    )
                    import traceback
                    self.log_util.error(
                        service_name="DelaySchedulerService",
                        message=f"Traceback: {traceback.format_exc()}"
                    )
        
        except Exception as e:
            self.log_util.error(
                service_name="DelaySchedulerService",
                message=f"Error getting pending delays: {str(e)}"
            )
    
    async def _trigger_delay_complete_webhook(self, delay):
        """
        Trigger delay_complete webhook for a delay record.
        
        Args:
            delay: DelayData object
        """
        if not self.webhook_service:
            self.log_util.error(
                service_name="DelaySchedulerService",
                message="WebhookService not initialized, cannot trigger delay_complete webhook"
            )
            return
        
        # Get user data to get user_id
        user_data = await self.flow_db.get_user_data(
            user_identifier=delay.user_identifier,
            brand_id=delay.brand_id,
            channel=delay.channel,
            channel_account_id=delay.channel_account_id
        )
        
        if not user_data:
            self.log_util.warning(
                service_name="DelaySchedulerService",
                message=f"User {delay.user_identifier} not found, skipping delay_complete webhook"
            )
            return
        
        # Create delay_complete webhook request
        # Use actual user_identifier as sender so it finds the correct user
        webhook_request = WebhookMessageRequest(
            sender=delay.user_identifier,  # Use actual user identifier, not "system"
            brand_id=delay.brand_id,
            user_id=user_data.user_id,
            channel_identifier=delay.channel_account_id,
            channel=delay.channel,  # Use actual channel, not "system"
            message_type="delay_complete",
            message_body={
                "user_identifier": delay.user_identifier,
                "flow_id": delay.flow_id,
                "node_id": delay.delay_node_id,
                "delay_completed_at": datetime.utcnow().isoformat(),
                "delay_duration": delay.delay_duration,
                "delay_unit": delay.delay_unit
            }
        )
        
        # Send webhook to webhook service
        result = await self.webhook_service.process_webhook_message(webhook_request)
        
        if result.get("status") == "success" or result.get("automation_triggered"):
            self.log_util.info(
                service_name="DelaySchedulerService",
                message=f"Successfully triggered delay_complete webhook for user {delay.user_identifier}, delay {delay.id}"
            )
        else:
            self.log_util.error(
                service_name="DelaySchedulerService",
                message=f"Failed to trigger delay_complete webhook for user {delay.user_identifier}: {result.get('message')}"
            )

