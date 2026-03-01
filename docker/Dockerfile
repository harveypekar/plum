# Plum Docker Image - Replicates VPS environment for testing
# Build: docker-compose -f docker/docker-compose.local.yml build

FROM ubuntu:22.04

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install base tools
RUN apt-get update && apt-get install -y \
    bash \
    curl \
    wget \
    git \
    ssh \
    openssh-client \
    vim \
    jq \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /plum

# Copy scripts into container
COPY scripts/ /plum/scripts/
COPY .env.example /plum/.env.example

# Make scripts executable
RUN chmod +x /plum/scripts/**/*.sh

# Default command
CMD ["/bin/bash"]
