from typing import Optional, Dict, Any
import httpx
import os

# Utils
from utils.log_utils import LogUtil
from utils.environment_utils import EnvironmentUtils

# Database
from database.flow_db import FlowDB

# Models
from models.flow_data import FlowData


class GmailFlowService:
    """
    Service for handling Gmail/Email flow operations.
    Handles sending email templates via the email service API.
    """
    
    def __init__(
        self,
        log_util: LogUtil,
        flow_db: FlowDB,
        environment_utils: Optional[EnvironmentUtils] = None,
        email_service_api_url: Optional[str] = None,
    ):
        self.log_util = log_util
        self.flow_db = flow_db
        self.environment_utils = environment_utils
        
        # Default to localhost, but can be overridden for different deployments
        self.email_service_api_url = email_service_api_url or "http://localhost:8019/campaign-recipients/direct-send"
        
        # Get source_email from environment or use default
        if self.environment_utils:
            try:
                self.default_source_email = self.environment_utils.get_env_variable("EMAIL_SOURCE_ADDRESS")
            except ValueError:
                self.default_source_email = os.getenv("EMAIL_SOURCE_ADDRESS", "noreply@example.com")
        else:
            self.default_source_email = os.getenv("EMAIL_SOURCE_ADDRESS", "noreply@example.com")
        
        # Get configuration_set_name from environment or use default
        if self.environment_utils:
            try:
                self.default_configuration_set_name = self.environment_utils.get_env_variable("EMAIL_CONFIGURATION_SET_NAME")
            except ValueError:
                self.default_configuration_set_name = os.getenv("EMAIL_CONFIGURATION_SET_NAME", "my-first-configuration-set")
        else:
            self.default_configuration_set_name = os.getenv("EMAIL_CONFIGURATION_SET_NAME", "my-first-configuration-set")

    async def send_email_template(
        self,
        flow_id: str,
        template_name: str,
        recipients: list,
        brand_id: int,
        user_id: int,
        source_email: Optional[str] = None,
        configuration_set_name: Optional[str] = None,
        lead_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send email template via the email service API.
        
        Args:
            flow_id: Flow ID
            template_name: Email template name
            source_email: Source email address (optional, uses default if not provided)
            configuration_set_name: Configuration set name (optional, uses default if not provided)
            recipients: List of recipient dicts with lead_id
            brand_id: Brand ID
            user_id: User ID
            lead_id: Optional lead ID (if single recipient)
        
        Returns:
            Dict with status and response data
        """
        try:
            # Use provided source_email or default
            final_source_email = source_email or self.default_source_email
            
            # Use provided configuration_set_name or default
            final_configuration_set_name = configuration_set_name or self.default_configuration_set_name
            
            # Prepare recipients list
            recipients_list = []
            if lead_id:
                # Single recipient
                recipients_list.append({"lead_id": str(lead_id)})
            elif recipients:
                # Multiple recipients provided
                recipients_list = [{"lead_id": str(r.get("lead_id"))} for r in recipients if r.get("lead_id")]
            else:
                return {
                    "status": "error",
                    "message": "No recipients provided. Either lead_id or recipients list is required.",
                    "success": False
                }
            
            if not recipients_list:
                return {
                    "status": "error",
                    "message": "No valid recipients found. Recipients must have lead_id.",
                    "success": False
                }
            
            # Prepare request body
            request_body = {
                "flow_id": flow_id,
                "template_name": template_name,
                "source_email": final_source_email,
                "configuration_set_name": final_configuration_set_name,
                "recipients": recipients_list,
                "brand_id": brand_id,
                "user_id": user_id
            }
            
            self.log_util.info(
                service_name="GmailFlowService",
                message=f"[SEND_EMAIL_TEMPLATE] Sending email template request to {self.email_service_api_url}: "
                        f"flow_id={flow_id}, template_name={template_name}, "
                        f"recipients_count={len(recipients_list)}, brand_id={brand_id}, user_id={user_id}"
            )
            self.log_util.debug(
                service_name="GmailFlowService",
                message=f"[SEND_EMAIL_TEMPLATE] Full request payload: {request_body}"
            )
            
            # Make API call to email service
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.email_service_api_url,
                    json=request_body,
                    headers={
                        "Content-Type": "application/json",
                        "x-user-id": str(user_id)
                    }
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    self.log_util.info(
                        service_name="GmailFlowService",
                        message=f"[SEND_EMAIL_TEMPLATE] Email template sent successfully: {response_data.get('message', '')}"
                    )
                    return {
                        "status": "success",
                        "message": response_data.get("message", "Email template sent successfully"),
                        "success": response_data.get("success", True),
                        "recipients_created": response_data.get("recipients_created", 0),
                        "emails_sent": response_data.get("emails_sent", 0),
                        "emails_failed": response_data.get("emails_failed", 0),
                        "results": response_data.get("results", [])
                    }
                else:
                    error_detail = response.json().get("detail", response.text) if response.headers.get("content-type", "").startswith("application/json") else response.text
                    self.log_util.error(
                        service_name="GmailFlowService",
                        message=f"[SEND_EMAIL_TEMPLATE] Email service API returned error: {response.status_code} - {error_detail}"
                    )
                    return {
                        "status": "error",
                        "message": f"Email service API error: {error_detail}",
                        "success": False,
                        "status_code": response.status_code
                    }
                    
        except httpx.TimeoutException:
            self.log_util.error(
                service_name="GmailFlowService",
                message=f"[SEND_EMAIL_TEMPLATE] Timeout calling email service API"
            )
            return {
                "status": "error",
                "message": "Timeout calling email service API",
                "success": False
            }
        except Exception as e:
            self.log_util.error(
                service_name="GmailFlowService",
                message=f"[SEND_EMAIL_TEMPLATE] Error calling email service API: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="GmailFlowService",
                message=f"[SEND_EMAIL_TEMPLATE] Traceback: {traceback.format_exc()}"
            )
            return {
                "status": "error",
                "message": f"Error calling email service API: {str(e)}",
                "success": False
            }

    async def process_email_template_node(
        self,
        flow: FlowData,
        node_data: Dict[str, Any],
        user_identifier: str,
        brand_id: int,
        user_id: int,
        lead_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a send_email_template node.
        
        Args:
            flow: Flow data object
            node_data: Email template node data
            user_identifier: User identifier
            brand_id: Brand ID
            user_id: User ID
            lead_id: Optional lead ID
        
        Returns:
            Dict with status and response data
        """
        try:
            # Extract email template information from node
            email_template_mongo_id = node_data.get("emailTemplateMongoId")
            email_template_name = node_data.get("emailTemplateName")
            
            if not email_template_mongo_id:
                return {
                    "status": "error",
                    "message": "emailTemplateMongoId is required in send_email_template node",
                    "success": False
                }
            
            # Use emailTemplateName if provided, otherwise use emailTemplateMongoId as template_name
            template_name = email_template_name or email_template_mongo_id
            
            # Extract source_email from node data if available
            source_email = node_data.get("sourceEmail") or node_data.get("source_email")
            
            # If source_email is not in node data, fetch from flow_settings
            if not source_email:
                node_id = node_data.get("id")
                if node_id:
                    self.log_util.info(
                        service_name="GmailFlowService",
                        message=f"[PROCESS_EMAIL_TEMPLATE_NODE] source_email not found in node data, fetching from flow_settings: flow_id={flow.id}, node_id={node_id}"
                    )
                    flow_settings = await self.flow_db.get_flow_settings(flow.id, node_id)
                    if flow_settings and flow_settings.email:
                        source_email = flow_settings.email.source_email
                        self.log_util.info(
                            service_name="GmailFlowService",
                            message=f"[PROCESS_EMAIL_TEMPLATE_NODE] Found source_email in flow_settings: {source_email}"
                        )
                    else:
                        self.log_util.info(
                            service_name="GmailFlowService",
                            message=f"[PROCESS_EMAIL_TEMPLATE_NODE] No flow_settings found for flow_id={flow.id}, node_id={node_id}, will use default"
                        )
                else:
                    self.log_util.warning(
                        service_name="GmailFlowService",
                        message=f"[PROCESS_EMAIL_TEMPLATE_NODE] node_id not found in node_data, cannot fetch from flow_settings"
                    )
            
            # Extract configuration_set_name from node data if available
            configuration_set_name = node_data.get("configurationSetName") or node_data.get("configuration_set_name")
            
            # Prepare recipients - use lead_id if provided
            recipients = []
            if lead_id:
                recipients = [{"lead_id": lead_id}]
            
            # Call send_email_template
            result = await self.send_email_template(
                flow_id=flow.id,
                template_name=template_name,
                recipients=recipients,
                brand_id=brand_id,
                user_id=user_id,
                source_email=source_email,
                configuration_set_name=configuration_set_name,
                lead_id=lead_id
            )
            
            return result
            
        except Exception as e:
            self.log_util.error(
                service_name="GmailFlowService",
                message=f"[PROCESS_EMAIL_TEMPLATE_NODE] Error processing email template node: {str(e)}"
            )
            import traceback
            self.log_util.error(
                service_name="GmailFlowService",
                message=f"[PROCESS_EMAIL_TEMPLATE_NODE] Traceback: {traceback.format_exc()}"
            )
            return {
                "status": "error",
                "message": f"Error processing email template node: {str(e)}",
                "success": False
            }

