# Complete Flow: Condition and Delay Node Processing

## Overview
This document covers the complete flow for how **Node Identification Service** processes condition and delay nodes, what it sends to **User State Service**, and how **User State Service** updates and processes these nodes.

---

## 1. CONDITION NODE FLOW

### 1.1 Node Identification Service Processing

#### Step 1: Identify Condition Node
- **Location**: `node_identification_service.py` - STEP 6.5
- **Trigger**: When `next_node_type == "condition"`
- **Action**: Calls `process_internal_node_service.process_internal_node()`

#### Step 2: Process Internal Node Service
- **Location**: `process_internal_node_service.py` - `_process_condition_node()`
- **Process**:
  1. Gets `flowNodeConditions` (list of conditions to evaluate)
  2. Gets `conditionResult` (array format: `[{"id":"...__true","nodeResultId":"..."},{"id":"...__false","nodeResultId":"..."}]`)
  3. Extracts `yResultNodeId` and `nResultNodeId` from array
  4. Gets user's flow context variables from database
  5. Evaluates each condition:
     - Gets variable name (removes `@` prefix)
     - Gets actual value from flow context
     - Compares with expected value based on condition type (Equal, NotEqual, Contains, GreaterThan, LessThan)
  6. Applies operator (AND/OR/None) to combine results
  7. Returns `processed_value`:
     - If condition is **TRUE** → `processed_value = yResultNodeId` (e.g., `"condition-node-xxx__true"`)
     - If condition is **FALSE** → `processed_value = nResultNodeId` (e.g., `"condition-node-xxx__false"`)

#### Step 3: Node Identification Service Response
- **Returns to User State Service**:
```python
{
    "status": "success",
    "message": "Condition node processed successfully",
    "next_node_id": "<condition_node_id>",  # e.g., "condition-node-xxx"
    "processed_value": "<yes_or_no_node_id>"  # e.g., "condition-node-xxx__true" or "condition-node-xxx__false"
}
```

---

### 1.2 User State Service Processing

#### Step 1: Receive Response
- **Location**: `user_state_service.py` - `_handle_successful_node_processing()`
- **Input**: 
  - `next_node_id` = condition node ID
  - `processed_value` = yes/no node ID

#### Step 2: Handle Condition Node
- **Location**: `user_state_service.py` - Lines 562-602
- **Process**:
  1. Detects `next_node_type == "condition"` and `processed_value` exists
  2. Uses `processed_value` (yes/no node ID) as `current_node_id` for recursive call
  3. Calls `node_identification_service.identify_and_process_node()` with:
     - `current_node_id = processed_value` (yes/no node ID)
     - `node_id_to_process = None`
  4. Node Identification Service finds edge with `source_node_id = processed_value`
  5. Gets next node from edge's `target_node_id`
  6. Recursively calls `_handle_successful_node_processing()` with the next node

#### Step 3: User State Update
- **Important**: Condition node does NOT update `current_node_id` in user state
- The recursive call processes the next node (from yes/no result) and updates user state accordingly
- If next node is:
  - **User input node** → Updates `current_node_id = next_node_id`
  - **Message node** → Processes recursively, may chain multiple message nodes
  - **Terminal node** → Exits automation (`is_in_automation = False`)
  - **Another condition/delay** → Processes recursively

---

## 2. DELAY NODE FLOW

### 2.1 Node Identification Service Processing

#### Step 1: Identify Delay Node
- **Location**: `node_identification_service.py` - STEP 6.5
- **Trigger**: When `next_node_type == "delay"`
- **Action**: Calls `process_internal_node_service.process_internal_node()`

#### Step 2: Process Internal Node Service
- **Location**: `process_internal_node_service.py` - `_process_delay_node()`
- **Process**:
  1. Gets `delayDuration` and `delayUnit` from node data
  2. Calculates `wait_time_seconds`:
     - `seconds` → `wait_time_seconds = delayDuration`
     - `minutes` → `wait_time_seconds = delayDuration * 60`
     - `hours` → `wait_time_seconds = delayDuration * 3600`
     - `days` → `wait_time_seconds = delayDuration * 86400`
  3. Gets `waitForReply` (not currently used in processing)
  4. Returns `processed_value`:
```python
{
    "delay_duration": 1,
    "delay_unit": "minutes",
    "wait_time_seconds": 60,
    "wait_for_reply": False
}
```

#### Step 3: Node Identification Service Response
- **Returns to User State Service**:
```python
{
    "status": "success",
    "message": "Delay node processed successfully",
    "next_node_id": "<delay_node_id>",  # e.g., "delay-node-xxx"
    "processed_value": {
        "delay_duration": 1,
        "delay_unit": "minutes",
        "wait_time_seconds": 60,
        "wait_for_reply": False
    }
}
```

---

### 2.2 User State Service Processing

#### Step 1: Receive Response
- **Location**: `user_state_service.py` - `_handle_successful_node_processing()`
- **Input**: 
  - `next_node_id` = delay node ID
  - `processed_value` = delay info dict

