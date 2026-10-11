#!/bin/bash
set -e

# Update package lists and install Docker if missing
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    apt-get update -y
    apt-get install -y docker.io unzip curl
    systemctl enable docker
    systemctl start docker
    usermod -aG docker ubuntu
fi

# Ensure docker daemon is active and enabled on system startup
systemctl enable docker
systemctl start docker

# Install AWS CLI v2 if missing
if ! command -v aws &> /dev/null; then
    echo "Installing AWS CLI..."
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    ./aws/install
    rm -rf aws awscliv2.zip
fi

echo "Dependencies ready."
