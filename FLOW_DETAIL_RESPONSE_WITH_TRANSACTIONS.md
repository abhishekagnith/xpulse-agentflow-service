# Flow Detail API - Updated Response Structure with Transaction Counts

## Overview

The Flow Detail API (`GET /flow/detail/{flow_id}`) now includes transaction counts for each node in the flow. The transaction count represents the total number of user transactions that have been processed for each node.

## Updated Response Structure

### Complete Response Example

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

## New Field: transactionCount

### Description
- **Field Name:** `transactionCount`
- **Type:** `integer`
- **Location:** Included in each node object within the `flowNodes` array
- **Description:** Total number of user transactions processed for this specific node
- **Default Value:** `0` if no transactions exist for the node

### How It Works

1. **Data Source:** Transaction counts are retrieved from the `user_transactions` collection
2. **Grouping:** Transactions are grouped by `flow_id` and `node_id`
3. **Calculation:** The count represents the total number of transactions where:
   - `flow_id` matches the requested flow
   - `node_id` matches the specific node

### Example Values

- `transactionCount: 0` - No transactions have been processed for this node
- `transactionCount: 45` - 45 transactions have been processed for this node
- `transactionCount: 1234` - 1234 transactions have been processed for this node

## Implementation Details

### Database Query
The transaction counts are calculated using MongoDB aggregation:
```javascript
[
  { "$match": { "flow_id": "<flow_id>" } },
  { "$group": {
      "_id": "$node_id",
      "count": { "$sum": 1 }
    }
  }
]
```

### Performance Considerations
- Transaction counts are calculated on-demand when the detail API is called
- The aggregation query is efficient and only processes transactions for the specific flow
- If a node has no transactions, the count defaults to 0

## Notes

1. **Only in Detail API:** The `transactionCount` field is **only** included in the Flow Detail API response, not in the List API response
2. **All Node Types:** Transaction counts are included for all node types (trigger, message, question, button_question, list_question, condition, delay)
3. **Real-time Data:** Counts reflect the current state of transactions in the database at the time of the API call
4. **Zero Counts:** Nodes with no transactions will show `transactionCount: 0`

## Use Cases

- **Analytics:** Track which nodes are most frequently processed
- **Flow Optimization:** Identify bottlenecks or popular paths in flows
- **Performance Monitoring:** Monitor node processing volumes
- **User Engagement:** Understand which parts of flows are most active