#### Step 2: Handle Delay Node
- **Location**: `user_state_service.py` - Lines 604-621
- **Process**:
  1. Detects `next_node_type == "delay"` and `processed_value` exists
  2. Calls `_update_delay_node_state()` with:
     - `next_node_id` = delay node ID
     - `next_node_data` = complete delay node object
     - `clear_delay_data = False`

#### Step 3: Update Delay Node State
- **Location**: `user_state_service.py` - `_update_delay_node_state()`
- **Process**:
  1. Converts delay node data to dict
  2. Updates user automation state:
     - `is_in_automation = True`
     - `current_flow_id = flow_id`
     - `current_node_id = None` ⚠️ **DOES NOT UPDATE** (keeps previous node ID)
     - `delay_node_data = <complete_delay_node_object>`
  3. Saves delay record to `delays` collection:
     - `delay_started_at = now()`
     - `delay_completes_at = delay_started_at + wait_time_seconds`
     - `processed = False`
  4. Returns success response

#### Step 4: User State After Delay Node
- **User State**:
  - `is_in_automation = True`
  - `current_flow_id = <flow_id>`
  - `current_node_id = <previous_node_id>` (NOT updated to delay node)
  - `delay_node_data = {complete delay node object}`

---

## 3. DELAY COMPLETE WEBHOOK FLOW

### 3.1 Delay Scheduler Service
- **Location**: `delay_scheduler_service.py`
- **Process**:
  1. Background scheduler runs every 20 seconds
  2. Queries `delays` collection for expired delays:
     - `processed = False`
     - `delay_completes_at <= now()`
  3. For each expired delay:
     - Gets user data
     - Creates `delay_complete` webhook request
     - Sends to `webhook_service.process_webhook_message()`
     - Marks delay as `processed = True`

### 3.2 User State Service - Delay Complete Handler
- **Location**: `user_state_service.py` - Lines 1017-1130
- **Trigger**: When `message_type == "delay_complete"`

#### Step 1: Extract Not Interrupted Node ID
- Gets `delay_node_data` from user state
- Extracts `delayResult` (array format)
- Finds item with `"__not_interrupted"` in `id`
- Gets `nodeResultId` → `current_node_id_for_delay`

#### Step 2: Process Next Node
- Calls `node_identification_service.identify_and_process_node()` with:
  - `current_node_id = notInterruptedNodeId`
  - `node_id_to_process = None`

#### Step 3: Handle Next Node Processing
- If node service returns success:
  - Gets `next_node_id` from response
  - Calls `_handle_successful_node_processing()` with next node
  - Updates user state based on next node type

#### Step 4: Clear Delay Data
- After successful next node processing:
  - Calls `_update_delay_node_state(clear_delay_data=True)`
  - Removes `delay_node_data` from user state
  - Keeps `current_node_id` as updated by next node processing

---

## 4. DELAY INTERRUPT SCENARIOS

### 4.1 Delay Interrupt Enabled (`delayInterrupt = true`)

#### Scenario: User Sends Message During Delay
- **Current Behavior**: Not yet implemented
- **Expected Behavior**:
  1. User sends message while delay is active
  2. User State Service should check if user has `delay_node_data`
  3. If `delayInterrupt = true`:
     - Extract `interruptedNodeId` from `delayResult`
     - Process next node using `interruptedNodeId`
     - Clear `delay_node_data`
     - Cancel delay record in `delays` collection
  4. If `delayInterrupt = false`:
     - Ignore user message (delay continues)

#### Delay Result Structure (Array Format):
```json
[
  {
    "id": "delay-node-xxx__interrupted",
    "expectedInput": "Interrupted",
    "isDefault": false,
    "nodeResultId": "message-node-interrupted-path"
  },
  {
    "id": "delay-node-xxx__not_interrupted",
    "expectedInput": "Not Interrupted",
    "isDefault": false,
    "nodeResultId": "message-node-not-interrupted-path"
  }
]
```

### 4.2 Delay Interrupt Disabled (`delayInterrupt = false`)

#### Scenario: User Sends Message During Delay
- **Current Behavior**: User message is processed normally
- **Expected Behavior**:
  1. User sends message while delay is active
  2. User State Service checks if user has `delay_node_data`
  3. If `delayInterrupt = false`:
     - Ignore user message
     - Delay continues until `delay_completes_at`
  4. When delay expires:
     - Process `notInterruptedNodeId` path
     - Clear `delay_node_data`

---

## 5. SUMMARY TABLE

| Node Type | Node ID Service Returns | User State Updates | Current Node ID | Delay Node Data |
|-----------|------------------------|-------------------|-----------------|-----------------|
| **Condition** | `next_node_id` = condition node ID<br>`processed_value` = yes/no node ID | Recursively processes next node from yes/no result | Updated to next node (from yes/no result) | Not applicable |
| **Delay** | `next_node_id` = delay node ID<br>`processed_value` = delay info dict | Saves complete delay node to `delay_node_data` | **NOT UPDATED** (keeps previous) | Saved with complete delay node object |
| **Delay Complete** | `next_node_id` = next node ID<br>`processed_value` = (varies) | Updates based on next node type | Updated to next node | **CLEARED** after processing |

