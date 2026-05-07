#!/bin/bash
# Start both web server and scheduler for River's Edge

# Start scheduler in background
python rivers_edge_scheduler.py &

# Start web server in foreground
gunicorn rivers_edge_chatbot_backend:app
