# UserStateService ↔ ReplyValidationService Interaction (Updated)

## Overview
This document describes the updated interaction between `UserStateService` and `ReplyValidationService` after implementing all the requested changes.

---

## When UserStateService Calls ReplyValidationService

### Scenario
- **User is in automation** (`is_in_automation = True`)
- **Current node expects a reply** (determined from `node_details` database collection using `user_input_required` field)
- **Webhook is NOT a `delay_complete` type**
- **User reply is extracted** from webhook data

### How UserStateService Determines if Node Expects Reply

1. Gets `node_type` from current node in flow
2. Queries `node_details` collection using `get_node_detail_by_id(node_type)`
3. Checks `node_detail.user_input_required` field
4. Also checks if `node_type == "question"` (text question) to set `is_text` flag

```python
# Get node detail from database
node_detail = await self.flow_db.get_node_detail_by_id(node_type)
has_expected_reply = False
is_text = False

if node_detail:
    has_expected_reply = node_detail.user_input_required
    is_text = (node_type == "question")  # Text question type
```

---

## Method Called

```python
# Get current validation count from user state
current_validation_count = 0
if existing_user.validation:
    if isinstance(existing_user.validation, dict):
        current_validation_count = existing_user.validation.get("failure_count", 0)
    else:
        current_validation_count = existing_user.validation.failure_count if hasattr(existing_user.validation, "failure_count") else 0

validation_result = await self.reply_validation_service.validate_and_match_reply(
    metadata=metadata,                    # WebhookMetadata - Complete metadata object
    data=data,                            # Dict[str, Any] - Complete data object (contains user_reply)
    current_node_id=existing_user.current_node_id,  # str - Current node ID from user state
    flow_id=flow.id,                      # str - Flow ID from user state
    is_text=is_text,                      # bool - True if node_type is "question" (text question)
    current_validation_count=current_validation_count  # int - Current validation failure count from user state
)
```

### Parameters Sent

1. **`metadata`** (WebhookMetadata): Complete metadata object from webhook
   - Contains: `sender`, `brand_id`, `user_id`, `channel`, `channel_identifier`, `message_type`, `status`

2. **`data`** (Dict[str, Any]): Complete data object from webhook
   - Contains: `user_reply`, `media_url`, `media_type`, etc.

3. **`current_node_id`** (str): Current node ID from user state

4. **`flow_id`** (str): Flow ID from user state

5. **`is_text`** (bool): 
   - `True` if `node_type == "question"` (text question)
   - `False` otherwise
   - When `True`, validation service skips checking expected answers in flow

6. **`current_validation_count`** (int): 
   - Current validation failure count from user state (`existing_user.validation.failure_count`)
   - Used by validation service to check if limit exceeded

---

## What ReplyValidationService Returns

### Response Format

```python
{
    "status": str,                    # Status type (see below)
    "matched_answer_id": Optional[str], # Answer ID if matched in current node
    "matched_node_id": Optional[str],   # Node ID if matched in another node
    "fallback_message": Optional[str],   # Fallback message for validation failures
    "message": Optional[str]            # Error message if status is "error"
}
```

**Note:** `next_node_id` is **NOT** in the response format anymore.

### Possible Status Values and Responses

#### 1. `status: "matched"` - Reply matched expected answer in current node
```python
{
    "status": "matched",
    "matched_answer_id": "button_question-node-xxx_btn_yyy",
    "matched_node_id": None,
    "fallback_message": None
}
```
**Action:** UserStateService uses `matched_answer_id` as `current_node_id` when calling NodeIdentificationService

#### 2. `status: "matched_other_node"` - Reply matched another node in the flow
```python
{
    "status": "matched_other_node",
    "matched_node_id": "button_question-node-zzz",
    "matched_answer_id": None,
    "fallback_message": None
}
```
**Action:** UserStateService calls NodeIdentificationService with `node_id_to_process = matched_node_id`

#### 3. `status: "mismatch_retry"` - Reply didn't match, retry with fallback
```python
{
    "status": "mismatch_retry",
    "matched_answer_id": None,
    "matched_node_id": None,
    "fallback_message": "I'm afraid I didn't understand, could you try again, please?"
}
```
**Action:** UserStateService calls NodeIdentificationService with:
- `is_validation_error = True`
- `fallback_message` from response
- `node_id_to_process = current_node_id` (retry same node)

#### 4. `status: "validation_exit"` - Validation limit exceeded
```python
{
    "status": "validation_exit",
    "message": "Validation limit exceeded, automation exited",
    "matched_answer_id": None,
    "matched_node_id": None,
    "fallback_message": "..."  # Fallback message from node
}
```
**Action:** UserStateService calls NodeIdentificationService with validation error:
- Calls node service with: `is_validation_error = True`, `fallback_message` from node, `node_id_to_process = None`, `current_node_id = current_node_id`
- After successful node service response, exits automation:
  - Updates user state: `is_in_automation = False`, `current_flow_id = None`, `current_node_id = None`
  - Resets validation state: `validation_failed = False`, `failure_message = None`

#### 5. `status: "use_default_edge"` - Use default edge (for non-button/list nodes)
```python
{
    "status": "use_default_edge",
    "matched_answer_id": None,
    "matched_node_id": None,
    "fallback_message": None
}
```
**Action:** UserStateService calls NodeIdentificationService with `node_id_to_process = None` (uses default edge)

