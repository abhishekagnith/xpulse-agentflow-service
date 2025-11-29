# UserStateService Flow Diagram and Parameters

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ WebhookService.process_webhook_message()                     │
│ - Normalizes message                                         │
│ - Saves webhook with metadata & data                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │ UserStateService                       │
        │ check_and_process_user_with_flow()     │
        │ Receives:                              │
        │ - metadata (WebhookMetadata)           │
        │ - data (Dict[str, Any])                │
        │ - sender, brand_id, user_id, etc.     │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │ Check: User Exists?                    │
        └───────────────────────────────────────┘
                    │                    │
            NO      │                    │      YES
                    ▼                    ▼
    ┌───────────────────────┐  ┌──────────────────────┐
    │ Create User           │  │ Check:               │
    │                       │  │ is_in_automation?    │
    │ Call Trigger Service  │  └──────────────────────┘
    │ identify_and_initiate │              │
    │ _trigger_flow()       │      ┌───────┴───────┐
    │                       │      │               │
    │ Returns:             │   NO │               │ YES
    │ - status             │      │               │
    │ - flow_id            │      ▼               ▼
    │ - trigger_node_id    │ ┌──────────┐  ┌──────────────────┐
    │                       │ │ Check    │  │ Check:            │
    │ If matched:          │ │ Triggers  │  │ message_type ==   │
    │   Call Node Service  │ │          │  │ "delay_complete"? │
    │   with:              │ │ Call     │  └──────────────────┘
    │   - metadata         │ │ Trigger  │         │
    │   - data             │ │ Service  │    YES  │  NO
    │   - is_validation_   │ └──────────┘         │
    │     error = false    │                      │
    │   - fallback_message │                      ▼
    │     = null           │      ┌──────────────────────────────┐
    │   - node_id_to_      │      │ Check if current node has    │
    │     process =        │      │ expected reply                │
    │     trigger_node_id  │      │ (button_question, list_question)│
    │   - current_node_id  │      └──────────────────────────────┘
    │     = null           │                  │
    └───────────────────────┘          ┌───────┴───────┐
                                        │               │
                                    YES │               │ NO
                                        │               │
                                        ▼               ▼
                            ┌──────────────────┐  ┌──────────────┐
                            │ Call Reply       │  │ Call Node     │
                            │ Validation       │  │ Service with: │
                            │ Service          │  │ - metadata    │
                            │                  │  │ - data       │
                            │ validate_and_    │  │ - is_validation│
                            │ match_reply()    │  │   _error=false│
                            │                  │  │ - fallback_msg│
                            │ Returns:         │  │   =null       │
                            │ - status         │  │ - node_id_to_ │
                            │ - next_node_id   │  │   process=null │
                            │ - fallback_msg   │  │ - current_node│
                            │ - matched_node_id│  │   _id         │
                            └──────────────────┘  └──────────────┘
                                        │
                                        ▼
                            ┌──────────────────────┐
                            │ Based on status:     │
                            │                      │
                            │ - matched:           │
                            │   node_id_to_process │
                            │   = next_node_id     │
                            │   is_validation_error│
                            │   = false            │
                            │                      │
                            │ - mismatch_retry:    │
                            │   node_id_to_process │
                            │   = current_node_id  │
                            │   is_validation_error│
                            │   = true             │
                            │   fallback_message = │
                            │   message            │
                            │                      │
                            │ - validation_exit:   │
                            │   (exit automation)   │
                            │                      │
                            │ - matched_other_node:│
                            │   node_id_to_process │
                            │   = matched_node_id  │
                            │   is_validation_error│
                            │   = false            │
                            └──────────────────────┘
                                        │
                                        ▼
                            ┌──────────────────────┐
                            │ Call Node Service    │
                            │ identify_and_process │
                            │ _node()              │
                            │                      │
                            │ Parameters:          │
                            │ - metadata           │
                            │ - data               │
                            │ - is_validation_error│
                            │ - fallback_message   │
                            │ - node_id_to_process │
                            │ - current_node_id    │
                            └──────────────────────┘
