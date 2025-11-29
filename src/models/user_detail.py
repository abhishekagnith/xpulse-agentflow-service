from pydantic import BaseModel, Field
from typing import Optional


class UserDetail(BaseModel):
    """
    User detail object containing channel-specific identifiers.
    Based on the channel, the appropriate identifier field will be populated.
    """
    phone_number: Optional[str] = Field(default=None, description="Phone number (for WhatsApp, SMS, Telegram)")
    email: Optional[str] = Field(default=None, description="Email address (for Gmail, Email channels)")
    instagram_user_id: Optional[str] = Field(default=None, description="Instagram user ID (for Instagram)")
    facebook_user_id: Optional[str] = Field(default=None, description="Facebook user ID (for Facebook)")
    telegram_user_id: Optional[str] = Field(default=None, description="Telegram user ID (for Telegram)")
    custom_identifier: Optional[str] = Field(default=None, description="Custom identifier for other channels")
    
    def get_identifier(self, channel: str) -> Optional[str]:
        """
        Get the appropriate identifier based on the channel.
        Returns the identifier string or None if not found.
        """
        channel_lower = channel.lower()
        
        if channel_lower == "whatsapp" or channel_lower == "sms":
            return self.phone_number
        elif channel_lower == "gmail" or channel_lower == "email":
            return self.email
        elif channel_lower == "instagram":
            return self.instagram_user_id
        elif channel_lower == "facebook":
            return self.facebook_user_id
        elif channel_lower == "telegram":
            return self.telegram_user_id
        else:
            # For unknown channels, try custom_identifier or return first available
            return self.custom_identifier or self.phone_number or self.email
    
    def set_identifier(self, channel: str, identifier: str) -> None:
        """
        Set the appropriate identifier based on the channel.
        """
        channel_lower = channel.lower()
        
        if channel_lower == "whatsapp" or channel_lower == "sms":
            self.phone_number = identifier
        elif channel_lower == "gmail" or channel_lower == "email":
            self.email = identifier
        elif channel_lower == "instagram":
            self.instagram_user_id = identifier
        elif channel_lower == "facebook":
            self.facebook_user_id = identifier
        elif channel_lower == "telegram":
            self.telegram_user_id = identifier
        else:
            self.custom_identifier = identifier

