# Migration Guide: WhatsApp Service → Flow Service

## Overview
This guide explains how the Flow Service was extracted from the WhatsApp Service and how to complete the migration.

## File Movements

### From WhatsApp Service → Flow Service

| Original File (xpulse-whatsapp-service) | New File (flow_service) | Status |
|----------------------------------------|-------------------------|--------|
| `src/services/whatsapp_flow_service.py` | `src/services/flow_service.py` | ✅ Copied |
| `src/services/whatsapp_user_state_service.py` | `src/services/user_state_service.py` | ✅ Copied |
| `src/apis/whatsapp_flow_api.py` | `src/apis/flow_api.py` | ✅ Copied |
| `src/models/whatsapp_flow_data.py` | `src/models/flow_data.py` | ✅ Copied & Renamed |
| `src/models/whatsapp_flow_node_data.py` | `src/models/flow_node_data.py` | ✅ Copied |
| `src/models/whatsapp_flow_edge_data.py` | `src/models/flow_edge_data.py` | ✅ Copied |
| `src/models/whatsapp_flow_trigger_data.py` | `src/models/flow_trigger_data.py` | ✅ Copied |
| `src/models/whatsapp_user_data.py` | `src/models/user_data.py` | ✅ Copied & Renamed |
| `src/models/whatsapp_flow_user_context.py` | `src/models/flow_user_context.py` | ✅ Copied & Renamed |
| `src/database/whatsapp_db.py` (flow methods only) | `src/database/flow_db.py` | ✅ Created new simplified version |

## Changes Made

### 1. Model Renaming
- `WhatsAppFlowData` → `FlowData`
- `WhatsAppFlowUserContext` → `FlowUserContext`
- `WhatsAppUserData` → `UserData`

### 2. Database Simplification
Created `FlowDB` class with only flow-related operations:
- Removed WhatsApp-specific collections (templates, messages, webhooks, etc.)
- Kept only: flows, flow_nodes, flow_edges, flow_triggers, users, flow_user_context
- Changed database name from `whatsapp_db` to `flow_db`

### 3. New Utilities Created
- `log_utils.py` - Loki logging (adapted for flow_service)
- `environment_utils.py` - Environment config (simplified for flow service)
- `flow_exception.py` - Flow-specific exceptions

### 4. Main Application
Created new `main.py` with:
- FastAPI application setup
- Flow service initialization
- API routing
- Health check endpoint

## Pending Tasks (To Make it Functional)

### Critical: Update Imports in Copied Files

#### 1. **flow_service.py** (Highest Priority)
```python
# Current (WhatsApp Service)
from utils.log_utils import LogUtil
from utils.environment_utils import EnvironmentUtils
from database.whatsapp_db import WhatsAppDB
from services.internal.user_service import UserService
from services.internal.brand_service import BrandService
from models.whatsapp_flow_data import WhatsAppFlowData
from models.whatsapp_flow_trigger_data import WhatsAppFlowTriggerData
from exceptions.whatsapp_exception import WhatsAppFlowException

class WhatsAppFlowService:
    def __init__(self, log_util, environment_utils, whatsapp_db, user_service, brand_service):
        # ...

# Needs to become (Flow Service)
from utils.log_utils import LogUtil
from utils.environment_utils import EnvironmentUtils
from database.flow_db import FlowDB
from models.flow_data import FlowData
from models.flow_trigger_data import FlowTriggerData
from exceptions.flow_exception import FlowServiceException

class FlowService:
    def __init__(self, log_util, environment_utils, flow_db):
        # Remove user_service and brand_service OR create stubs
        # ...
```

**Action Items:**
- [ ] Rename class `WhatsAppFlowService` → `FlowService`
- [ ] Update all imports to use flow_service models
- [ ] Change `whatsapp_db` to `flow_db`
- [ ] Remove or stub `user_service` and `brand_service` dependencies
- [ ] Update exception imports

#### 2. **user_state_service.py**
```python
# Current
from database.whatsapp_db import WhatsAppDB
from services.whatsapp_flow_service import WhatsAppFlowService
from services.whatsapp_node_process_service import WhatsAppNodeProcessService
from models.whatsapp_user_data import WhatsAppUserData
from models.whatsapp_flow_data import WhatsAppFlowData

class WhatsAppUserStateService:
    def __init__(self, log_util, whatsapp_db, whatsapp_flow_service, whatsapp_node_process_service):
        # ...

# Needs to become
from database.flow_db import FlowDB
from services.flow_service import FlowService
# Note: WhatsAppNodeProcessService might need to stay in WhatsApp service
# or be refactored into a channel-agnostic interface
from models.user_data import UserData
from models.flow_data import FlowData

class UserStateService:
    def __init__(self, log_util, flow_db, flow_service, node_process_service=None):
        # ...
```

