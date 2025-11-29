# Flow API Documentation

## API Endpoints

### 1. List Flows API

**Endpoint:** `GET /flow/list`

**Headers:**
```
x-user-id: <integer>
```

**Response:** Array of FlowData objects

**Response Structure:**
```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "name": "My Flow",
    "created": "2025-01-15T10:30:00.000Z",
    "flowNodes": [
      {
        "id": "trigger-keyword-node-123",
        "type": "trigger_keyword",
        "flowNodeType": "Trigger",
        "flowNodePosition": {
          "posX": "-172.05",
          "posY": "-174.58"
        },
        "isStartNode": true,
        "triggerKeywords": ["hello", "hi"]
      },
      {
        "id": "message-node-456",
        "type": "message",
        "flowNodeType": "Message",
        "flowNodePosition": {
          "posX": "128.18",
          "posY": "-164.33"
        },
        "isStartNode": false,
        "flowReplies": [
          {
            "flowReplyType": "Text",
            "data": "Hello! How can I help you?",
            "caption": "",
            "mimeType": ""
          }
        ]
      }
    ],
    "flowEdges": [
      {
        "id": "edge-123",
        "sourceNodeId": "trigger-keyword-node-123",
        "targetNodeId": "message-node-456"
      }
    ],
    "lastUpdated": "2025-01-20T15:45:00.000Z",
    "transform": {
      "posX": "-291.90",
      "posY": "181.90",
      "zoom": "0.56"
    },
    "isPro": false,
    "status": "draft",
    "brand_id": 1,
    "user_id": 123,
    "created_at": "2025-01-15T10:30:00.000Z",
    "updated_at": "2025-01-20T15:45:00.000Z"
  }
]
```

**Response Fields:**
- `id` (string): MongoDB ObjectId of the flow
- `name` (string): Flow name
- `created` (datetime): Flow creation timestamp
- `flowNodes` (array): Array of flow nodes (see node types below)
- `flowEdges` (array): Array of flow edges connecting nodes
- `lastUpdated` (string, optional): Last update timestamp
- `transform` (object, optional): Canvas transform data
- `isPro` (boolean): Whether flow is pro version
- `status` (string): Flow status - "draft" or "published"
- `brand_id` (integer): Brand ID
- `user_id` (integer): User ID
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last update timestamp

**Example Response (Empty):**
```json
[]
```

---

### 2. Flow Detail API

**Endpoint:** `GET /flow/detail/{flow_id}`

**Headers:**
```
x-user-id: <integer>
```

**Path Parameters:**
- `flow_id` (string): MongoDB ObjectId of the flow

**Response:** Single FlowData object with transaction counts for each node