---

## 6. KEY POINTS

### Condition Node:
- ✅ Evaluates conditions using flow context variables
- ✅ Returns yes/no node ID as `processed_value`
- ✅ Recursively processes next node from yes/no result
- ✅ Does NOT update `current_node_id` to condition node itself

### Delay Node:
- ✅ Calculates wait time in seconds
- ✅ Saves complete delay node object to user state
- ✅ **DOES NOT** update `current_node_id` (keeps previous node)
- ✅ Saves delay record for background scheduler
- ✅ Background scheduler triggers `delay_complete` webhook when time expires

### Delay Complete:
- ✅ Extracts `notInterruptedNodeId` from `delayResult` array
- ✅ Processes next node using `notInterruptedNodeId`
- ✅ Clears `delay_node_data` after successful processing
- ✅ Updates `current_node_id` based on next node type

### Delay Interrupt (Not Yet Implemented):
- ⚠️ Should check `delayInterrupt` flag when user sends message during delay
- ⚠️ Should use `interruptedNodeId` if interrupt enabled
- ⚠️ Should ignore message if interrupt disabled

---

## 7. DATA STRUCTURES

### Condition Result (Array Format):
```json
[
  {
    "id": "condition-node-xxx__true",
    "expectedInput": "True",
    "isDefault": false,
    "nodeResultId": "message-node-yes-path"
  },
  {
    "id": "condition-node-xxx__false",
    "expectedInput": "False",
    "isDefault": false,
    "nodeResultId": "delay-node-no-path"
  }
]
```

### Delay Result (Array Format):
```json
[
  {
    "id": "delay-node-xxx__interrupted",
    "expectedInput": "Interrupted",
    "isDefault": false,
    "nodeResultId": "message-node-interrupted-path"
  },
  {
    "id": "delay-node-xxx__not_interrupted",
    "expectedInput": "Not Interrupted",
    "isDefault": false,
    "nodeResultId": "message-node-not-interrupted-path"
  }
]
```

### Delay Node Data (Saved in User State):
```json
{
  "id": "delay-node-xxx",
  "type": "delay",
  "delayDuration": 1,
  "delayUnit": "minutes",
  "delayInterrupt": true,
  "waitForReply": false,
  "delayResult": [
    {
      "id": "delay-node-xxx__interrupted",
      "nodeResultId": "message-node-interrupted"
    },
    {
      "id": "delay-node-xxx__not_interrupted",
      "nodeResultId": "message-node-not-interrupted"
    }
  ]
}
```

---

## 8. FLOW DIAGRAMS

### Condition Node Flow:
```
Node Identification Service
  ↓ (finds condition node)
Process Internal Node Service
  ↓ (evaluates conditions)
Returns: {next_node_id: "condition-node-xxx", processed_value: "condition-node-xxx__true"}
  ↓
User State Service
  ↓ (detects condition node)
Recursive Call: node_identification_service(current_node_id = "condition-node-xxx__true")
  ↓ (finds edge, gets next node)
Process Next Node
  ↓
Update User State (current_node_id = next_node_id)
```

### Delay Node Flow:
```
Node Identification Service
  ↓ (finds delay node)
Process Internal Node Service
  ↓ (calculates wait time)
Returns: {next_node_id: "delay-node-xxx", processed_value: {delay_info}}
  ↓
User State Service
  ↓ (detects delay node)
Update Delay Node State
  ↓
Save to User State:
  - delay_node_data = {complete delay node}
  - current_node_id = NOT UPDATED (keeps previous)
  ↓
Save Delay Record to delays collection
  ↓
Background Scheduler (every 20 seconds)
  ↓ (checks expired delays)
Send delay_complete webhook
  ↓
User State Service (delay_complete handler)
  ↓ (extracts notInterruptedNodeId)
Process Next Node
  ↓
Clear delay_node_data
  ↓
Update User State (current_node_id = next_node_id)
```

---

## 9. EDGE CASES AND NOTES

1. **Condition Node with Missing Context Variables**: Returns `nResultNodeId` (false path) if variable not found
2. **Delay Node with Invalid Duration**: Uses default 0 seconds if invalid
3. **Delay Complete with Missing delay_node_data**: Returns error, does not process
4. **Delay Complete with Missing notInterruptedNodeId**: Returns error, does not process
5. **Multiple Sequential Condition Nodes**: Each processes recursively
6. **Condition Node Leading to Delay Node**: Delay node is processed after condition evaluation
7. **Delay Node Leading to Condition Node**: Condition node is processed after delay completes

---

## 10. FUTURE ENHANCEMENTS

1. **Delay Interrupt Implementation**: 
   - Check `delayInterrupt` flag when user sends message during delay
   - Use `interruptedNodeId` if interrupt enabled
   - Cancel delay record if interrupted

2. **Wait For Reply**:
   - Currently `waitForReply` is stored but not used
   - Could be used to determine if delay should wait for user reply before proceeding

3. **Delay Node Current Node ID**:
   - Currently `current_node_id` is NOT updated when delay node is processed
   - Consider if this should be updated to delay node ID for tracking purposes

