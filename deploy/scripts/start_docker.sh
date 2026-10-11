#!/bin/bash
set -e

# Default AWS configuration
AWS_REGION="${AWS_REGION:-ap-southeast-2}"
ECR_REPOSITORY="${ECR_REPOSITORY:-research-paper-rag}"
CONTAINER_NAME="research-paper-rag-container"

# Fetch AWS Account ID dynamically
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --region ${AWS_REGION} --query Account --output text)
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:latest"

echo "Logging in to Amazon ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}

echo "Pulling latest image: ${IMAGE_URI}..."
docker pull ${IMAGE_URI}

echo "Starting container..."
# Locate environment file (prioritizing project-specific .env.rag to avoid collisions on shared EC2)
ENV_FLAG=""
ENV_FILE=""
if [ -f "/home/ubuntu/.env.rag" ]; then
    ENV_FILE="/home/ubuntu/.env.rag"
elif [ -f "/home/ubuntu/app/.env.rag" ]; then
    ENV_FILE="/home/ubuntu/app/.env.rag"
elif [ -f "/home/ubuntu/.env" ]; then
    ENV_FILE="/home/ubuntu/.env"
elif [ -f "/home/ubuntu/app/.env" ]; then
    ENV_FILE="/home/ubuntu/app/.env"
fi

if [ -n "$ENV_FILE" ]; then
    # Sanitize env file format for Docker
    sed -i 's/\r$//' "$ENV_FILE"
    sed -i 's/[[:space:]]*=[[:space:]]*/=/' "$ENV_FILE"
    sed -i -E 's/="?([^"]*)"?$/=\1/' "$ENV_FILE"
    ENV_FLAG="--env-file $ENV_FILE"
fi

# Run container mapping port 80 to Streamlit (7860) and port 8000 for FastAPI
docker run -d \
    --name ${CONTAINER_NAME} \
    --restart unless-stopped \
    -p 80:7860 \
    -p 8000:8000 \
    $ENV_FLAG \
    ${IMAGE_URI}

# Ensure restart policy is applied
docker update --restart unless-stopped ${CONTAINER_NAME}

echo "Research Paper RAG container started successfully with automatic restart policy."