**Response Structure:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "My Flow",
  "created": "2025-01-15T10:30:00.000Z",
  "flowNodes": [
    {
      "id": "trigger-keyword-node-123",
      "type": "trigger_keyword",
      "flowNodeType": "Trigger",
      "flowNodePosition": {
        "posX": "-172.05",
        "posY": "-174.58"
      },
      "isStartNode": true,
      "triggerKeywords": ["hello", "hi"],
      "transactionCount": 45
    },
    {
      "id": "message-node-456",
      "type": "message",
      "flowNodeType": "Message",
      "flowNodePosition": {
        "posX": "128.18",
        "posY": "-164.33"
      },
      "isStartNode": false,
      "flowReplies": [
        {
          "flowReplyType": "Text",
          "data": "Hello! How can I help you?",
          "caption": "",
          "mimeType": ""
        }
      ],
      "transactionCount": 42
    },
    {
      "id": "question-node-789",
      "type": "question",
      "flowNodeType": "Question",
      "flowNodePosition": {
        "posX": "300.50",
        "posY": "200.75"
      },
      "isStartNode": false,
      "flowReplies": [
        {
          "flowReplyType": "Text",
          "data": "What's your name?",
          "caption": "",
          "mimeType": ""
        }
      ],
      "userInputVariable": "@name",
      "answerValidation": {
        "type": "None",
        "minValue": "",
        "maxValue": "",
        "regex": "",
        "fallback": "Please try again",
        "failsCount": "3"
      },
      "isMediaAccepted": false,
      "transactionCount": 38
    },
    {
      "id": "button-question-node-101",
      "type": "button_question",
      "flowNodeType": "Question",
      "flowNodePosition": {
        "posX": "400.00",
        "posY": "300.00"
      },
      "isStartNode": false,
      "interactiveButtonsHeader": {
        "type": "Text",
        "text": "Choose an option",
        "media": null
      },
      "interactiveButtonsBody": "Please select one of the following:",
      "interactiveButtonsFooter": "Thank you!",
      "interactiveButtonsUserInputVariable": "@choice",
      "interactiveButtonsDefaultNodeResultId": "",
      "expectedAnswers": [
        {
          "id": "btn-1",
          "expectedInput": "Option A",
          "isDefault": true,
          "nodeResultId": "message-node-456"
        },
        {
          "id": "btn-2",
          "expectedInput": "Option B",
          "isDefault": false,
          "nodeResultId": "message-node-789"
        }
      ],
      "transactionCount": 35
    },
    {
      "id": "condition-node-202",
      "type": "condition",
      "flowNodeType": "Condition",
      "flowNodePosition": {
        "posX": "500.00",
        "posY": "400.00"
      },
      "isStartNode": false,
      "flowNodeConditions": [
        {
          "id": "cond-1",
          "flowConditionType": "Equal",
          "variable": "@name",
          "value": "John"
        }
      ],
      "conditionResult": [
        {
          "id": "result-1",
          "expectedInput": "true",
          "isDefault": true,
          "nodeResultId": "message-node-456"
        },
        {
          "id": "result-2",
          "expectedInput": "false",
          "isDefault": false,
          "nodeResultId": "message-node-789"
        }
      ],
      "conditionOperator": "None",
      "transactionCount": 30
    },
    {
      "id": "delay-node-303",
      "type": "delay",
      "flowNodeType": "Delay",
      "flowNodePosition": {
        "posX": "600.00",
        "posY": "500.00"
      },
      "isStartNode": false,
      "delayDuration": 5,
      "delayUnit": "minutes",
      "waitForReply": false,
      "delayInterrupt": false,
      "delayResult": [
        {
          "id": "delay-result-1",
          "expectedInput": "complete",
          "isDefault": true,
          "nodeResultId": "message-node-456"
        }
      ],
      "transactionCount": 25
    }
  ],
  "flowEdges": [
    {
      "id": "edge-123",
      "sourceNodeId": "trigger-keyword-node-123",
      "targetNodeId": "message-node-456"
    },
    {
      "id": "edge-456",
      "sourceNodeId": "message-node-456",
      "targetNodeId": "question-node-789"
    }
  ],
  "lastUpdated": "2025-01-20T15:45:00.000Z",
  "transform": {
    "posX": "-291.90",
    "posY": "181.90",
    "zoom": "0.56"
  },
  "isPro": false,
  "status": "draft",
  "brand_id": 1,
  "user_id": 123,
  "created_at": "2025-01-15T10:30:00.000Z",
  "updated_at": "2025-01-20T15:45:00.000Z"
}
```

**Response Fields:** Same as List API (single object instead of array), with additional field:
- `transactionCount` (integer): Number of transactions processed for this node (included in each node object)

**Note:** The `transactionCount` field is only included in the Detail API response when the flow status is "published" or "stop". For "draft" flows, the transactionCount field is not included. It represents the total number of user transactions that have been processed for each node in the flow.

**Error Responses:**
- `404`: Flow not found
- `401`: Unauthorized (missing x-user-id header)
- `500`: Internal server error

---

### 3. Update Flow Status API

**Endpoint:** `POST /flow/status/{flow_id}`

**Headers:**
```
x-user-id: <integer>
Content-Type: application/json
```

**Path Parameters:**
- `flow_id` (string): MongoDB ObjectId of the flow

**Request Body:**
```json
{
  "status": "published" | "stop"
}
```

**Request Example (Publish Flow):**
```bash
curl -X POST "http://localhost:8000/flow/status/507f1f77bcf86cd799439011" \
  -H "x-user-id: 123" \
  -H "Content-Type: application/json" \
  -d '{"status": "published"}'
```

**Request Example (Stop Flow):**
```bash
curl -X POST "http://localhost:8000/flow/status/507f1f77bcf86cd799439011" \
  -H "x-user-id: 123" \
  -H "Content-Type: application/json" \
  -d '{"status": "stop"}'
```

**Response:** Updated FlowData object with new status

**Response Structure:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "My Flow",
  "created": "2025-01-15T10:30:00.000Z",
  "flowNodes": [...],
  "flowEdges": [...],
  "lastUpdated": "2025-01-20T15:45:00.000Z",
  "transform": {
    "posX": "-291.90",
    "posY": "181.90",
    "zoom": "0.56"
  },
  "isPro": false,
  "status": "published",
  "brand_id": 1,
  "user_id": 123,
  "created_at": "2025-01-15T10:30:00.000Z",
  "updated_at": "2025-01-20T16:00:00.000Z"
}
```

**Response Fields:** Same as Detail API, with `status` updated to the requested value and `updated_at` updated

**Valid Status Values:**
- `"published"`: Publish the flow (makes it active and triggerable)
- `"stop"`: Stop a published flow (prevents new triggers)

**Status Transition Rules:**
- `draft` → `published`: ✅ Allowed
- `published` → `stop`: ✅ Allowed
- `stop` → `published`: ✅ Allowed (resume flow)
- Any → `draft`: ❌ Not allowed (use update API to modify flow content)

**Error Responses:**
- `400`: Invalid status value or missing status in request body
- `404`: Flow not found
- `401`: Unauthorized (missing x-user-id header)
- `403`: Unauthorized (flow does not belong to user)
- `500`: Internal server error

**Success Response Codes:**
- `200`: Flow status updated successfully

---

## Node Types Reference

### Trigger Keyword Node
```json
{
  "id": "string",
  "type": "trigger_keyword",
  "flowNodeType": "Trigger",
  "flowNodePosition": { "posX": "string", "posY": "string" },
  "isStartNode": true,
  "triggerKeywords": ["keyword1", "keyword2"]
}
```

