# UserStateService ↔ NodeIdentificationService Interaction

## Parameters Sent by UserStateService

```python
{
    "metadata": WebhookMetadata,           # Webhook metadata object (contains user_identifier, brand_id, user_id, channel, channel_identifier)
    "data": Dict[str, Any],                 # Webhook data (contains user_reply, media_url, etc.)
    "is_validation_error": bool,            # True if validation failed, False otherwise
    "fallback_message": Optional[str],      # Fallback message for validation failures
    "node_id_to_process": Optional[str],    # Node ID to process (None = identify next node)
    "current_node_id": str,                 # Current node ID (or trigger_node_id or matched_answer_id)
    "flow_id": str                          # Flow ID
}
```

---

## Scenarios and Parameters

### 1. New Trigger (New User or Existing User Not in Automation)
```python
{
    "is_validation_error": False,
    "fallback_message": None,
    "node_id_to_process": None,
    "current_node_id": trigger_node_id
}
```

### 2. Delay Complete Webhook
```python
{
    "is_validation_error": False,
    "fallback_message": None,
    "node_id_to_process": None,
    "current_node_id": delay_node_id  # From user state
}
```

### 3. Validation Exit (Limit Exceeded)
```python
{
    "is_validation_error": True,
    "fallback_message": "Node fallback message",
    "node_id_to_process": None,
    "current_node_id": current_node_id  # From user state
}
```

### 4. Reply Matched (Current Node)
```python
{
    "is_validation_error": False,
    "fallback_message": None,
    "node_id_to_process": None,
    "current_node_id": matched_answer_id  # Uses matched_answer_id as current_node_id
}
```

### 5. Reply Matched (Other Node)
```python
{
    "is_validation_error": False,
    "fallback_message": None,
    "node_id_to_process": matched_node_id,
    "current_node_id": current_node_id  # From user state
}
```

### 6. Reply Mismatch Retry
```python
{
    "is_validation_error": True,
    "fallback_message": "Validation fallback message",
    "node_id_to_process": current_node_id,  # Retry same node
    "current_node_id": current_node_id  # From user state
}
```

### 7. Use Default Edge (No Expected Reply)
```python
{
    "is_validation_error": False,
    "fallback_message": None,
    "node_id_to_process": None,
    "current_node_id": current_node_id  # From user state
}
```

---

## Responses from NodeIdentificationService

### Success Response
```python
{
    "status": "success",
    "message": "Node identified and processed successfully",
    "next_node_id": "node-id-xxx"  # Next node ID after processing
}
```

### Internal Node Response
```python
{
    "status": "internal_node",
    "message": "Next node is internal",
    "next_node_id": "node-id-xxx"  # Internal node ID (condition, delay, etc.)
}
```

### Error Responses

#### User Not Found
```python
{
    "status": "error",
    "message": "User not found",
    "next_node_id": None
}
```

#### Flow Not Found
```python
{
    "status": "error",
    "message": "Flow not found",
    "next_node_id": None
}
```

#### Current Node Not Found
```python
{
    "status": "error",
    "message": "Current node not found in flow",
    "next_node_id": None
}
```

#### Next Node Not Found
```python
{
    "status": "error",
    "message": "Next node {next_node_id} not found",
    "next_node_id": None
}
```

#### Node Processing Failed
```python
{
    "status": "error",
    "message": "Node processing failed",
    "next_node_id": None
}
```

#### General Error
```python
{
    "status": "error",
    "message": "Error identifying and processing node: {error_details}",
    "next_node_id": None
}
```

---

## Summary Table

| Scenario | is_validation_error | fallback_message | node_id_to_process | current_node_id |
|----------|---------------------|------------------|-------------------|-----------------|
| New Trigger | `False` | `None` | `None` | `trigger_node_id` |
| Delay Complete | `False` | `None` | `None` | `delay_node_id` |
| Validation Exit | `True` | `"Node fallback"` | `None` | `current_node_id` |
| Reply Matched (Current) | `False` | `None` | `None` | `matched_answer_id` |
| Reply Matched (Other) | `False` | `None` | `matched_node_id` | `current_node_id` |
| Reply Mismatch Retry | `True` | `"Fallback msg"` | `current_node_id` | `current_node_id` |
| Use Default Edge | `False` | `None` | `None` | `current_node_id` |

---

## Response Status Values

| Status | Meaning | next_node_id |
|--------|---------|--------------|
| `"success"` | Node processed successfully | Next node ID |
| `"internal_node"` | Next node is internal (condition, delay) | Internal node ID |
| `"error"` | Error occurred | `None` |

