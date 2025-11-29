from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException

# Utils
from utils.log_utils import LogUtil

# Services
from services.flow_service import FlowService

# Exceptions
from exceptions.flow_exception import FlowServiceException

def create_flow_api(
    log_util: LogUtil,
    flow_service: FlowService
) -> APIRouter:
    router = APIRouter(
        prefix="/flow",
        tags=["flow"],
    )

    @router.post("/create")
    async def create_flow(request: Request, flow_data: dict):
        try:
            user_id = request.headers.get("x-user-id")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Unauthorized")
            user_id = int(user_id)
            
            return await flow_service.create_flow(user_id=user_id, flow_data=flow_data)
        except FlowServiceException as e:
            log_util.error(service_name="FlowService", message=f"Error creating flow: {e}")
            raise HTTPException(status_code=e.status_code, detail=e.message)
        except Exception as e:
            log_util.error(service_name="FlowService", message=f"Error creating flow: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/list")
    async def get_flows_list(request: Request):
        try:
            user_id = request.headers.get("x-user-id")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Unauthorized")
            user_id = int(user_id)
            
            return await flow_service.get_flows_list(user_id=user_id)
        except FlowServiceException as e:
            log_util.error(service_name="FlowService", message=f"Error getting flows list: {e}")
            raise HTTPException(status_code=e.status_code, detail=e.message)
        except Exception as e:
            log_util.error(service_name="FlowService", message=f"Error getting flows list: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/detail/{flow_id}")
    async def get_flow_detail(request: Request, flow_id: str):
        try:
            user_id = request.headers.get("x-user-id")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            return await flow_service.get_flow_detail(flow_id=flow_id)
        except FlowServiceException as e:
            log_util.error(service_name="FlowService", message=f"Error getting flow detail: {e}")
            raise HTTPException(status_code=e.status_code, detail=e.message)
        except Exception as e:
            log_util.error(service_name="FlowService", message=f"Error getting flow detail: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.put("/update/{flow_id}")
    async def update_flow(request: Request, flow_id: str, flow_data: dict):
        try:
            user_id = request.headers.get("x-user-id")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Unauthorized")
            user_id = int(user_id)
            
            return await flow_service.update_flow(user_id=user_id, flow_id=flow_id, flow_data=flow_data)
        except FlowServiceException as e:
            log_util.error(service_name="FlowService", message=f"Error updating flow: {e}")
            raise HTTPException(status_code=e.status_code, detail=e.message)
        except Exception as e:
            log_util.error(service_name="FlowService", message=f"Error updating flow: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/status/{flow_id}")
    async def update_flow_status(request: Request, flow_id: str, status_data: dict):
        """
        Update flow status. Valid statuses: "published", "stop"
        
        Request body:
        {
            "status": "published" | "stop"
        }
        """
        try:
            user_id = request.headers.get("x-user-id")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Unauthorized")
            user_id = int(user_id)
            
            # Extract status from request body
            status = status_data.get("status")
            if not status:
                raise HTTPException(status_code=400, detail="Status is required in request body")
            
            return await flow_service.update_flow_status(user_id=user_id, flow_id=flow_id, status=status)
        except FlowServiceException as e:
            log_util.error(service_name="FlowService", message=f"Error updating flow status: {e}")
            raise HTTPException(status_code=e.status_code, detail=e.message)
        except HTTPException:
            raise
        except Exception as e:
            log_util.error(service_name="FlowService", message=f"Error updating flow status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router