### Trigger Template Node
```json
{
  "id": "string",
  "type": "trigger_template",
  "flowNodeType": "Trigger",
  "flowNodePosition": { "posX": "string", "posY": "string" },
  "isStartNode": true,
  "triggerTemplateId": "string",
  "triggerTemplateName": "string (optional)",
  "expectedAnswers": [
    {
      "id": "string",
      "expectedInput": "string",
      "isDefault": true,
      "nodeResultId": "string (optional)"
    }
  ]
}
```

### Message Node
```json
{
  "id": "string",
  "type": "message",
  "flowNodeType": "Message",
  "flowNodePosition": { "posX": "string", "posY": "string" },
  "isStartNode": false,
  "flowReplies": [
    {
      "flowReplyType": "Text|Image|Video|Audio|Document",
      "data": "string",
      "caption": "string (optional)",
      "mimeType": "string (optional)"
    }
  ]
}
```

### Question Node
```json
{
  "id": "string",
  "type": "question",
  "flowNodeType": "Question",
  "flowNodePosition": { "posX": "string", "posY": "string" },
  "isStartNode": false,
  "flowReplies": [
    {
      "flowReplyType": "Text",
      "data": "string",
      "caption": "",
      "mimeType": ""
    }
  ],
  "userInputVariable": "@variable_name",
  "answerValidation": {
    "type": "None|Number|Text|Email|Phone",
    "minValue": "string",
    "maxValue": "string",
    "regex": "string",
    "fallback": "string",
    "failsCount": "string"
  },
  "isMediaAccepted": false
}
```

### Button Question Node
```json
{
  "id": "string",
  "type": "button_question",
  "flowNodeType": "Question",
  "flowNodePosition": { "posX": "string", "posY": "string" },
  "isStartNode": false,
  "interactiveButtonsHeader": {
    "type": "Text|Image|Video|Document",
    "text": "string (optional)",
    "media": "string (optional)"
  },
  "interactiveButtonsBody": "string",
  "interactiveButtonsFooter": "string (optional)",
  "interactiveButtonsUserInputVariable": "@variable_name",
  "interactiveButtonsDefaultNodeResultId": "string (optional)",
  "expectedAnswers": [
    {
      "id": "string",
      "expectedInput": "string",
      "isDefault": true,
      "nodeResultId": "string (optional)"
    }
  ]
}
```

### List Question Node
```json
{
  "id": "string",
  "type": "list_question",
  "flowNodeType": "Question",
  "flowNodePosition": { "posX": "string", "posY": "string" },
  "isStartNode": false,
  "flowReplies": [
    {
      "flowReplyType": "Text",
      "data": "string",
      "caption": "",
      "mimeType": ""
    }
  ],
  "userInputVariable": "@variable_name",
  "answerValidation": {
    "type": "None|Number|Text|Email|Phone",
    "minValue": "string",
    "maxValue": "string",
    "regex": "string",
    "fallback": "string",
    "failsCount": "string"
  },
  "isMediaAccepted": false
}
```

### Condition Node
```json
{
  "id": "string",
  "type": "condition",
  "flowNodeType": "Condition",
  "flowNodePosition": { "posX": "string", "posY": "string" },
  "isStartNode": false,
  "flowNodeConditions": [
    {
      "id": "string",
      "flowConditionType": "Equal|NotEqual|GreaterThan|LessThan|Contains|NotContains",
      "variable": "@variable_name",
      "value": "string"
    }
  ],
  "conditionResult": [
    {
      "id": "string",
      "expectedInput": "true|false",
      "isDefault": true,
      "nodeResultId": "string"
    }
  ],
  "conditionOperator": "None|And|Or"
}
```

### Delay Node
```json
{
  "id": "string",
  "type": "delay",
  "flowNodeType": "Delay",
  "flowNodePosition": { "posX": "string", "posY": "string" },
  "isStartNode": false,
  "delayDuration": 5,
  "delayUnit": "seconds|minutes|hours|days",
  "waitForReply": false,
  "delayInterrupt": false,
  "delayResult": [
    {
      "id": "string",
      "expectedInput": "complete|interrupted",
      "isDefault": true,
      "nodeResultId": "string"
    }
  ]
}
```

---

## Status Values

- `"draft"`: Flow is in draft mode (default for create/update operations)
  - Flows in draft status cannot be triggered
  - Transaction counts are not included in detail API response
- `"published"`: Flow is published and active
  - Published flows can be triggered by users
  - Transaction counts are included in detail API response
- `"stop"`: Flow is stopped (was previously published)
  - Stopped flows cannot be triggered
  - Transaction counts are included in detail API response
  - Can be resumed by setting status back to "published"

---

## Notes

1. All datetime fields are returned in ISO 8601 format (UTC)
2. The `status` field is included in all flow responses (list, detail, publish)
3. The publish API only updates the status field, all other flow data remains unchanged
4. All endpoints require the `x-user-id` header for authentication
5. Flow ownership is validated - users can only publish their own flows

