"""
Channel Message Adapter Service
Normalizes channel-specific message payloads to a consistent structure.
"""
from typing import Optional, Dict, Any
from utils.log_utils import LogUtil


class NormalizedMessage:
    """
    Normalized message structure that all channels should conform to.
    Simplified structure with user_reply, media_url, and media_type.
    """
    def __init__(
        self,
        user_reply: Optional[str] = None,
        media_url: Optional[str] = None,
        media_type: Optional[str] = None
    ):
        self.user_reply = user_reply
        self.media_url = media_url
        self.media_type = media_type
    
    def get_text_content(self) -> Optional[str]:
        """
        Get the primary text content for trigger matching and processing.
        Returns user_reply if available.
        """
        return self.user_reply
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/transmission"""
        # Check if custom data was set (for system webhooks)
        if hasattr(self, '_custom_data'):
            return self._custom_data
        
        # Regular channel webhooks
        result = {}
        if self.user_reply:
            result["user_reply"] = self.user_reply
        if self.media_url:
            result["media_url"] = self.media_url
        if self.media_type:
            result["media_type"] = self.media_type
        return result


class ChannelMessageAdapter:
    """
    Adapter service to normalize channel-specific message payloads.
    Each channel has its own parser that converts to NormalizedMessage.
    """
    
    def __init__(self, log_util: LogUtil):
        self.log_util = log_util
    
    def normalize_message(
        self,
        channel: str,
        message_type: str,
        message_body: Dict[str, Any]
    ) -> NormalizedMessage:
        """
        Normalize channel-specific message to common structure.
        
        Args:
            channel: Channel name (whatsapp, gmail, telegram, sms, etc.) or "system" for internal webhooks
            message_type: Message type (text, button, interactive, email, delay_complete, scheduled_trigger, etc.)
            message_body: Channel-specific message payload
        
        Returns:
            NormalizedMessage with consistent structure
        """
        channel_lower = channel.lower()
        
        # Handle system/internal webhook types
        if message_type == "delay_complete":
            return self._normalize_delay_complete(message_body)
        elif message_type == "scheduled_trigger":
            return self._normalize_scheduled_trigger(message_body)
        
        # Handle channel-specific webhooks
        if channel_lower == "whatsapp":
            return self._normalize_whatsapp(message_type, message_body)
        elif channel_lower in ["gmail", "email"]:
            return self._normalize_email(message_type, message_body)
        elif channel_lower == "telegram":
            return self._normalize_telegram(message_type, message_body)
        elif channel_lower == "sms":
            return self._normalize_sms(message_type, message_body)
        elif channel_lower == "instagram":
            return self._normalize_instagram(message_type, message_body)
        elif channel_lower == "facebook":
            return self._normalize_facebook(message_type, message_body)
        else:
            # Default: try to extract common fields
            self.log_util.warning(
                service_name="ChannelMessageAdapter",
                message=f"Unknown channel '{channel}', using generic normalization"
            )
            return self._normalize_generic(message_type, message_body)
    
    def _normalize_whatsapp(self, message_type: str, message_body: Dict[str, Any]) -> NormalizedMessage:
        """Normalize WhatsApp message format"""
        user_reply = None
        media_url = None
        media_type = None
        
        if message_type == "text":
            if message_body.get("type") == "text" and "text" in message_body:
                user_reply = message_body["text"].get("body", "").strip()
        
        elif message_type == "button":
            if message_body.get("type") == "button" and "button" in message_body:
                button_data = message_body["button"]
                # Prefer text over payload
                user_reply = button_data.get("text", button_data.get("payload", "")).strip()
        
        elif message_type == "interactive":
            interactive_data = message_body.get("interactive", {})
            interactive_type = interactive_data.get("type")
            
            if interactive_type == "button_reply":
                button_reply = interactive_data.get("button_reply", {})
                user_reply = button_reply.get("title", button_reply.get("id", "")).strip()
            elif interactive_type == "list_reply":
                list_reply = interactive_data.get("list_reply", {})
                user_reply = list_reply.get("title", list_reply.get("id", "")).strip()
        
        elif message_type in ["image", "video", "audio", "document"]:
            media_type = message_type
            media_data = message_body.get(message_type, {})
            media_url = media_data.get("url") or media_data.get("link")
            # Extract caption if available as user_reply
            user_reply = media_data.get("caption", "").strip() or None
        
        return NormalizedMessage(
            user_reply=user_reply,
            media_url=media_url,
            media_type=media_type
        )
    
    def _normalize_email(self, message_type: str, message_body: Dict[str, Any]) -> NormalizedMessage:
        """Normalize Gmail/Email message format"""
        subject = message_body.get("subject", "").strip()
        body = message_body.get("body", "").strip() or message_body.get("text", "").strip()
        # Use subject as primary user_reply, fallback to body
        user_reply = subject or body or None
        
        return NormalizedMessage(
            user_reply=user_reply,
            raw_data=message_body
        )
    
    def _normalize_telegram(self, message_type: str, message_body: Dict[str, Any]) -> NormalizedMessage:
        """Normalize Telegram message format"""
        user_reply = None
        
        # Telegram format: {"message": {"text": "...", "from": {...}}}
        message = message_body.get("message", message_body)
        user_reply = message.get("text", "").strip() or None
        
        # Handle callback queries (button presses)
        if message_type == "callback_query":
            callback_data = message_body.get("callback_query", {})
            user_reply = callback_data.get("data", "").strip() or None
        
        return NormalizedMessage(
            user_reply=user_reply,
            raw_data=message_body
        )
    
    def _normalize_sms(self, message_type: str, message_body: Dict[str, Any]) -> NormalizedMessage:
        """Normalize SMS message format"""
        user_reply = message_body.get("text", message_body.get("body", message_body.get("message", ""))).strip() or None
        
        return NormalizedMessage(
            user_reply=user_reply,
            raw_data=message_body
        )
    
    def _normalize_instagram(self, message_type: str, message_body: Dict[str, Any]) -> NormalizedMessage:
        """Normalize Instagram message format"""
        user_reply = None
        
        # Instagram format varies, try common fields
        if "text" in message_body:
            user_reply = message_body["text"].strip() or None
        elif "message" in message_body:
            user_reply = message_body["message"].get("text", "").strip() or None
        
        return NormalizedMessage(
            user_reply=user_reply,
            raw_data=message_body
        )
    
    def _normalize_facebook(self, message_type: str, message_body: Dict[str, Any]) -> NormalizedMessage:
        """Normalize Facebook Messenger message format"""
        user_reply = None
        
        # Facebook format: {"message": {"text": "..."}}
        message = message_body.get("message", {})
        user_reply = message.get("text", "").strip() or None
        
        # Handle postbacks (button presses)
        if message_type == "postback":
            postback = message_body.get("postback", {})
            user_reply = postback.get("title", postback.get("payload", "")).strip() or None
        
        return NormalizedMessage(
            user_reply=user_reply,
            raw_data=message_body
        )
    
    def _normalize_generic(self, message_type: str, message_body: Dict[str, Any]) -> NormalizedMessage:
        """Generic normalization for unknown channels"""
        # Try to find common text fields
        user_reply = (
            message_body.get("text") or
            message_body.get("body") or
            message_body.get("message") or
            message_body.get("content")
        )
        
        if isinstance(user_reply, dict):
            user_reply = user_reply.get("text") or user_reply.get("body") or None
        
        if user_reply:
            user_reply = str(user_reply).strip() or None
        else:
            user_reply = None
        
        return NormalizedMessage(
            user_reply=user_reply
        )
    
    def _normalize_delay_complete(self, message_body: Dict[str, Any]) -> NormalizedMessage:
        """
        Normalize delay completion webhook for automation flows.
        
        Expected input structure:
        {
            "user_identifier": "919634086404",
            "flow_id": "691ee40841e8102454474848",
            "node_id": "delay-node-1764137867486-8xdbezftq",
            "delay_completed_at": "2025-11-26T10:30:00Z",
            "delay_duration": 60,
            "delay_unit": "minutes"
        }
        
        Returns NormalizedMessage with user_state_id in data (extracted from user_identifier)
        """
        # Extract user_state_id (user_identifier) from message_body
        user_state_id = message_body.get("user_identifier")
        
        # Create a custom data structure with only user_state_id
        # We'll override to_dict to return this structure
        normalized = NormalizedMessage(user_reply=None)
        normalized._custom_data = {"user_state_id": user_state_id} if user_state_id else {}
        return normalized
    
    def _normalize_scheduled_trigger(self, message_body: Dict[str, Any]) -> NormalizedMessage:
        """
        Normalize scheduled/time-based trigger webhook.
        
        Expected input structure:
        {
            "trigger_id": "trigger_123",
            "flow_id": "691ee40841e8102454474848",
            "trigger_node_id": "trigger_keyword-node-1763631396283-h1ymxv3e3",
            "scheduled_time": "2025-11-26T10:00:00Z",
            "trigger_type": "scheduled",  # or "recurring", "one_time"
            "recurrence_pattern": "daily",  # optional: "daily", "weekly", "monthly", etc.
            "target_users": ["user1", "user2"],  # optional: specific users to trigger
            "target_brand_id": 1  # optional: specific brand
        }
        
        Returns NormalizedMessage with flow_id in data
        """
        # Extract flow_id from message_body
        flow_id = message_body.get("flow_id")
        
        # Create a custom data structure with only flow_id
        # We'll override to_dict to return this structure
        normalized = NormalizedMessage(user_reply=None)
        normalized._custom_data = {"flow_id": flow_id} if flow_id else {}
        return normalized

