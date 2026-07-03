#!/usr/bin/env bash
# =============================================================================
# One-command public deploy of the ETAP Engineering Service
# =============================================================================
# Targets a pre-built GHCR image:
#   ghcr.io/<owner>/<repo>/etap-engineering-service[:<tag>]
#
# Usage:
#   ./scripts/deploy-engineering-service.sh fly      <app-name> [--region iad] [--tag latest] [--repo owner/repo]
#   ./scripts/deploy-engineering-service.sh render                                       [--tag latest] [--repo owner/repo]
#   ./scripts/deploy-engineering-service.sh railway                                      [--tag latest] [--repo owner/repo]
#   ./scripts/deploy-engineering-service.sh all                                          [--tag latest]
#   ./scripts/deploy-engineering-service.sh docker-run [--port 8000] [--tag latest] [--repo owner/repo]
#
# Examples:
#   ./scripts/deploy-engineering-service.sh fly etap-eng-prod --region iad
#   ./scripts/deploy-engineering-service.sh render --tag v1.2.3
#   ./scripts/deploy-engineering-service.sh railway
#   ./scripts/deploy-engineering-service.sh all --tag v1.2.3
#
# Before running, make sure the image exists:
#   ./scripts/docker_build.sh --service engineering-service --multiarch --push --tag v1.2.3
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Defaults
PLATFORM=""
APP_NAME="etap-engineering-service"
REGION="iad"
TAG="latest"
REPO=""                # owner/repo; auto-derived if empty
PORT="8000"
API_KEY="${ENGINEERING_SERVICE_API_KEY:-}"
NO_BROWSER="false"

# ---------------------------------------------------------------------------
# Pretty output
# ---------------------------------------------------------------------------
RED=$'\033[0;31m'; GRN=$'\033[0;32m'; YEL=$'\033[0;33m'; BLU=$'\033[0;34m'; RST=$'\033[0m'
say()   { echo "${BLU}[deploy]${RST} $*"; }
ok()    { echo "${GRN}[ ✓ ]${RST} $*"; }
warn()  { echo "${YEL}[ ! ]${RST} $*" >&2; }
die()   { echo "${RED}[ ✗ ]${RST} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Resolve GHCR_REPOSITORY (owner/repo) the same way docker_build.sh does
# ---------------------------------------------------------------------------
resolve_repo() {
  if [[ -n "${REPO}" ]]; then echo "${REPO}"; return 0; fi
  if [[ -n "${GHCR_REPOSITORY:-}" ]]; then echo "${GHCR_REPOSITORY}"; return 0; fi
  if [[ -n "${GITHUB_REPOSITORY:-}" ]]; then echo "${GITHUB_REPOSITORY}"; return 0; fi
  local remote
  remote="$(git -C "${PROJECT_DIR}" remote get-url origin 2>/dev/null || true)"
  if [[ -n "${remote}" ]]; then
    echo "${remote}" | sed -E 's#^.*github\.com[:/]([^/]+/[^/]+?)(\.git)?$#\1#'
    return 0
  fi
  return 1
}

image_for() {
  # $1 = repo (owner/name)
  echo "ghcr.io/${1}/etap-engineering-service:${TAG}"
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
  sed -n '2,30p' "$0" | sed 's/^# \?//'
  exit "${1:-0}"
}

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
if [[ $# -lt 1 ]]; then usage 1; fi
PLATFORM="$1"; shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)  REGION="$2"; shift 2 ;;
    --tag)     TAG="$2"; shift 2 ;;
    --repo)    REPO="$2"; shift 2 ;;
    --port)    PORT="$2"; shift 2 ;;
    --app)     APP_NAME="$2"; shift 2 ;;
    --api-key) API_KEY="$2"; shift 2 ;;
    --no-browser) NO_BROWSER="true"; shift ;;
    -h|--help) usage 0 ;;
    *)
      # First positional after the platform = app name (Fly only)
      if [[ "${PLATFORM}" = "fly" ]] && [[ -z "${APP_NAME_SET:-}" ]]; then
        APP_NAME="$1"; APP_NAME_SET="true"; shift
      else
        die "Unknown argument: $1"
      fi
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
REPO_RESOLVED="$(resolve_repo)" || die "Could not determine GitHub owner/repo. Set --repo OWNER/REPO or GHCR_REPOSITORY."
IMAGE="$(image_for "${REPO_RESOLVED}")"
say "Image:    ${IMAGE}"
say "Platform: ${PLATFORM}"
[[ -n "${API_KEY}" ]] && say "API key:  (set, ${#API_KEY} chars)" || say "API key:  (not set — service will be open)"

