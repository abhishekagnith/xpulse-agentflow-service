# Flow Service

A generic flow automation service that manages multi-channel conversation flows.

## Overview

This service provides a channel-agnostic flow engine for managing automated conversations across multiple channels (WhatsApp, Email, SMS, Facebook, etc.).

## Features

- **Flow Management**: Create, update, and manage conversation flows
- **User State Management**: Track user progress through flows
- **Node Processing**: Handle different node types (message, question, button_question, etc.)
- **Context Storage**: Store user responses and variables
- **Channel Agnostic**: Works with any messaging channel

## Architecture

```
flow_service/
├── src/
│   ├── apis/          # API endpoints
│   ├── services/      # Business logic
│   ├── database/      # Database operations
│   ├── models/        # Data models
│   ├── utils/         # Utility functions
│   ├── exceptions/    # Custom exceptions
│   └── main.py        # Application entry point
├── requirements.txt
├── .env.example
└── README.md
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run the service:
```bash
python src/main.py
```

## API Endpoints

- `POST /flow/create` - Create a new flow
- `GET /flow/list` - List all flows
- `GET /flow/{flow_id}` - Get flow details
- `PUT /flow/{flow_id}` - Update a flow
- `DELETE /flow/{flow_id}` - Delete a flow

## Environment Variables

See `.env.example` for required environment variables.

## MongoDB Collections

- `flows` - Flow definitions
- `flow_nodes` - Flow node data
- `flow_edges` - Flow edge connections
- `flow_triggers` - Flow trigger configurations
- `users` - User state and progress
- `flow_user_context` - User response context

## License

Proprietary

