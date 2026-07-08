#!/bin/bash
# ETAP AI Platform - Quick Start Script
# This script sets up and starts the platform in one command

set -e  # Exit on error

echo "=========================================="
echo "ETAP AI Engineering Platform - Quick Start"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_success() {
    local param="$1"
    echo -e "${GREEN}✓ ${param}${NC}"
}

print_info() {
    local param="$1"
    echo -e "${BLUE}ℹ ${param}${NC}"
}

print_error() {
    local param="$1"
    echo -e "${RED}✗ ${param}${NC}"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

print_success "Docker and Docker Compose found"

# Check if .env file exists
if [[ ! -f .env ]]; then
    print_info "Creating .env file from template..."
    cp .env.example .env
    print_success ".env file created. Please edit it with your configuration."
fi

# Build and start services
print_info "Building Docker images..."
docker-compose build

print_info "Starting services..."
docker-compose up -d

# Optionally start the Engineering Service (FastAPI) under the
# `engineering` profile. Set START_ENGINEERING_SERVICE=1 in the environment
# to opt in non-interactively; otherwise prompt if stdin is a TTY.
START_ENG="${START_ENGINEERING_SERVICE:-}"
if [[ -z "$START_ENG" ]]; then
  if [[ -t 0 ]]; then
    read -rp "Start the Engineering Service too? [y/N]: " START_ENG
    START_ENG="$(printf '%s' "${START_ENG:-n}" | tr '[:upper:]' '[:lower:]')"
  else
    START_ENG="n"
  fi
fi
if [[ "$START_ENG" = "y" ]] || [[ "$START_ENG" = "yes" ]] || [[ "$START_ENG" = "1" ]]; then
  print_info "Starting Engineering Service (profile: engineering)..."
  docker-compose --profile engineering up -d engineering-service
  print_info "Waiting for Engineering Service /health..."
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo 000)
    if [[ "$code" = "200" ]]; then
      print_success "Engineering Service is running and healthy (port 8000)"
      break
    fi
    sleep 1
  done
fi

# Wait for services to be ready
print_info "Waiting for services to start..."
sleep 10

# Check health
print_info "Checking service health..."
if curl -f http://localhost:3000/health &> /dev/null; then
    print_success "Platform is running and healthy!"
    echo ""
    echo "Access the platform at: http://localhost:3000"
    echo "API documentation: http://localhost:3000/docs"
    echo ""
    echo "Engineering Service:   http://localhost:8000 (if started)"
    echo ""
    echo "Useful commands:"
    echo "  View logs:     docker-compose logs -f"
    echo "  Stop services: docker-compose down"
    echo "  Restart:       docker-compose restart"
    echo ""
    echo "To start the Engineering Service (Python FastAPI) on port 8000:"
    echo "  docker compose --profile engineering up -d"
    echo "Or set START_ENGINEERING_SERVICE=1 before running this script."
else
    print_error "Platform may not be ready yet. Check logs:"
    echo "  docker-compose logs -f"
fi

echo ""
print_success "Setup complete!"
