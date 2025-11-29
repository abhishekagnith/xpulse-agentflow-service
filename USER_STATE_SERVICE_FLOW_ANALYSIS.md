# UserStateService Flow Analysis

## Current Flow vs Required Flow

### Required Flow:
1. Webhook received → `check_and_process_user_with_flow`
2. Check if in automation or not
   - **NOT in automation**: Create user → Call trigger service → Get trigger node ID and flow ID → Call node identification service
   - **IN automation**:
     - Check if delay type webhook → Process with next node identification
     - Otherwise: Check if current node has expected reply → Call reply validation service → Get validation state/message or node ID → Call node identification service

### Current Issues:
1. ❌ **Missing delay webhook check** - UserStateService doesn't check for `delay_complete` message_type
2. ❌ **Wrong parameters to NodeIdentificationService** - Currently passes flow, source_node_id, next_node_id, message_type, message_body, etc.
3. ❌ **Should pass metadata/data from webhook** - Currently passes raw message_body
4. ❌ **Missing is_validation_error flag** - Not explicitly passed
5. ❌ **Node ID parameter naming** - Uses `next_node_id` instead of `node_id_to_process`

### Required Parameters for NodeIdentificationService:
1. **metadata**: WebhookMetadata from saved webhook
2. **data**: Normalized data from saved webhook (Dict[str, Any])
3. **is_validation_error**: bool (True if validation failed, False otherwise)
4. **fallback_message**: Optional[str] (None if no validation error, otherwise the fallback message)
5. **node_id_to_process**: Optional[str] (If None, node service identifies next node, otherwise processes this node)
6. **current_node_id**: str (Current node ID from user state)

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Webhook Received → check_and_process_user_with_flow()     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │ User Exists?                          │
        └───────────────────────────────────────┘
                    │                    │
            NO      │                    │      YES
                    ▼                    ▼
    ┌───────────────────────┐  ┌──────────────────────┐
    │ Create User           │  │ Check is_in_automation│
    │ Call Trigger Service  │  └──────────────────────┘
    │ Get trigger_node_id   │              │
    │ Get flow_id           │      ┌───────┴───────┐
    │                       │      │               │
    │ Call Node Service     │   NO │               │ YES
    │ with:                 │      │               │
    │ - metadata            │      ▼               ▼
    │ - data                │ ┌──────────┐  ┌──────────────────┐
    │ - is_validation_error │ │ Check    │  │ Check message_type│
    │   = false             │ │ Triggers │  │ == "delay_complete"│
    │ - fallback_message    │ │          │  └──────────────────┘
    │   = null              │ │ Call      │         │
    │ - node_id_to_process  │ │ Trigger  │    YES  │  NO
    │   = trigger_node_id   │ │ Service  │         │
    │ - current_node_id     │ └──────────┘         │
    │   = null              │                      │
    └───────────────────────┘                      ▼
                                    ┌──────────────────────────────┐
                                    │ Check if current node has    │
                                    │ expected reply (button/list) │
                                    └──────────────────────────────┘
                                                │
                                        ┌───────┴───────┐
                                        │               │
                                    YES │               │ NO
                                        │               │
                                        ▼               ▼
                            ┌──────────────────┐  ┌──────────────┐
                            │ Call Reply       │  │ Call Node     │
                            │ Validation       │  │ Service with: │
                            │ Service          │  │ - metadata    │
                            │                  │  │ - data        │
                            │ Get:             │  │ - is_validation│
                            │ - status         │  │   _error=false│
                            │ - next_node_id   │  │ - fallback_msg│
                            │ - fallback_msg   │  │   =null       │
                            └──────────────────┘  │ - node_id_to_ │
                                        │         │   process=null │
                                        ▼         │ - current_node│
                            ┌──────────────────┐  │   _id         │
                            │ Based on status: │  └──────────────┘
                            │                  │
                            │ - matched:       │
                            │   node_id_to_    │
                            │   process =      │
                            │   next_node_id   │
                            │                  │
                            │ - mismatch_retry:│
                            │   is_validation_│
                            │   error = true   │
                            │   fallback_msg = │
                            │   message        │
                            │   node_id_to_    │
                            │   process =      │
                            │   current_node_id│
                            │                  │
                            │ - validation_exit│
                            │   (exit flow)    │
                            │                  │
                            │ - matched_other_│
                            │   node:          │
                            │   node_id_to_    │
                            │   process =      │
                            │   matched_node_id│
                            └──────────────────┘
                                        │
                                        ▼
                            ┌──────────────────────┐
                            │ Call Node Service    │
                            │ with:                │
                            │ - metadata           │
                            │ - data               │
                            │ - is_validation_error│
                            │ - fallback_message   │
                            │ - node_id_to_process │
                            │ - current_node_id    │
                            └──────────────────────┘
```

## Scenarios and Parameters

### Scenario 1: New User (Not in Automation) - Trigger Matched
**Parameters to NodeIdentificationService:**
- `metadata`: WebhookMetadata from saved webhook
- `data`: Normalized data from saved webhook
- `is_validation_error`: `False`
- `fallback_message`: `None`
- `node_id_to_process`: `trigger_node_id` (from trigger service)
- `current_node_id`: `None` (new user, no current node)

### Scenario 2: User in Automation - Delay Complete Webhook
**Parameters to NodeIdentificationService:**
- `metadata`: WebhookMetadata from saved webhook
- `data`: Normalized data from saved webhook (contains user_state_id)
- `is_validation_error`: `False`
- `fallback_message`: `None`
- `node_id_to_process`: `None` (node service identifies next node from delay node)
- `current_node_id`: `delay_node_id` (from user state)

### Scenario 3: User in Automation - Reply Matched Expected Answer
**Parameters to NodeIdentificationService:**
- `metadata`: WebhookMetadata from saved webhook
- `data`: Normalized data from saved webhook
- `is_validation_error`: `False`
- `fallback_message`: `None`
- `node_id_to_process`: `next_node_id` (from validation service)
- `current_node_id`: `current_node_id` (from user state)

### Scenario 4: User in Automation - Reply Mismatch (Validation Error)
**Parameters to NodeIdentificationService:**
- `metadata`: WebhookMetadata from saved webhook
- `data`: Normalized data from saved webhook
- `is_validation_error`: `True`
- `fallback_message`: `"This is not the valid response. Please try again below"` (from validation service)
- `node_id_to_process`: `current_node_id` (retry same node)
- `current_node_id`: `current_node_id` (from user state)

### Scenario 5: User in Automation - Reply Matched Other Node in Flow
**Parameters to NodeIdentificationService:**
- `metadata`: WebhookMetadata from saved webhook
- `data`: Normalized data from saved webhook
- `is_validation_error`: `False`
- `fallback_message`: `None`
- `node_id_to_process`: `matched_node_id` (from validation service)
- `current_node_id`: `current_node_id` (from user state)

### Scenario 6: User in Automation - No Expected Reply (Message/Question Node)
**Parameters to NodeIdentificationService:**
- `metadata`: WebhookMetadata from saved webhook
- `data`: Normalized data from saved webhook
- `is_validation_error`: `False`
- `fallback_message`: `None`
- `node_id_to_process`: `None` (node service identifies next node via default edge)
- `current_node_id`: `current_node_id` (from user state)

