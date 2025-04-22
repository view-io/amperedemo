#!/bin/bash

# Check if we're in test mode
if [ "$TEST_MODE" = "true" ]; then
    echo "Running in test mode. Services will not start automatically."
    tail -f /dev/null
else
    # Start nginx
    service nginx start

    # Start the FastAPI application
    uvicorn main:app  --host 0.0.0.0 --port 8000 --reload
fi