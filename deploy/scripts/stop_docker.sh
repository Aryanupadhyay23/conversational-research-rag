#!/bin/bash
# Stop and remove existing container if running
CONTAINER_NAME="research-paper-rag-container"

echo "Stopping existing container: ${CONTAINER_NAME}..."
if command -v docker &> /dev/null; then
    docker stop "${CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${CONTAINER_NAME}" 2>/dev/null || true
fi
