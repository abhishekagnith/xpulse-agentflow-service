from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException

# Utils
from utils.log_utils import LogUtil

# Database
from database.flow_db import FlowDB

# Exceptions
from exceptions.flow_exception import FlowServiceException


def create_node_detail_api(
    log_util: LogUtil,
    flow_db: FlowDB
) -> APIRouter:
    router = APIRouter(
        prefix="/node-details",
        tags=["node-details"],
    )

    @router.get("/list")
    async def get_all_node_details(request: Request):
        """
        Get all node details
        """
        try:
            node_details = await flow_db.get_all_node_details()
            return node_details
        except Exception as e:
            log_util.error(service_name="NodeDetailAPI", message=f"Error getting node details: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/{node_id}")
    async def get_node_detail_by_id(request: Request, node_id: str):
        """
        Get node detail by node_id (e.g., "trigger-keyword", "message", etc.)
        """
        try:
            node_detail = await flow_db.get_node_detail_by_id(node_id)
            if node_detail is None:
                raise HTTPException(status_code=404, detail=f"Node detail not found for node_id: {node_id}")
            return node_detail
        except HTTPException:
            raise
        except Exception as e:
            log_util.error(service_name="NodeDetailAPI", message=f"Error getting node detail: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/category/{category}")
    async def get_node_details_by_category(request: Request, category: str):
        """
        Get node details by category (Trigger, Action, Condition, Delay)
        """
        try:
            valid_categories = ["Trigger", "Action", "Condition", "Delay"]
            if category not in valid_categories:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
                )
            
            node_details = await flow_db.get_node_details_by_category(category)
            return node_details
        except HTTPException:
            raise
        except Exception as e:
            log_util.error(service_name="NodeDetailAPI", message=f"Error getting node details by category: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router


