import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

# Utils
from utils.log_utils import LogUtil
from utils.environment_utils import EnvironmentUtils

# Database
from database.flow_db import FlowDB

# Internal Services (for multitenancy)
from services.internal.user_service import UserService
from services.internal.brand_service import BrandService

# Services
from services.flow_service import FlowService
from services.user_state_service import UserStateService
from services.webhook_service import WebhookService
from services.trigger_identification_service import TriggerIdentificationService
from services.time_triggered_automation_service import TimeTriggeredAutomationService
from services.reply_validation_service import ReplyValidationService
from services.node_identification_service import NodeIdentificationService
from services.whatsapp_flow_service import WhatsAppFlowService

# APIs
from apis.flow_api import create_flow_api
from apis.webhook_message_api import create_webhook_message_api
from apis.node_detail_api import create_node_detail_api

# Utils
log_util = LogUtil()
environment_utils = EnvironmentUtils(log_util=log_util)

# Database
flow_db = FlowDB(log_util=log_util, environment_utils=environment_utils)

# Internal Services (for multitenancy validation)
user_service = UserService(log_util=log_util)
brand_service = BrandService(log_util=log_util)

# Services
flow_service = FlowService(
    log_util=log_util,
    environment_utils=environment_utils,
    flow_db=flow_db,
    user_service=user_service,
    brand_service=brand_service
)

# Initialize ReplyValidationService
reply_validation_service = ReplyValidationService(
    log_util=log_util,
    flow_db=flow_db
)

# Initialize WhatsAppFlowService
whatsapp_flow_service = WhatsAppFlowService(
    log_util=log_util,
    flow_db=flow_db,
    node_process_api_url=None  # Will be set from environment if needed
)

# Initialize ProcessInternalNodeService
from services.process_internal_node_service import ProcessInternalNodeService
process_internal_node_service = ProcessInternalNodeService(
    log_util=log_util,
    flow_db=flow_db
)

# Initialize UserTransactionService
from services.user_transaction_service import UserTransactionService
user_transaction_service = UserTransactionService(
    log_util=log_util,
    flow_db=flow_db
)

# Initialize NodeIdentificationService
node_identification_service = NodeIdentificationService(
    log_util=log_util,
    flow_db=flow_db,
    whatsapp_flow_service=whatsapp_flow_service,
    process_internal_node_service=process_internal_node_service,
    user_transaction_service=user_transaction_service
)

user_state_service = UserStateService(
    log_util=log_util,
    flow_db=flow_db,
    flow_service=flow_service,
    node_identification_service=node_identification_service,
    reply_validation_service=reply_validation_service
)

trigger_identification_service = TriggerIdentificationService(
    log_util=log_util,
    flow_db=flow_db,
    flow_service=flow_service,
    user_state_service=user_state_service
)

# Set trigger service in user state service
user_state_service.set_trigger_identification_service(trigger_identification_service)

# Time-triggered automation service for scheduled triggers
time_triggered_automation_service = TimeTriggeredAutomationService(
    log_util=log_util,
    flow_db=flow_db
)

webhook_service = WebhookService(
    log_util=log_util,
    flow_db=flow_db,
    user_state_service=user_state_service,
    time_triggered_automation_service=time_triggered_automation_service
)

# Initialize Delay Scheduler Service
from services.delay_scheduler_service import DelaySchedulerService
delay_scheduler_service = DelaySchedulerService(
    log_util=log_util,
    flow_db=flow_db,
    webhook_service=webhook_service,
    check_interval_seconds=20  # Check every 20 seconds
)

# Define lifespan function
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log_util.info(service_name="FlowService", message="Application startup complete")
    
    # Start delay scheduler
    await delay_scheduler_service.start()
    log_util.info(service_name="FlowService", message="Delay scheduler started")
    
    yield
    
    # Shutdown
    # Stop delay scheduler
    await delay_scheduler_service.stop()
    log_util.info(service_name="FlowService", message="Delay scheduler stopped")
    
    flow_db.close()
    log_util.info(service_name="FlowService", message="Application shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="xpulse flow service",
    description="Generic flow automation service for multi-channel messaging",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# APIs
from apis.flow_api import create_flow_api
from apis.node_process_api import create_node_process_api

# Flow management APIs
flow_api_router = create_flow_api(
    log_util=log_util,
    flow_service=flow_service
)
app.include_router(flow_api_router)

# Node processing API (routes to channel services)
node_process_router = create_node_process_api(log_util=log_util)
app.include_router(node_process_router)

# Webhook message API (receives messages from channel services)
webhook_message_router = create_webhook_message_api(
    log_util=log_util,
    webhook_service=webhook_service
)
app.include_router(webhook_message_router)

# Node details API
node_detail_router = create_node_detail_api(
    log_util=log_util,
    flow_db=flow_db
)
app.include_router(node_detail_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "flow_service"}

# Global exception handler for HTTPExceptions
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    log_util.error(service_name="FlowService", message=f"HTTPException: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error": str(exc),
            "status_code": exc.status_code
        },
        headers={"Content-Type": "application/json"}
    )

# Global exception handler for any unhandled exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    log_util.error(service_name="FlowService", message=f"Exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc),
            "status_code": 500
        },
        headers={"Content-Type": "application/json"}
    )

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=environment_utils.get_env_variable("HOST"),
        port=environment_utils.get_env_variable("PORT")
    )

