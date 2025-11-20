from typing import Optional
import httpx

# Utils
from utils.log_utils import LogUtil

# Models
from models.response.user.user_data import UserData


class UserService:
    """Service for handling user related operations."""
    def __init__(self, log_util: LogUtil):
        self.user_service_url = "http://143.244.131.181:8007/auth/user"
        self.log_util = log_util

    async def get_user_info(self, user_id: str) -> Optional[UserData]:
        user_details_url = f"{self.user_service_url}/fetch/{user_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(user_details_url)
            if response.status_code == 200:
                return UserData(**response.json())
            return None