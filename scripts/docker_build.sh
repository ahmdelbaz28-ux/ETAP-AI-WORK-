#!/usr/bin/env bash
# =============================================================================
# ETAP AI Engineering Platform - Docker Build & Push Script
# =============================================================================
# Builds (and optionally pushes) Docker images for the platform.
#
# Usage:
#   ./scripts/docker_build.sh                                          # Build all (single-arch, loadable)
#   ./scripts/docker_build.sh --push                                   # Build all + push to registry
#   ./scripts/docker_build.sh --service engineering-service            # Build only one service
#   ./scripts/docker_build.sh --multiarch                              # Multi-arch (linux/amd64,linux/arm64)
#   ./scripts/docker_build.sh --platform linux/arm64                   # Build for a single non-default arch
#
#   # Common release flow — push engineering service to GHCR (multi-arch):
#   export GITHUB_TOKEN=<token-with-write:packages>
#   export GITHUB_ACTOR=<github-username>
#   ./scripts/docker_build.sh \
#       --service engineering-service \
#       --multiarch \
#       --push \
#       --tag v1.2.3
#
# GHCR auto-detect (in priority order):
#   1. $GHCR_REPOSITORY        e.g. "owner/repo"
#   2. $GITHUB_REPOSITORY      set by GitHub Actions
#   3. `git remote get-url origin`  (SSH or HTTPS form)
#   4. error with instructions
#
# Image naming:
#   Without --registry:  <service>:<tag>             (local)
#   With --registry:     <registry>/<service>:<tag>  (e.g. ghcr.io/owner/repo/etap-engineering-service:v1.2.3)
#
# QEMU / multi-arch:
#   The script uses whatever buildx builder is currently selected. If you
#   haven't set one up for multi-arch, run:
#     docker buildx create --name etap-multiarch --driver docker-container --use
#   The docker-container driver ships with QEMU baked in.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
REGISTRY=""             # e.g. "ghcr.io/owner/repo/" — empty means local
TAG="latest"
PLATFORM="linux/amd64"
NO_CACHE=""
PUSH="false"
MULTIARCH="false"
SERVICE=""              # empty = all services
GIT_SHA="$(git -C "${PROJECT_DIR}" rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GHCR_REPOSITORY=""

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
    --multiarch)
      MULTIARCH="true"
      shift
      ;;
    --service)
      SERVICE="$2"
      shift 2
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
      grep -E '^#( |$)' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Run with --help for usage." >&2
      exit 1
      ;;
  esac
done

# Auto-detect multiarch from a comma in --platform
if [[ "${PLATFORM}" == *","* ]]; then
  MULTIARCH="true"
fi

# ---------------------------------------------------------------------------
# Validate prerequisites
# ---------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || { echo "Error: docker is not installed" >&2; exit 1; }
docker buildx version >/dev/null 2>&1 || { echo "Error: docker buildx is required" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Resolve GHCR_REPOSITORY (used for image naming + labels)
# ---------------------------------------------------------------------------
if [[ -n "${GHCR_REPOSITORY:-}" ]]; then
  : # already set
elif [[ -n "${GITHUB_REPOSITORY:-}" ]]; then
  GHCR_REPOSITORY="${GITHUB_REPOSITORY}"
else
  remote="$(git -C "${PROJECT_DIR}" remote get-url origin 2>/dev/null || true)"
  if [[ -n "${remote}" ]]; then
    # SSH: git@github.com:owner/repo(.git) ; HTTPS: https://github.com/owner/repo(.git)
    GHCR_REPOSITORY="$(echo "${remote}" | sed -E 's#^.*github\.com[:/]([^/]+/[^/]+?)(\.git)?$#\1#')"
  fi
fi

# If --registry wasn't passed but --push is set, try to default to GHCR
if [[ -z "${REGISTRY}" ]] && [[ "${PUSH}" = "true" ]] && [[ -n "${GHCR_REPOSITORY}" ]]; then
  REGISTRY="ghcr.io/${GHCR_REPOSITORY}/"
  echo "  → Auto-derived registry: ${REGISTRY}"
fi

# Normalize trailing slash on registry
REGISTRY="${REGISTRY%/}/"
# Re-render "registry/  " as "registry" when registry is empty
if [[ "${REGISTRY}" = "/" ]]; then REGISTRY=""; fi

# ---------------------------------------------------------------------------
# GHCR login
# ---------------------------------------------------------------------------
login_ghcr() {
  case "${REGISTRY}" in
    *ghcr.io*) ;;
    *) return 0 ;;
  esac
  if [[ -z "${GITHUB_TOKEN:-}" ]]; then
    echo "Error: GITHUB_TOKEN env var required to push to GHCR" >&2
    echo "  Create a PAT with 'write:packages' scope:" >&2
    echo "    https://github.com/settings/tokens/new?scopes=write:packages" >&2
    exit 1
  fi
  local user="${GITHUB_ACTOR:-${GITHUB_USERNAME:-github}}"
  echo "  → docker login ghcr.io (user=${user})"
  echo "${GITHUB_TOKEN}" | docker login ghcr.io -u "${user}" --password-stdin >/dev/null
}

