#!/bin/bash
set -e

# Default AWS configuration
AWS_REGION="${AWS_REGION:-ap-southeast-2}"
ECR_REPOSITORY="${ECR_REPOSITORY:-research-paper-rag}"
CONTAINER_NAME="research-paper-rag-container"

# Fetch AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity \
    --region "${AWS_REGION}" \
    --query Account \
    --output text)

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:latest"

echo "Logging in to Amazon ECR..."
aws ecr get-login-password --region "${AWS_REGION}" |
    docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "Pulling latest image: ${IMAGE_URI}..."
docker pull "${IMAGE_URI}"

# Locate environment file, prioritizing the RAG-specific file
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

ENV_ARGS=()
if [ -n "${ENV_FILE}" ]; then
    echo "Using environment file: ${ENV_FILE}"
    sed -i 's/\r$//' "${ENV_FILE}"
    sed -i 's/[[:space:]]*=[[:space:]]*/=/' "${ENV_FILE}"
    sed -i -E 's/="?([^"]*)"?$/=\1/' "${ENV_FILE}"
    ENV_ARGS=(--env-file "${ENV_FILE}")
fi

echo "Removing existing container if present..."
if docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
    docker rm -f "${CONTAINER_NAME}"
fi

echo "Starting Research Paper RAG container..."

docker run -d \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    -p 8502:7860 \
    -p 8001:8000 \
    "${ENV_ARGS[@]}" \
    "${IMAGE_URI}" \
    sh -c '
        uvicorn backend.main:app \
            --host 0.0.0.0 \
            --port 8000 \
            --root-path /research-rag-backend &

        exec streamlit run frontend/app.py \
            --server.port=7860 \
            --server.address=0.0.0.0 \
            --server.baseUrlPath=research-rag \
            --server.fileWatcherType=none \
            --browser.gatherUsageStats=false
    '

docker update --restart unless-stopped "${CONTAINER_NAME}"

echo "Research Paper RAG started successfully."
echo "Frontend: http://aryan-projects.duckdns.org/research-rag/"
echo "Backend docs: http://aryan-projects.duckdns.org/research-rag-backend/docs"













# #!/bin/bash
# set -e
# 
# # Default AWS configuration
# AWS_REGION="${AWS_REGION:-ap-southeast-2}"
# ECR_REPOSITORY="${ECR_REPOSITORY:-research-paper-rag}"
# CONTAINER_NAME="research-paper-rag-container"
# 
# # Fetch AWS Account ID dynamically
# AWS_ACCOUNT_ID=$(aws sts get-caller-identity --region ${AWS_REGION} --query Account --output text)
# ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
# IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:latest"
# 
# echo "Logging in to Amazon ECR..."
# aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
# 
# echo "Pulling latest image: ${IMAGE_URI}..."
# docker pull ${IMAGE_URI}
# 
# echo "Starting container..."
# # Locate environment file (prioritizing project-specific .env.rag to avoid collisions on shared EC2)
# ENV_FLAG=""
# ENV_FILE=""
# if [ -f "/home/ubuntu/.env.rag" ]; then
#     ENV_FILE="/home/ubuntu/.env.rag"
# elif [ -f "/home/ubuntu/app/.env.rag" ]; then
#     ENV_FILE="/home/ubuntu/app/.env.rag"
# elif [ -f "/home/ubuntu/.env" ]; then
#     ENV_FILE="/home/ubuntu/.env"
# elif [ -f "/home/ubuntu/app/.env" ]; then
#     ENV_FILE="/home/ubuntu/app/.env"
# fi
# 
# if [ -n "$ENV_FILE" ]; then
#     # Sanitize env file format for Docker
#     sed -i 's/\r$//' "$ENV_FILE"
#     sed -i 's/[[:space:]]*=[[:space:]]*/=/' "$ENV_FILE"
#     sed -i -E 's/="?([^"]*)"?$/=\1/' "$ENV_FILE"
#     ENV_FLAG="--env-file $ENV_FILE"
# fi
# 
# # Run container mapping host port 8502 to Streamlit (7860) and host port 8001 to FastAPI (8000)
# docker run -d \
#     --name ${CONTAINER_NAME} \
#     --restart unless-stopped \
#     -p 8502:7860 \
#     -p 8001:8000 \
#     $ENV_FLAG \
#     ${IMAGE_URI}
# 
# # Ensure restart policy is applied
# docker update --restart unless-stopped ${CONTAINER_NAME}
# 
# echo "Research Paper RAG container started successfully with automatic restart policy."