# ---------------------------------------------------------------------------
# Fly.io
# ---------------------------------------------------------------------------
deploy_fly() {
  command -v fly >/dev/null 2>&1 || die "fly CLI not installed. Install: https://fly.io/docs/hands-on/install-flyctl/"
  # Log in if needed
  if ! fly auth whoami >/dev/null 2>&1; then
    say "Logging you in to Fly.io…"
    fly auth login
  fi
  local whoami; whoami="$(fly auth whoami)"
  ok "Logged in as ${whoami}"

  # Create app if it doesn't exist (use `fly apps show` so we don't depend on JSON parsing)
  if ! fly apps show "${APP_NAME}" >/dev/null 2>&1; then
    say "Creating Fly app '${APP_NAME}' in ${REGION}…"
    fly apps create "${APP_NAME}" --org personal || warn "App create returned non-zero (may already exist)."
  else
    ok "Fly app '${APP_NAME}' already exists."
  fi

  # Set API key secret if provided
  if [[ -n "${API_KEY}" ]]; then
    say "Setting ENGINEERING_SERVICE_API_KEY secret…"
    fly secrets set ENGINEERING_SERVICE_API_KEY="${API_KEY}" --app "${APP_NAME}" >/dev/null
  fi

  # Override the image at deploy time. `fly deploy --image` overrides the [build] image
  # in fly.toml, so we don't need to patch the file. fly.toml still provides env vars,
  # services, health checks, and VM sizing.
  say "Deploying to ${APP_NAME} (region=${REGION}, image=${IMAGE})…"
  fly deploy \
      --image "${IMAGE}" \
      --primary-region "${REGION}" \
      --app "${APP_NAME}" \
      --strategy rolling

  echo
  ok "Deployed. Public URL: https://${APP_NAME}.fly.dev"
  say "Health:  curl https://${APP_NAME}.fly.dev/health"
  say "Logs:    fly logs --app ${APP_NAME}"
}

# ---------------------------------------------------------------------------
# Render (one-click)
# ---------------------------------------------------------------------------
deploy_render() {
  local url="https://render.com/deploy?repo=https://github.com/${REPO_RESOLVED}"
  say "Render is best deployed via the one-click button:"
  echo "    ${url}"
  if [[ "${NO_BROWSER}" != "true" ]] && command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${url}" >/dev/null 2>&1 || true
  elif [[ "${NO_BROWSER}" != "true" ]] && command -v open >/dev/null 2>&1; then
    open "${url}" >/dev/null 2>&1 || true
  fi

  # If the user has the Render CLI installed, do it for them
  if command -v render >/dev/null 2>&1; then
    if render whoami >/dev/null 2>&1; then
      # Patch the __GHCR_IMAGE__ placeholder in render.yaml (forks / different repos)
      local patched="${PROJECT_DIR}/render.yaml.tmp"
      sed "s|__GHCR_IMAGE__|${IMAGE}|g" "${PROJECT_DIR}/render.yaml" > "${patched}"
      trap 'rm -f "${patched}"' EXIT INT TERM
      say "Render CLI detected and authenticated — launching blueprint…"
      (cd "${PROJECT_DIR}" && render blueprint launch)
      rm -f "${patched}"
    else
      warn "render CLI present but not authenticated. Run 'render login' then 'render blueprint launch'."
    fi
  else
    say "Or with the Render CLI (after installing it):"
    echo "    render login"
    echo "    render blueprint launch   # from the repo root"
  fi
}

# ---------------------------------------------------------------------------
# Railway
# ---------------------------------------------------------------------------
deploy_railway() {
  command -v railway >/dev/null 2>&1 || die "railway CLI not installed. Install: https://docs.railway.com/guides/cli"
  if ! railway whoami >/dev/null 2>&1; then
    say "Logging you in to Railway…"
    railway login
  fi
  local whoami; whoami="$(railway whoami 2>&1 | head -1)"
  ok "Logged in: ${whoami}"

  if [[ ! -f "${PROJECT_DIR}/railway.toml" ]]; then
    die "railway.toml not found at ${PROJECT_DIR}/railway.toml"
  fi

  say "Initializing Railway project (if needed)…"
  if ! railway status >/dev/null 2>&1; then
    railway init --name "${APP_NAME}" || warn "railway init returned non-zero (project may already exist)."
  else
    ok "Railway project already linked."
  fi

  if [[ -n "${API_KEY}" ]]; then
    say "Setting ENGINEERING_SERVICE_API_KEY variable…"
    railway variables --set "ENGINEERING_SERVICE_API_KEY=${API_KEY}" >/dev/null \
      || warn "railway variables --set returned non-zero."
  fi

  say "Deploying from GHCR image ${IMAGE}…"
  railway up --image "${IMAGE}" --service "${APP_NAME}" --detach \
    || warn "railway up returned non-zero."

  echo
  say "Generating public domain…"
  railway domain || true
  ok "Deployed. Run 'railway status' for the URL."
  say "Logs:   railway logs"
}

# ---------------------------------------------------------------------------
# docker-run (local public via tunnel — convenience)
# ---------------------------------------------------------------------------
deploy_docker_run() {
  command -v docker >/dev/null 2>&1 || die "docker not installed"
  say "Pulling ${IMAGE}…"
  docker pull "${IMAGE}"
  docker rm -f etap-eng-svc >/dev/null 2>&1 || true
  say "Starting container on host port ${PORT}…"
  docker run -d --name etap-eng-svc \
    -p "${PORT}:8000" \
    -e "ENGINEERING_SERVICE_API_KEY=${API_KEY}" \
    "${IMAGE}"
  ok "Running at http://localhost:${PORT}"
  say "For a public URL, also run:  ./scripts/start-engineering-tunnel.sh"
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
case "${PLATFORM}" in
  fly)        deploy_fly ;;
  render)     deploy_render ;;
  railway)    deploy_railway ;;
  docker-run|docker) deploy_docker_run ;;
  all)
    deploy_fly || warn "Fly deploy skipped (continuing)"
    deploy_render || warn "Render deploy skipped (continuing)"
    deploy_railway || warn "Railway deploy skipped (continuing)"
    ;;
  -h|--help)  usage 0 ;;
  *)          die "Unknown platform: ${PLATFORM}. Use fly | render | railway | docker-run | all." ;;
esac
