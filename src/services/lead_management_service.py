"""
Lead Management Service
Handles integration with lead management service for user/lead creation and lookup.
"""
from typing import Optional, Dict, Any
import httpx

from utils.log_utils import LogUtil


class LeadManagementService:
    """
    Service for managing leads through the lead management API.
    Handles checking if user exists and creating new leads.
    """
    
    def __init__(
        self,
        log_util: LogUtil,
        lead_management_base_url: str = "https://agentcord.ai/landing-page/user"
    ):
        self.log_util = log_util
        self.lead_management_base_url = lead_management_base_url
    
    async def get_or_create_lead(
        self,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        address: Optional[str] = None,
        brand_id: int = None,
        user_id: int = None
    ) -> Optional[str]:
        """
        Get existing lead ID or create new lead.
        
        First checks if user exists by phone or email.
        If user exists, returns the lead ID from response.
        If user doesn't exist, creates new user and returns the lead ID.
        
        Args:
            phone: Phone number (optional, but phone or email required)
            email: Email address (optional, but phone or email required)
            first_name: First name (optional, for new user creation)
            last_name: Last name (optional, for new user creation)
            address: Address (optional, for new user creation)
            brand_id: Brand ID (required for new user creation)
            user_id: User ID for x-user-id header (required)
        
        Returns:
            Lead ID (str) if successful, None if failed
        """
        try:
            if not user_id:
                self.log_util.error(
                    service_name="LeadManagementService",
                    message="user_id is required for lead management API calls"
                )
                return None
            
            if not phone and not email:
                self.log_util.error(
                    service_name="LeadManagementService",
                    message="Either phone or email is required to check/create lead"
                )
                return None
            
            # Step 1: Check if user exists by phone
            lead_id = None
            if phone:
                lead_id = await self._check_user_exists(
                    filter_by="phone",
                    filter_value=phone,
                    user_id=user_id
                )
                if lead_id:
                    self.log_util.info(
                        service_name="LeadManagementService",
                        message=f"Found existing lead by phone: {lead_id}"
                    )
                    return lead_id
            
            # Step 2: Check if user exists by email (if not found by phone)
            if not lead_id and email:
                lead_id = await self._check_user_exists(
                    filter_by="email",
                    filter_value=email,
                    user_id=user_id
                )
                if lead_id:
                    self.log_util.info(
                        service_name="LeadManagementService",
                        message=f"Found existing lead by email: {lead_id}"
                    )
                    return lead_id
            
            # Step 3: User doesn't exist, create new user
            if not lead_id:
                if not brand_id:
                    self.log_util.error(
                        service_name="LeadManagementService",
                        message="brand_id is required to create new lead"
                    )
                    return None
                
                lead_id = await self._create_new_user(
                    phone=phone,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    address=address,
                    brand_id=brand_id,
                    user_id=user_id
                )
                if lead_id:
                    self.log_util.info(
                        service_name="LeadManagementService",
                        message=f"Created new lead: {lead_id}"
                    )
                    return lead_id
            
            return None
            
        except Exception as e:
            self.log_util.error(
                service_name="LeadManagementService",
                message=f"Error in get_or_create_lead: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="LeadManagementService",
                message=f"Traceback: {traceback.format_exc()}"
            )
            return None
    
    async def _check_user_exists(
        self,
        filter_by: str,
        filter_value: str,
        user_id: int
    ) -> Optional[str]:
        """
        Check if user exists in lead management service.
        
        Args:
            filter_by: "phone" or "email"
            filter_value: Phone number or email address
            user_id: User ID for x-user-id header
        
        Returns:
            Lead ID if user exists, None otherwise
        """
        try:
            url = f"{self.lead_management_base_url}/get-users"
            params = {
                "filter_by": filter_by,
                "filter_value": filter_value
            }
            
            headers = {
                "x-user-id": str(user_id),
                "Content-Type": "application/json"
            }
            
            self.log_util.info(
                service_name="LeadManagementService",
                message=f"Checking if user exists: {filter_by}={filter_value}"
            )
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params, headers=headers)
                
                if response.status_code == 200:
                    response_data = response.json()
                    
                    # Check if response contains user data
                    # Assuming response format: {"users": [...]} or {"id": "...", ...} or [{"id": "...", ...}]
                    if isinstance(response_data, dict):
                        # Check if response has users array
                        if "users" in response_data and isinstance(response_data["users"], list) and len(response_data["users"]) > 0:
                            # Get first user's ID
                            first_user = response_data["users"][0]
                            if isinstance(first_user, dict) and "id" in first_user:
                                return str(first_user["id"])
                        # Check if response has id directly
                        elif "id" in response_data:
                            return str(response_data["id"])
                    elif isinstance(response_data, list) and len(response_data) > 0:
                        # Response is array of users
                        first_user = response_data[0]
                        if isinstance(first_user, dict) and "id" in first_user:
                            return str(first_user["id"])
                    
                    # User not found
                    self.log_util.info(
                        service_name="LeadManagementService",
                        message=f"User not found with {filter_by}={filter_value}"
                    )
                    return None
                else:
                    self.log_util.warning(
                        service_name="LeadManagementService",
                        message=f"Lead management API returned error: {response.status_code} - {response.text}"
                    )
                    return None
                    
        except httpx.TimeoutException:
            self.log_util.error(
                service_name="LeadManagementService",
                message=f"Timeout while checking user existence: {filter_by}={filter_value}"
            )
            return None
        except Exception as e:
            self.log_util.error(
                service_name="LeadManagementService",
                message=f"Error checking user existence: {str(e)}"
            )
            return None
    
    async def _create_new_user(
        self,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        address: Optional[str] = None,
        brand_id: int = None,
        user_id: int = None
    ) -> Optional[str]:
        """
        Create new user in lead management service.
        
        Args:
            phone: Phone number (optional)
            email: Email address (optional)
            first_name: First name (optional)
            last_name: Last name (optional)
            address: Address (optional)
            brand_id: Brand ID (required)
            user_id: User ID for x-user-id header (required)
        
        Returns:
            Lead ID if successful, None if failed
        """
        try:
            url = f"{self.lead_management_base_url}/add-user"
            
            # Build request payload
            payload = {
                "brand_id": brand_id
            }
            
            if phone:
                payload["phone"] = phone
            if email:
                payload["email"] = email
            if first_name:
                payload["first_name"] = first_name
            if last_name:
                payload["last_name"] = last_name
            if address:
                payload["address"] = address
            
            headers = {
                "x-user-id": str(user_id),
                "Content-Type": "application/json"
            }
            
            self.log_util.info(
                service_name="LeadManagementService",
                message=f"Creating new user with phone={phone}, email={email}, brand_id={brand_id}"
            )
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200 or response.status_code == 201:
                    response_data = response.json()
                    
                    # Extract lead ID from response
                    # Assuming response format: {"id": "...", ...} or {"user": {"id": "..."}, ...}
                    if isinstance(response_data, dict):
                        if "id" in response_data:
                            return str(response_data["id"])
                        elif "user" in response_data and isinstance(response_data["user"], dict) and "id" in response_data["user"]:
                            return str(response_data["user"]["id"])
                    
                    self.log_util.error(
                        service_name="LeadManagementService",
                        message=f"Unexpected response format from create user API: {response_data}"
                    )
                    return None
                else:
                    self.log_util.error(
                        service_name="LeadManagementService",
                        message=f"Failed to create user: {response.status_code} - {response.text}"
                    )
                    return None
                    
        except httpx.TimeoutException:
            self.log_util.error(
                service_name="LeadManagementService",
                message="Timeout while creating new user"
            )
            return None
        except Exception as e:
            self.log_util.error(
                service_name="LeadManagementService",
                message=f"Error creating new user: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="LeadManagementService",
                message=f"Traceback: {traceback.format_exc()}"
            )
            return None