**Action Items:**
- [ ] Rename class `WhatsAppUserStateService` → `UserStateService`
- [ ] Update all imports
- [ ] Change `whatsapp_db` to `flow_db`
- [ ] Decide how to handle `WhatsAppNodeProcessService` dependency
  - Option A: Keep it as optional parameter
  - Option B: Create generic `NodeProcessService` interface
  - Option C: Move node processing logic here

#### 3. **flow_api.py**
```python
# Current
from services.whatsapp_flow_service import WhatsAppFlowService
from exceptions.whatsapp_exception import WhatsAppFlowException

def create_whatsapp_flow_api(log_util, whatsapp_flow_service):
    # ...

# Needs to become
from services.flow_service import FlowService
from exceptions.flow_exception import FlowServiceException

def create_flow_api(log_util, flow_service):
    # ...
```

**Action Items:**
- [ ] Rename function `create_whatsapp_flow_api` → `create_flow_api`
- [ ] Update parameter name `whatsapp_flow_service` → `flow_service`
- [ ] Update exception imports
- [ ] Update all references in function body

### Optional: Handle Internal Service Dependencies

#### Option A: Create Stub Services
Create minimal versions of `UserService` and `BrandService` in flow_service:

```
flow_service/src/services/internal/
├── __init__.py
├── user_service.py       # Stub or API client to main platform
└── brand_service.py      # Stub or API client to main platform
```

#### Option B: Make Them Optional
Modify `FlowService` to work without these dependencies:
```python
class FlowService:
    def __init__(self, log_util, environment_utils, flow_db, 
                 user_service=None, brand_service=None):
        self.user_service = user_service
        self.brand_service = brand_service
        # Add checks before using these services
```

#### Option C: Use API Calls
Instead of importing services, make HTTP calls to the main platform:
```python
async def get_user_info(self, user_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{PLATFORM_URL}/users/{user_id}")
        return response.json()
```

## Database Migration Strategy

### Option 1: Shared Database (Recommended for Start)
- Both services use same MongoDB instance
- WhatsApp service: `whatsapp_db` database
- Flow service: `flow_db` database
- Share user state via flow_db.users collection

### Option 2: Separate Databases
- Complete data separation
- Requires synchronization mechanism
- More complex but better isolation

### Option 3: Hybrid (Best Long-term)
- Flow service has its own database for flow definitions
- Shared database for user state and context
- Channel services (WhatsApp, Email, etc.) have their own databases

## API Integration

### WhatsApp Service Calling Flow Service

```python
# In WhatsApp Service
import httpx

class WhatsAppWebhookService:
    async def process_flow(self, user_input, user_id, brand_id):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://flow-service:8018/flow/process",
                json={
                    "user_id": user_id,
                    "brand_id": brand_id,
                    "user_input": user_input,
                    "channel": "whatsapp"
                }
            )
            return response.json()
```

### Flow Service Calling Back to WhatsApp Service

```python
# In Flow Service
async def send_message_via_channel(self, channel: str, recipient: str, message: dict):
    if channel == "whatsapp":
        async with httpx.AsyncClient() as client:
            await client.post(
                "http://whatsapp-service:8017/message/send",
                json={
                    "recipient": recipient,
                    "message": message
                }
            )
```

## Testing the Migration

### 1. Start Both Services
```bash
# Terminal 1: WhatsApp Service
cd xpulse-whatsapp-service
python src/main.py

# Terminal 2: Flow Service
cd flow_service
python src/main.py
```

### 2. Test Flow Service Health
```bash
curl http://localhost:8018/health
```

### 3. Test Flow Creation
```bash
curl -X POST http://localhost:8018/flow/create \
  -H "Content-Type: application/json" \
  -H "x-user-id: 1" \
  -d '{
    "name": "Test Flow",
    "flowNodes": [],
    "flowEdges": []
  }'
```

### 4. Test Flow List
```bash
curl http://localhost:8018/flow/list \
  -H "x-user-id: 1"
```

## Rollback Plan

If issues occur:
1. The original files in WhatsApp service are untouched
2. Simply stop the flow_service
3. WhatsApp service continues to work as before
4. Delete `flow_service/` directory if needed

## Success Criteria

✅ Flow service starts without errors
✅ Health check returns 200
✅ Can create a flow via API
✅ Can list flows via API
✅ No import errors in any file
✅ Database connections work
✅ Logging works (check Loki)

## Timeline Recommendation

1. **Phase 1 (Day 1)**: Fix imports, remove WhatsApp dependencies
2. **Phase 2 (Day 2)**: Test basic CRUD operations
3. **Phase 3 (Day 3)**: Integrate with WhatsApp service via API calls
4. **Phase 4 (Week 2)**: Refactor node processing to be channel-agnostic
5. **Phase 5 (Week 3)**: Add support for second channel (Email/SMS)

## Notes

- Original WhatsApp service files are **NOT MODIFIED** yet
- All changes are in the new `flow_service` directory
- This is a safe, reversible migration
- Can run both services simultaneously during transition

