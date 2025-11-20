from fastapi import APIRouter, Request, HTTPException
import httpx
from typing import Dict, Any

# Utils
from utils.log_utils import LogUtil

# Models
from models.request.process_node_request import ProcessNodeRequest
from models.response.process_node_response import ProcessNodeResponse


def create_node_process_api(log_util: LogUtil) -> APIRouter:
    """
    API for sending node processing requests to channel services
    Flow service calls this internally to request channel-specific message sending
    """
    router = APIRouter(
        prefix="/agentflow/node",
        tags=["node_processing"],
    )

    @router.post("/process", response_model=ProcessNodeResponse)
    async def process_node(process_request: ProcessNodeRequest):
        """
        Process a flow node by calling the appropriate channel service
        
        This endpoint acts as a proxy/router that:
        1. Receives node processing request from flow logic
        2. Determines which channel service to call based on process_request.channel
        3. Forwards request to channel-specific service (WhatsApp, Email, SMS, etc.)
        4. Returns standardized response
        
        Channel Services Configuration:
        - whatsapp: http://localhost:8017/channel/process-node
        - email: http://localhost:8019/channel/process-node
        - sms: http://localhost:8020/channel/process-node
        - facebook: http://localhost:8021/channel/process-node
        """
        try:
            # Map channels to their service endpoints
            channel_endpoints = {
                "whatsapp": "http://localhost:8017/channel/process-node",
                "email": "http://localhost:8019/channel/process-node",
                "sms": "http://localhost:8020/channel/process-node",
                "facebook": "http://localhost:8021/channel/process-node",
                "instagram": "http://localhost:8022/channel/process-node",
            }
            
            channel = process_request.channel.lower()
            
            if channel not in channel_endpoints:
                log_util.error(
                    service_name="NodeProcessAPI",
                    message=f"Unsupported channel: {channel}"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported channel: {channel}. Supported: {list(channel_endpoints.keys())}"
                )
            
            # Get the channel service endpoint
            channel_endpoint = channel_endpoints[channel]
            
            log_util.info(
                service_name="NodeProcessAPI",
                message=f"Forwarding node processing request to {channel} service at {channel_endpoint}"
            )
            
            # Forward request to channel service
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    response = await client.post(
                        channel_endpoint,
                        json=process_request.model_dump(),
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        log_util.info(
                            service_name="NodeProcessAPI",
                            message=f"Successfully processed node via {channel} service"
                        )
                        return ProcessNodeResponse(**response_data)
                    else:
                        log_util.error(
                            service_name="NodeProcessAPI",
                            message=f"Channel service returned error: {response.status_code} - {response.text}"
                        )
                        return ProcessNodeResponse(
                            status="error",
                            message=f"Channel service error: {response.text}",
                            flow_id=process_request.flow_id,
                            next_node_id=process_request.next_node_id,
                            automation_exited=False
                        )
                        
                except httpx.TimeoutException:
                    log_util.error(
                        service_name="NodeProcessAPI",
                        message=f"Timeout calling {channel} service"
                    )
                    return ProcessNodeResponse(
                        status="error",
                        message=f"Timeout calling {channel} service",
                        flow_id=process_request.flow_id,
                        next_node_id=process_request.next_node_id,
                        automation_exited=False
                    )
                    
                except httpx.RequestError as e:
                    log_util.error(
                        service_name="NodeProcessAPI",
                        message=f"Error calling {channel} service: {str(e)}"
                    )
                    return ProcessNodeResponse(
                        status="error",
                        message=f"Error calling {channel} service: {str(e)}",
                        flow_id=process_request.flow_id,
                        next_node_id=process_request.next_node_id,
                        automation_exited=False
                    )
                    
        except HTTPException:
            raise
        except Exception as e:
            log_util.error(
                service_name="NodeProcessAPI",
                message=f"Unexpected error processing node: {str(e)}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Internal error: {str(e)}"
            )

    @router.get("/channels")
    async def get_supported_channels():
        """
        Get list of supported channels and their endpoints
        """
        return {
            "channels": [
                {
                    "name": "whatsapp",
                    "endpoint": "http://localhost:8017/channel/process-node",
                    "description": "WhatsApp Business API"
                },
                {
                    "name": "email",
                    "endpoint": "http://localhost:8019/channel/process-node",
                    "description": "Email (SMTP/SendGrid)"
                },
                {
                    "name": "sms",
                    "endpoint": "http://localhost:8020/channel/process-node",
                    "description": "SMS (Twilio/Vonage)"
                },
                {
                    "name": "facebook",
                    "endpoint": "http://localhost:8021/channel/process-node",
                    "description": "Facebook Messenger"
                },
                {
                    "name": "instagram",
                    "endpoint": "http://localhost:8022/channel/process-node",
                    "description": "Instagram Direct Messages"
                }
            ]
        }

    return router

