#!/usr/bin/env bash
# =============================================================================
# ETAP AI Engineering Platform - Docker Build Script
# =============================================================================
# Builds all Docker images for the platform.
#
# Usage:
#   ./scripts/docker_build.sh              # Build all images (default)
#   ./scripts/docker_build.sh --no-cache   # Build without cache
#   ./scripts/docker_build.sh --push       # Build and push to registry
#   ./scripts/docker_build.sh --platform   # Build for specific platform
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Defaults
REGISTRY="${REGISTRY:-}"
TAG="${TAG:-latest}"
PLATFORM="${PLATFORM:-linux/amd64}"
NO_CACHE=""
PUSH="false"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-cache)
      NO_CACHE="--no-cache"
      shift
      ;;
    --push)
      PUSH="true"
      shift
      ;;
    --platform)
      PLATFORM="$2"
      shift 2
      ;;
    --tag)
      TAG="$2"
      shift 2
      ;;
    --registry)
      REGISTRY="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--no-cache] [--push] [--platform linux/amd64] [--tag latest] [--registry registry.example.com]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Validate prerequisites
# ---------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || { echo "Error: docker is not installed"; exit 1; }
docker buildx version >/dev/null 2>&1 || { echo "Error: docker buildx is required"; exit 1; }

# ---------------------------------------------------------------------------
# Image tags
# ---------------------------------------------------------------------------
MAIN_IMAGE="${REGISTRY}etap-ai-platform:${TAG}"
WORKER_IMAGE="${REGISTRY}etap-windows-worker:${TAG}"

echo "=========================================="
echo " ETAP AI Platform - Docker Build"
echo "=========================================="
echo "Registry:       ${REGISTRY:-<none>}"
echo "Tag:            ${TAG}"
echo "Platform:       ${PLATFORM}"
echo "No cache:       ${NO_CACHE:-false}"
echo "Push:           ${PUSH}"
echo "=========================================="

# ---------------------------------------------------------------------------
# Step 1: Build Linux main image
# ---------------------------------------------------------------------------
echo ""
echo "[1/2] Building main platform image: ${MAIN_IMAGE}"

docker buildx build \
  ${NO_CACHE} \
  --platform "${PLATFORM}" \
  --target runtime \
  --file "${PROJECT_DIR}/Dockerfile" \
  --label "org.label-schema.build-date=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --label "org.label-schema.vcs-ref=$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
  $( [ "${PUSH}" = "true" ] && echo "--push" || echo "--load" ) \
  -t "${MAIN_IMAGE}" \
  "${PROJECT_DIR}"

echo "  ✓ Main image built successfully"

# ---------------------------------------------------------------------------
# Step 2: Build Windows worker image
# ---------------------------------------------------------------------------
echo ""
echo "[2/2] Building Windows worker image: ${WORKER_IMAGE}"

docker buildx build \
  ${NO_CACHE} \
  --platform windows/amd64 \
  --file "${PROJECT_DIR}/Dockerfile.windows-worker" \
  --label "org.label-schema.build-date=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --label "org.label-schema.vcs-ref=$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
  $( [ "${PUSH}" = "true" ] && echo "--push" || echo "--load" ) \
  -t "${WORKER_IMAGE}" \
  "${PROJECT_DIR}"

echo "  ✓ Windows worker image built successfully"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=========================================="
echo " Build Complete"
echo "=========================================="
echo "  ${MAIN_IMAGE}"
echo "  ${WORKER_IMAGE}"
echo "=========================================="