#### 6. `status: "error"` - Error occurred
```python
{
    "status": "error",
    "message": "Flow not found" | "User not found" | etc.,
    "matched_answer_id": None,
    "matched_node_id": None,
    "fallback_message": None
}
```
**Action:** UserStateService logs error and returns early

---

## What UserStateService Does After Receiving Response

### Flow Based on Status

#### 1. `status == "matched"`:
```python
# Use matched_answer_id as current_node_id for flow service
current_node_id_for_service = matched_answer_id  # Use as current_node_id

# Call NodeIdentificationService with:
# - current_node_id = matched_answer_id (not original current_node_id)
# - node_id_to_process = None
# - is_validation_error = False
# - fallback_message = None
```

#### 2. `status == "matched_other_node"`:
```python
# Call NodeIdentificationService with:
# - node_id_to_process = matched_node_id (process the matched node)
# - is_validation_error = False
# - fallback_message = None
```

#### 3. `status == "mismatch_retry"`:
```python
# Call NodeIdentificationService with:
# - node_id_to_process = current_node_id (retry same node)
# - is_validation_error = True
# - fallback_message = validation_result.get("fallback_message")
```

#### 4. `status == "validation_exit"`:
```python
# Get fallback message from validation result
fallback_message = validation_result.get("fallback_message")

# Call NodeIdentificationService with validation error
node_service_response = await self.node_identification_service.identify_and_process_node(
    metadata=metadata,
    data=data,
    is_validation_error=True,
    fallback_message=fallback_message,
    node_id_to_process=None,  # Blank - no specific node to process
    current_node_id=existing_user.current_node_id,
    flow_id=flow.id,
    ...
)

# After successful node service response, exit automation
if node_service_response.get("status") == "success":
    # Exit automation - update user state
    await self.flow_db.update_user_automation_state(
        is_in_automation=False,
        current_flow_id=None,
        current_node_id=None
    )
    # Reset validation state
    await self.flow_db.update_validation_state(
        validation_failed=False,
        failure_message=None
    )
return
```

#### 5. `status == "use_default_edge"`:
```python
# Call NodeIdentificationService with:
# - node_id_to_process = None (uses default edge)
# - is_validation_error = False
# - fallback_message = None
```

#### 6. `status == "error"`:
```python
# Log error and return early
return
```

### After Calling NodeIdentificationService

UserStateService:
1. **Waits for node service response**
2. **Updates validation state** (only after successful node processing):
   - If `status == "mismatch_retry"`: Increment validation count
   - Otherwise: Reset validation count
3. **Updates user automation state** with `next_node_id` from node service response
4. **Returns status to WebhookService**

---

## Key Changes from Previous Version

### 1. Node Details from Database
- ✅ Uses `node_details` collection to check if node expects reply
- ✅ Checks `user_input_required` field instead of hardcoded list
- ✅ Identifies "question" type from database (text value)

### 2. is_text Flag
- ✅ Sends `is_text` flag to validation service
- ✅ When `is_text = True`, validation service skips checking expected answers in flow

### 3. Parameters Changed
- ✅ Sends `metadata` and `data` objects instead of individual parameters
- ✅ Validation service extracts `user_reply` from `data` internally

### 4. Response Format
- ✅ **Removed** `next_node_id` from response format
- ✅ Response only contains: `status`, `matched_answer_id`, `matched_node_id`, `fallback_message`, `message`

### 5. Matched Status Handling
- ✅ For `status == "matched"`: Uses `matched_answer_id` as `current_node_id` when calling NodeIdentificationService
- ✅ **Removed** extra `matched_answer_id` field from data sent to node service

### 6. User State Updates
- ✅ **ReplyValidationService does NOT update any user state**
- ✅ **All user state updates are done by UserStateService**:
  - After successful node service response
  - For validation_exit status
  - Validation state updates (increment/reset) after node service success

---

## Summary Table

| Status | Meaning | UserStateService Action | Parameters to Node Service |
|--------|---------|------------------------|---------------------------|
| `matched` | Reply matched current node | Use `matched_answer_id` as `current_node_id` | `current_node_id = matched_answer_id`, `node_id_to_process = None`, `is_validation_error = False` |
| `matched_other_node` | Reply matched another node | Use `matched_node_id` | `node_id_to_process = matched_node_id`, `is_validation_error = False` |
| `mismatch_retry` | No match, retry with fallback | Retry same node | `node_id_to_process = current_node_id`, `is_validation_error = True`, `fallback_message` |
| `validation_exit` | Validation limit exceeded | Call node service with validation error, then exit automation | `is_validation_error = True`, `fallback_message`, `node_id_to_process = None`, `current_node_id = current_node_id` |
| `use_default_edge` | Use default edge | Use default edge | `node_id_to_process = None`, `is_validation_error = False` |
| `error` | Error occurred | Log and return | No node service call |

---

## Important Notes

1. **Only called when:** User is in automation AND current node has expected replies (determined from `node_details` database)

2. **is_text flag:** When `True`, validation service skips checking expected answers in other nodes in the flow

3. **UserStateService extracts user_reply:** Before calling ReplyValidationService, UserStateService extracts `user_reply` from data

4. **No user state updates in ReplyValidationService:** All user state updates (automation state, validation state) are handled by UserStateService

5. **UserStateService updates state only after node service success:** UserStateService waits for node service response, then updates both validation state and automation state

6. **matched_answer_id usage:** For matched status, `matched_answer_id` is used as `current_node_id` when calling NodeIdentificationService (not as a separate field in data)

