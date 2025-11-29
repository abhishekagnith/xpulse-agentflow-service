# UserStateService - User State Update Logic After Node Service Response

## Overview
When `is_validation_error = False`, UserStateService uses a new function `_handle_successful_node_processing()` to determine how to update the user state table.

---

## Logic Flow

### 1. If `is_validation_error = True`
**Action:** Update user state as is (direct update)
```python
# Update validation state
await self.flow_db.update_validation_state(...)

# Update user automation state
await self.flow_db.update_user_automation_state(
    is_in_automation=True,
    current_flow_id=flow_id,
    current_node_id=next_node_id
)
```

---

### 2. If `is_validation_error = False`
**Action:** Call `_handle_successful_node_processing()` function

#### Step 1: Check Node Type
- Get node detail from `node_details` DB using `node_type`
- Check if `user_input_required = True` OR `node_type == "delay"`

#### Step 2A: If User Input Type OR Delay Type
**Action:** Update user state DB
```python
# Update validation state (if validation_result provided)
if validation_result["status"] == "mismatch_retry":
    update_validation_state(validation_failed=True, ...)
else:
    update_validation_state(validation_failed=False, ...)

# Update user automation state
update_user_automation_state(
    is_in_automation=True,
    current_flow_id=flow_id,
    current_node_id=next_node_id
)
```

#### Step 2B: If NOT User Input Type AND NOT Delay Type
**Action:** Check if terminal node

##### 2B.1: If Terminal Node (No Outgoing Edges)
**Action:** Exit automation
```python
update_user_automation_state(
    is_in_automation=False,
    current_flow_id=None,
    current_node_id=None
)
```

##### 2B.2: If NOT Terminal Node (Has Outgoing Edges)
**Action:** Recursively call NodeIdentificationService
```python
# Call node service with processed node as current_node_id
node_service_response = await node_identification_service.identify_and_process_node(
    current_node_id=next_node_id,  # Use processed node
    node_id_to_process=None,
    is_validation_error=False,
    ...
)

# Handle response recursively:
# - If "internal_node": Process internal node, then recursively call _handle_successful_node_processing
# - If "success": Recursively call _handle_successful_node_processing with next_next_node_id
```

---

## Summary Table

| Condition | Node Type | Terminal? | Action |
|-----------|-----------|-----------|--------|
| `is_validation_error = True` | Any | N/A | Update state directly |
| `is_validation_error = False` | User Input OR Delay | N/A | Update state: `is_in_automation=True`, `current_node_id=next_node_id` |
| `is_validation_error = False` | Other | Yes (no edges) | Update state: `is_in_automation=False`, `current_flow_id=None`, `current_node_id=None` |
| `is_validation_error = False` | Other | No (has edges) | Recursively call node service, then `_handle_successful_node_processing` |

---

## Update Methods

### update_user_automation_state()
```python
{
    "is_in_automation": True/False,
    "current_flow_id": flow_id/None,
    "current_node_id": next_node_id/None
}
```

### update_validation_state()
```python
{
    "validation_failed": True/False,
    "failure_message": fallback_message/None
}
```

