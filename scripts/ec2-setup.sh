#!/usr/bin/env bash

# ====================================================================
# ResearchSwarm — AWS EC2 One-Click Initialization & Setup Script
# Works on Ubuntu 22.04 LTS / 24.04 LTS and Amazon Linux 2023
# ====================================================================

set -euo pipefail

log() {
  printf "\033[1;32m[%s]\033[0m %s\n" "$(date +"%H:%M:%S")" "$1"
}

warn() {
  printf "\033[1;33m[%s] WARNING:\033[0m %s\n" "$(date +"%H:%M:%S")" "$1"
}

error() {
  printf "\033[1;31m[%s] ERROR:\033[0m %s\n" "$(date +"%H:%M:%S")" "$1"
  exit 1
}

# 1. Detect Package Manager
if command -v apt-get >/dev/null 2>&1; then
  PKG_MANAGER="apt"
elif command -v dnf >/dev/null 2>&1; then
  PKG_MANAGER="dnf"
else
  error "Unsupported Linux distribution. Requires apt (Ubuntu/Debian) or dnf (Amazon Linux 2023)."
fi

log "Detected package manager: $PKG_MANAGER"

# 2. System Update & Dependencies
log "Updating system packages..."
if [ "$PKG_MANAGER" = "apt" ]; then
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl gnupg lsb-release git ufw
elif [ "$PKG_MANAGER" = "dnf" ]; then
  sudo dnf update -y
  sudo dnf install -y curl git
fi

# 3. Install Docker & Docker Compose
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker..."
  if [ "$PKG_MANAGER" = "apt" ]; then
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  elif [ "$PKG_MANAGER" = "dnf" ]; then
    sudo dnf install -y docker
    sudo systemctl enable --now docker
  fi
else
  log "Docker is already installed ($(docker --version))"
fi

# Enable Docker Service
sudo systemctl enable docker
sudo systemctl start docker

# Add Current User to Docker Group
log "Adding $USER to docker group..."
sudo usermod -aG docker "$USER" || true

# 4. Verify Docker Compose
if docker compose version >/dev/null 2>&1; then
  log "Docker Compose available: $(docker compose version)"
else
  error "Docker Compose installation failed."
fi

# 5. Configure Firewall (Ubuntu UFW)
if command -v ufw >/dev/null 2>&1; then
  log "Configuring basic firewall (UFW)..."
  sudo ufw allow 22/tcp comment 'SSH'
  sudo ufw allow 80/tcp comment 'HTTP'
  sudo ufw allow 443/tcp comment 'HTTPS'
  sudo ufw allow 3000/tcp comment 'Frontend UI'
  sudo ufw allow 8000/tcp comment 'Backend API'
  sudo ufw --force enable || true
fi

log "===================================================================="
log "EC2 Instance Provisioning Complete!"
log "NOTE: Please log out and log back in to apply docker group membership:"
log "      exit && ssh -i <your-key.pem> $USER@<your-ec2-ip>"
log "===================================================================="