warn_qemu() {
  if [[ "${MULTIARCH}" != "true" ]]; then return 0; fi
  local driver
  driver="$(docker buildx inspect 2>/dev/null | awk -F': ' '/Driver:/ {print $2; exit}' || true)"
  if [[ -z "${driver}" ]] || { [[ "${driver}" != "docker-container" ]] && [[ "${driver}" != "remote" ]] && [[ "${driver}" != "kubernetes" ]]; }; then
    cat <<EOF >&2
⚠️  Multi-arch build requested, but current buildx driver is '${driver:-default}'.
   For best results, run once:
     docker buildx create --name etap-multiarch --driver docker-container --use
   The docker-container driver has QEMU pre-installed.

EOF
  fi
}

# ---------------------------------------------------------------------------
# Service registry — keeps build steps DRY
# ---------------------------------------------------------------------------
SERVICES=(
  "etap-ai-platform|Dockerfile|linux/amd64"
  "etap-windows-worker|Dockerfile.windows-worker|windows/amd64"
  "etap-engineering-service|Dockerfile.engineering-service|linux/amd64"
)

should_build() {
  if [[ -z "${SERVICE}" ]]; then return 0; fi
  [[ "${SERVICE}" = "$1" ]] && return 0 || return 1
}

# ---------------------------------------------------------------------------
# Build step (single service)
# ---------------------------------------------------------------------------
build_service() {
  local name="$1"
  local dockerfile="$2"
  local default_platform="$3"
  local image="${REGISTRY}${name}:${TAG}"
  local extra_tag=""
  local platforms
  local platform_label
  local output_flag
  local target_args=()

  if [[ "${MULTIARCH}" = "true" ]]; then
    platforms="${PLATFORM}"
    platform_label="${PLATFORM}"
  else
    platforms="${default_platform}"
    platform_label="${default_platform}"
  fi

  # Decide --load vs --push
  if [[ "${MULTIARCH}" = "true" ]]; then
    if [[ "${PUSH}" != "true" ]]; then
      echo "  ! Multi-arch build requires --push. Auto-enabling --push." >&2
      PUSH="true"
    fi
    output_flag="--push"
  else
    if [[ "${PUSH}" = "true" ]]; then
      output_flag="--push"
    else
      output_flag="--load"
    fi
  fi

  # Also tag with the short SHA when pushing (traceability)
  if [[ "${PUSH}" = "true" ]] && [[ "${TAG}" = "latest" ]] && [[ "${GIT_SHA}" != "unknown" ]]; then
    extra_tag="${REGISTRY}${name}:sha-${GIT_SHA}"
  fi

  # Per-service target args
  case "${name}" in
    etap-ai-platform)
      target_args=(--target runtime)
      ;;
  esac

  echo ""
  echo "[+] Building ${name}"
  echo "    Dockerfile:   ${dockerfile}"
  echo "    Platforms:    ${platform_label}"
  echo "    Image:        ${image}"
  [[ -n "${extra_tag}" ]] && echo "    Extra tag:    ${extra_tag}"
  echo "    Output:       ${output_flag}"

  local cmd=(
    docker buildx build
    ${NO_CACHE}
    --platform "${platforms}"
    --file "${PROJECT_DIR}/${dockerfile}"
    --label "org.opencontainers.image.title=${name}"
    --label "org.opencontainers.image.source=https://github.com/${GHCR_REPOSITORY:-ahmdelbaz28/my-awesome-agent}"
    --label "org.opencontainers.image.revision=${GIT_SHA}"
    --label "org.opencontainers.image.created=${BUILD_DATE}"
  )
  cmd+=("${target_args[@]}" "${output_flag}" -t "${image}")
  if [[ -n "${extra_tag}" ]]; then
    cmd+=(-t "${extra_tag}")
  fi
  cmd+=("${PROJECT_DIR}")

  "${cmd[@]}"
  echo "    ✓ Built ${name}"
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
echo "=========================================="
echo " ETAP AI Platform - Docker Build"
echo "=========================================="
echo "Registry:    ${REGISTRY:-<none — local>}"
echo "Tag:         ${TAG}"
echo "Platform:    ${PLATFORM}"
echo "Multi-arch:  ${MULTIARCH}"
echo "Service:     ${SERVICE:-<all>}"
echo "No cache:    ${NO_CACHE:-false}"
echo "Push:        ${PUSH}"
echo "=========================================="

# ---------------------------------------------------------------------------
# Login if pushing to GHCR
# ---------------------------------------------------------------------------
login_ghcr
warn_qemu

# ---------------------------------------------------------------------------
# Run build steps
# ---------------------------------------------------------------------------
for entry in "${SERVICES[@]}"; do
  IFS='|' read -r name dockerfile default_platform <<< "${entry}"
  if should_build "${name}"; then
    build_service "${name}" "${dockerfile}" "${default_platform}"
  fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=========================================="
echo " Build Complete"
echo "=========================================="
for entry in "${SERVICES[@]}"; do
  IFS='|' read -r name dockerfile default_platform <<< "${entry}"
  if should_build "${name}"; then
    echo "  ${REGISTRY}${name}:${TAG}"
  fi
done
echo "=========================================="