```

## Parameters to NodeIdentificationService

### Scenario 1: New User - Trigger Matched
```python
{
    "metadata": WebhookMetadata(
        sender="919634086404",
        brand_id=1,
        user_id=1,
        channel_identifier="1289378275495917",
        channel="whatsapp",
        status="pending",
        message_type="text"
    ),
    "data": {
        "user_reply": "learn",
        "media_url": None,
        "media_type": None
    },
    "is_validation_error": False,
    "fallback_message": None,
    "node_id_to_process": None,  # null - node service identifies next node from trigger node
    "current_node_id": "trigger_keyword-node-1763631396283-h1ymxv3e3"  # trigger_node_id
}
```

### Scenario 2: User in Automation - Delay Complete Webhook
```python
{
    "metadata": WebhookMetadata(
        sender="system",
        brand_id=1,
        user_id=1,
        channel_identifier=None,
        channel="system",
        status="pending",
        message_type="delay_complete"
    ),
    "data": {
        "user_state_id": "919634086404"  # Extracted from message_body
    },
    "is_validation_error": False,
    "fallback_message": None,
    "node_id_to_process": None,  # Node service identifies next node from delay node
    "current_node_id": "delay-node-1764137867486-8xdbezftq"  # From user state
}
```

### Scenario 3: User in Automation - Reply Matched Expected Answer
```python
{
    "metadata": WebhookMetadata(
        sender="919634086404",
        brand_id=1,
        user_id=1,
        channel_identifier="1289378275495917",
        channel="whatsapp",
        status="pending",
        message_type="button"
    ),
    "data": {
        "user_reply": "IIT",
        "media_url": None,
        "media_type": None
    },
    "is_validation_error": False,
    "fallback_message": None,
    "node_id_to_process": None,  # null - node service identifies next node from matched answer edge
    "current_node_id": "button_question-node-1763631411168-xvt6ul76r"  # From user state
}
```

### Scenario 4: User in Automation - Reply Mismatch (Validation Error - No Match Found)
```python
{
    "metadata": WebhookMetadata(
        sender="919634086404",
        brand_id=1,
        user_id=1,
        channel_identifier="1289378275495917",
        channel="whatsapp",
        status="pending",
        message_type="text"
    ),
    "data": {
        "user_reply": "invalid reply",
        "media_url": None,
        "media_type": None
    },
    "is_validation_error": True,
    "fallback_message": "This is not the valid response. Please try again below",
    "node_id_to_process": "button_question-node-1763631411168-xvt6ul76r",  # Retry same node (current_node_id)
    "current_node_id": "button_question-node-1763631411168-xvt6ul76r"  # From user state
}
```

### Scenario 5: User in Automation - Reply Matched Other Node in Flow (Mismatch but Found in Another Node)
```python
{
    "metadata": WebhookMetadata(
        sender="919634086404",
        brand_id=1,
        user_id=1,
        channel_identifier="1289378275495917",
        channel="whatsapp",
        status="pending",
        message_type="text"
    ),
    "data": {
        "user_reply": "CUET",
        "media_url": None,
        "media_type": None
    },
    "is_validation_error": False,
    "fallback_message": None,
    "node_id_to_process": "button_question-node-1763631411168-xvt6ul76r",  # matched_node_id found in flow
    "current_node_id": "question-node-1763631557672-ldr6y58cm"  # From user state (different node)
}
```

### Scenario 6: User in Automation - No Expected Reply (Message/Question Node)
```python
{
    "metadata": WebhookMetadata(
        sender="919634086404",
        brand_id=1,
        user_id=1,
        channel_identifier="1289378275495917",
        channel="whatsapp",
        status="pending",
        message_type="text"
    ),
    "data": {
        "user_reply": "Abhishek",
        "media_url": None,
        "media_type": None
    },
    "is_validation_error": False,
    "fallback_message": None,
    "node_id_to_process": None,  # Node service identifies next node via default edge
    "current_node_id": "question-node-1763631557672-ldr6y58cm"  # From user state
}
```

## Parameter Rules Summary

### Key Rules:
1. **For new triggers**: 
   - `node_id_to_process` = `null` (node service identifies next node from trigger node)
   - `current_node_id` = `trigger_node_id`

2. **For reply match**: 
   - `node_id_to_process` = `null` (node service uses matched answer edge to find next node)
   - `current_node_id` = current node ID from user state

3. **For reply mismatch (matched in another node)**: 
   - `node_id_to_process` = matched node ID found in the flow
   - `current_node_id` = current node ID from user state

4. **For reply mismatch (no match found)**: 
   - `node_id_to_process` = current node ID (retry same node)
   - `current_node_id` = current node ID from user state
   - `is_validation_error` = `true`
   - `fallback_message` = validation error message

5. **`current_node_id` always goes**: 
   - Either as `trigger_node_id` (for new triggers) 
   - Or as `current_node_id` (if in automation)

## Current Issues to Fix

1. ❌ **UserStateService doesn't receive metadata/data** - Currently receives raw message_body
2. ❌ **Missing delay_complete check** - Doesn't check for delay webhooks
3. ❌ **NodeIdentificationService signature** - Needs to be updated to accept new parameters
4. ❌ **Trigger service return value** - Not used to get trigger_node_id and flow_id
5. ❌ **WebhookService** - Needs to pass saved webhook metadata/data to UserStateService
6. ❌ **Reply match logic** - Currently passes `next_node_id`, should pass `null` and let node service identify via matched answer edge

