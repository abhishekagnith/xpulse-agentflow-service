# Scripts

This directory contains utility scripts for the Flow Service.

## populate_node_details.py

This script populates the `node_details` MongoDB collection with all existing node types.

### Usage

```bash
# From the project root directory
python scripts/populate_node_details.py
```

### What it does

- Creates or updates node details for all 8 node types:
  - **Trigger nodes**: `trigger-keyword`, `trigger-template`
  - **Action nodes**: `message`, `question`, `button-question`, `list-question`
  - **Condition nodes**: `condition`
  - **Delay nodes**: `delay`

- Each node detail includes:
  - `node_id`: Unique identifier (e.g., "trigger-keyword")
  - `node_name`: Display name (e.g., "Keyword Trigger")
  - `category`: One of "Trigger", "Action", "Condition", "Delay"
  - `user_input_required`: Boolean indicating if user input is needed

### Prerequisites

- MongoDB connection configured in `.env` file
- All required environment variables set (see `.env.example`)
- Python dependencies installed (`pip install -r requirements.txt`)

### Output

The script will:
1. Display progress for each node being added/updated
2. Show a summary of all nodes in the database
3. Log all operations to Loki (if configured)

### Notes

- The script uses `upsert` operations, so it's safe to run multiple times
- Existing node details will be updated if they already exist
- The script will create the `node_details` collection if it doesn't exist


