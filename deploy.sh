#!/usr/bin/env bash

set -euo pipefail

log() {
  printf "[%s] %s\n" "$(date +"%H:%M:%S")" "$1"
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

if ! command_exists docker; then
  echo "Docker is required but not installed."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is required but not available via 'docker compose'."
  exit 1
fi

if [ ! -f .env ]; then
  echo ".env file not found. Copy .env.example to .env and add API keys."
  exit 1
fi

if ! grep -q '^GROQ_API_KEY=.' .env || ! grep -q '^GEMINI_API_KEY=.' .env || ! grep -q '^TAVILY_API_KEY=.' .env; then
  echo "One or more required API keys (GROQ_API_KEY, GEMINI_API_KEY, TAVILY_API_KEY) are missing in .env."
  exit 1
fi

log "Building containers"
if ! docker compose build --no-cache; then
  echo "Build failed."
  docker compose logs
  exit 1
fi

log "Starting containers"
if ! docker compose up -d; then
  echo "Startup failed."
  docker compose logs
  exit 1
fi

log "Waiting for backend health"
for i in {1..10}; do
  if curl -fsS http://localhost:8000/api/health >/dev/null 2>&1; then
    log "Backend is healthy"
    break
  fi
  sleep 3
  if [ "$i" -eq 10 ]; then
    echo "Health check failed."
    docker compose logs
    exit 1
  fi
done

if command_exists open; then
  open http://localhost:3000
elif command_exists xdg-open; then
  xdg-open http://localhost:3000
else
  log "Open http://localhost:3000 in your browser"
fi

echo "ResearchSwarm is live at http://localhost:3000"
