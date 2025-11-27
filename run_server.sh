#!/bin/bash
# Script to run the Django server with WebSocket support

cd "$(dirname "$0")"
source venv/bin/activate

# Run with daphne for WebSocket support
daphne -b 0.0.0.0 -p 8000 qa_agent.asgi:application

