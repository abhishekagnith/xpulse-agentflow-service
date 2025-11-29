# UserStateService - User State Table Update Scenarios

## Scenarios After NodeIdentificationService Response

### 1. Status: "internal_node"

**Scenario:** Next node is internal (condition, delay)

**Action:**
1. Call `ProcessInternalNodeService.process_internal_node()`
2. If internal node processing succeeds:
   - Update `user_automation_state`:
     ```python
     {
         "is_in_automation": True,
         "current_flow_id": flow_id,
         "current_node_id": next_node_id  # Internal node ID
     }
     ```

**Applies to:**
- New trigger
- Delay complete webhook
- Regular reply (with/without validation)

---

### 2. Status: "success"

**Scenario:** Node processed successfully

**Action:**
- Update `user_automation_state`:
  ```python
  {
      "is_in_automation": True,
      "current_flow_id": flow_id,
      "current_node_id": next_node_id  # From node service response
  }
  ```

**Additional Updates (for validation scenarios only):**

#### If validation_result["status"] == "mismatch_retry":
- Update `validation_state`:
  ```python
  {
      "validation_failed": True,
      "failure_message": fallback_message
  }
  ```

#### Otherwise (matched, matched_other_node, use_default_edge):
- Update `validation_state`:
  ```python
  {
      "validation_failed": False,
      "failure_message": None
  }
  ```

**Applies to:**
- New trigger
- Delay complete webhook
- Regular reply (with/without validation)

---

### 3. Status: "error"

**Scenario:** Node processing failed

**Action:**
- No user state update
- Log error message

**Applies to:**
- All scenarios

---

### 4. Status: "validation_exit" (Special Case)

**Scenario:** Validation limit exceeded (before calling node service)

**Action:**
1. Call node service with `is_validation_error = True`
2. If node service succeeds:
   - Update `user_automation_state`:
     ```python
     {
         "is_in_automation": False,
         "current_flow_id": None,
         "current_node_id": None
     }
     ```
   - Update `validation_state`:
     ```python
     {
         "validation_failed": False,
         "failure_message": None
     }
     ```

**Applies to:**
- Regular reply with validation (when limit exceeded)

---

## Summary Table

| Node Service Status | User Automation State Update | Validation State Update | Scenario |
|---------------------|----------------------------|------------------------|----------|
| `"internal_node"` | `is_in_automation: True`<br>`current_flow_id: flow_id`<br>`current_node_id: next_node_id` | None | All scenarios |
| `"success"` (no validation) | `is_in_automation: True`<br>`current_flow_id: flow_id`<br>`current_node_id: next_node_id` | None | New trigger, Delay complete, No expected reply |
| `"success"` (mismatch_retry) | `is_in_automation: True`<br>`current_flow_id: flow_id`<br>`current_node_id: next_node_id` | `validation_failed: True`<br>`failure_message: fallback_message` | Regular reply with validation |
| `"success"` (matched/matched_other_node/use_default_edge) | `is_in_automation: True`<br>`current_flow_id: flow_id`<br>`current_node_id: next_node_id` | `validation_failed: False`<br>`failure_message: None` | Regular reply with validation |
| `"error"` | No update | No update | All scenarios |
| `"validation_exit"` → node service `"success"` | `is_in_automation: False`<br>`current_flow_id: None`<br>`current_node_id: None` | `validation_failed: False`<br>`failure_message: None` | Validation limit exceeded |

---

## Update Methods Used

### 1. update_user_automation_state()
```python
await self.flow_db.update_user_automation_state(
    user_identifier=sender,
    brand_id=brand_id,
    is_in_automation=True/False,
    current_flow_id=flow_id/None,
    current_node_id=next_node_id/None,
    channel=channel,
    channel_account_id=channel_account_id
)
```

### 2. update_validation_state()
```python
await self.flow_db.update_validation_state(
    user_identifier=sender,
    brand_id=brand_id,
    validation_failed=True/False,
    failure_message=fallback_message/None,
    channel=channel,
    channel_account_id=channel_account_id
)
```

