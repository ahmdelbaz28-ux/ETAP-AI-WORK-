# =============================================================================
# AhmedETAP — Locust Stress Test Suite
# Comprehensive stress testing with study execution, AI assistant, auth flows,
# and custom metrics for study execution time tracking.
# =============================================================================

import json
import logging
import time

from locust import HttpUser, between, events, task
from locust.runners import MasterRunner, WorkerRunner

logger = logging.getLogger("ahmedetap-locust")

# ─── Custom Event Listeners & Metrics ────────────────────────────────────────

# Track study execution times for custom reporting
_study_execution_times: list[float] = []
_study_success_count: int = 0
_study_failure_count: int = 0


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log when the test starts."""
    runner_type = (
        "master"
        if isinstance(environment.runner, MasterRunner)
        else "worker"
        if isinstance(environment.runner, WorkerRunner)
        else "standalone"
    )
    logger.info(f"Locust test starting — runner: {runner_type}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print custom study execution metrics when the test ends."""
    if _study_execution_times:
        avg_time = sum(_study_execution_times) / len(_study_execution_times)
        max_time = max(_study_execution_times)
        min_time = min(_study_execution_times)
        p95_idx = int(len(_study_execution_times) * 0.95)
        sorted_times = sorted(_study_execution_times)
        p95_time = sorted_times[min(p95_idx, len(sorted_times) - 1)]
        logger.info(
            f"\n{'=' * 60}\n"
            f"  Study Execution Metrics (Custom)\n"
            f"{'=' * 60}\n"
            f"  Total studies:    {len(_study_execution_times)}\n"
            f"  Successful:       {_study_success_count}\n"
            f"  Failed:           {_study_failure_count}\n"
            f"  Avg time:         {avg_time:.1f} ms\n"
            f"  Min time:         {min_time:.1f} ms\n"
            f"  Max time:         {max_time:.1f} ms\n"
            f"  P95 time:         {p95_time:.1f} ms\n"
            f"{'=' * 60}"
        )


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track study-specific metrics on each request."""
    global _study_success_count, _study_failure_count
    if exception is None:
        if "study" in name.lower():
            _study_success_count += 1
            _study_execution_times.append(response_time)
    else:
        if "study" in name.lower():
            _study_failure_count += 1


# ─── Test Data ───────────────────────────────────────────────────────────────

SAMPLE_SYSTEM = {
    "base_mva": 100.0,
    "buses": [
        {"bus_id": 1, "voltage_magnitude": 1.05, "bus_type": "slack", "base_kv": 138.0},
        {
            "bus_id": 2,
            "voltage_magnitude": 1.0,
            "bus_type": "pq",
            "base_kv": 13.8,
            "load_power_real": 50,
            "load_power_imag": 20,
        },
        {
            "bus_id": 3,
            "voltage_magnitude": 1.0,
            "bus_type": "pv",
            "base_kv": 4.16,
            "generation_power_real": 30,
            "voltage_setpoint": 1.02,
        },
    ],
    "lines": [
        {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05, "bshunt1": 0.02},
        {"line_id": 2, "from_bus_id": 2, "to_bus_id": 3, "r1": 0.02, "x1": 0.08, "bshunt1": 0.01},
    ],
    "generators": [
        {"generator_id": 1, "bus_id": 1, "x1": 0.2, "internal_voltage_mag": 1.05},
        {
            "generator_id": 2,
            "bus_id": 3,
            "x1": 0.15,
            "internal_voltage_mag": 1.02,
            "power_real": 30,
        },
    ],
    "loads": [
        {"load_id": 1, "bus_id": 2, "p_mw": 50, "q_mvar": 20},
    ],
}

AI_QUESTIONS = [
    "What is the IEEE 1584-2018 standard for arc flash calculations?",
    "How do I size a cable for a 4.16kV motor starting scenario?",
    "Explain the difference between symmetrical and asymmetrical fault currents.",
    "What are the protection coordination requirements for a radial distribution system?",
    "How to calculate ground grid resistance per IEEE 80?",
    "What is the difference between load-flow Newton-Raphson and Fast-Decoupled methods?",
    "Explain IEC 60909 short circuit methodology.",
    "What are typical arc flash boundary distances for 480V switchgear?",
    "How to perform harmonic analysis per IEEE 519-2022?",
    "What relay coordination intervals are recommended for overcurrent protection?",
]


# ─── User Classes ────────────────────────────────────────────────────────────


class AuthenticatedUser(HttpUser):
    """Base user that handles authentication flow.

    Attempts to log in on start and stores the JWT token for subsequent requests.
    Falls back to unauthenticated mode if auth is disabled or login fails.
    """

    # Wait between 1 and 3 seconds between tasks (realistic user behavior)
    wait_time = between(1, 3)

    # Default credentials for load testing (should be created in test DB)
    _TEST_USERNAME = "loadtest_user"
    _TEST_PASSWORD = "LoadTest123!@#"

    def on_start(self):
        """Authenticate on user start."""
        self.token = None
        self.auth_headers = {"Content-Type": "application/json"}
        self._authenticate()

    def _authenticate(self):
        """Attempt JWT authentication. Falls back gracefully if auth is disabled."""
        # Try login first
        try:
            login_resp = self.client.post(
                "/api/v1/auth/login",
                json={
                    "username": self._TEST_USERNAME,
                    "password": self._TEST_PASSWORD,
                },
                name="/api/v1/auth/login",
                catch_response=True,
            )
            if login_resp.status_code == 200:
                try:
                    body = login_resp.json()
                    self.token = body.get("access_token") or body.get("token")
                    if self.token:
                        self.auth_headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {self.token}",
                        }
                        login_resp.success()
                        logger.debug("Authenticated successfully as loadtest_user")
                        return
                except json.JSONDecodeError:
                    pass
            elif login_resp.status_code == 401:
                # Try registering the test user
                self._register_test_user()
            elif login_resp.status_code == 404:
                # Auth endpoints may not be available — continue without auth
                login_resp.success()
                logger.debug("Auth endpoints not available — continuing without auth")
                return
            # If auth is disabled, the endpoint might not exist or return unexpected status
            login_resp.success()
        except Exception as e:
            logger.debug(f"Auth attempt failed (non-fatal): {e}")

    def _register_test_user(self):
        """Register the test user if they don't exist yet."""
        try:
            reg_resp = self.client.post(
                "/api/v1/auth/register",
                json={
                    "username": self._TEST_USERNAME,
                    "email": "loadtest@etap-ai.local",
                    "password": self._TEST_PASSWORD,
                    "full_name": "Load Test User",
                },
                name="/api/v1/auth/register",
                catch_response=True,
            )
            if reg_resp.status_code in (200, 201):
                # Now try logging in again
                login_resp = self.client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": self._TEST_USERNAME,
                        "password": self._TEST_PASSWORD,
                    },
                    name="/api/v1/auth/login",
                    catch_response=True,
                )
                if login_resp.status_code == 200:
                    try:
                        body = login_resp.json()
                        self.token = body.get("access_token") or body.get("token")
                        if self.token:
                            self.auth_headers = {
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {self.token}",
                            }
                    except json.JSONDecodeError:
                        pass
                login_resp.success()
            reg_resp.success()
        except Exception:
            pass

    def _get_auth_headers(self):
        """Return headers with auth if available, otherwise just content-type."""
        return self.auth_headers


class EngineeringServiceUser(AuthenticatedUser):
    """Simulates an engineering service user performing various operations.

    Task weights:
      - Health/Ready checks: 30%  (lightweight, frequent)
      - Study execution:     25%  (heavy, core functionality)
      - AI assistant chat:   15%  (medium, LLM-backed)
      - System validation:   10%  (medium)
      - Metrics retrieval:   10%  (lightweight)
      - Agent info:          10%  (lightweight)
    """

    # ── Health & Readiness (weight 5 each = 10 total) ───────────────────────

    @task(5)
    def health_check(self):
        self.client.get("/health", name="GET /health")

    @task(5)
    def readiness_check(self):
        self.client.get("/ready", name="GET /ready")

    @task(3)
    def liveness_probe(self):
        self.client.get("/healthz", name="GET /healthz")

    # ── Study Execution (weight: 15) ────────────────────────────────────────

    @task(8)
    def run_load_flow(self):
        """Execute a load flow study with a realistic power system model."""
        time.time()
        self.client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "load_flow",
                "system": SAMPLE_SYSTEM,
                "parameters": {
                    "max_iterations": 100,
                    "tolerance": 1e-6,
                    "algorithm": "newton_raphson",
                },
            },
            headers=self._get_auth_headers(),
            name="POST /api/v1/studies/run [load_flow]",
        )

    @task(4)
    def run_short_circuit(self):
        """Execute a short circuit study."""
        self.client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "short_circuit",
                "system": SAMPLE_SYSTEM,
                "parameters": {
                    "fault_type": "three_phase",
                    "bus_id": 2,
                },
            },
            headers=self._get_auth_headers(),
            name="POST /api/v1/studies/run [short_circuit]",
        )

    @task(3)
    def run_arc_flash(self):
        """Execute an arc flash study."""
        self.client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "arc_flash",
                "parameters": {
                    "voltage_kv": 13.8,
                    "bolted_fault_current_ka": 20.0,
                    "arc_duration_sec": 0.5,
                    "working_distance_mm": 610,
                },
            },
            headers=self._get_auth_headers(),
            name="POST /api/v1/studies/run [arc_flash]",
        )

    # ── AI Assistant Chat (weight: 15) ──────────────────────────────────────

    @task(8)
    def etap_expert_chat(self):
        """Chat with the ETAP Expert AI assistant."""
        import random

        question = random.choice(AI_QUESTIONS)
        self.client.post(
            "/api/v1/agents/etap-expert/chat",
            json={
                "question": question,
            },
            headers=self._get_auth_headers(),
            name="POST /api/v1/agents/etap-expert/chat",
        )

    @task(4)
    def etap_gui_chat(self):
        """Chat with the ETAP GUI Agent."""
        import random

        question = random.choice(AI_QUESTIONS[:5])  # Shorter questions for GUI agent
        self.client.post(
            "/api/v1/agents/etap-gui/chat",
            json={
                "question": question,
            },
            headers=self._get_auth_headers(),
            name="POST /api/v1/agents/etap-gui/chat",
        )

    @task(3)
    def rag_query(self):
        """Query the engineering knowledge base via RAG."""
        self.client.post(
            "/api/v1/rag/query",
            json={
                "query": "What are the IEEE 1584 arc flash calculation methods?",
                "top_k": 3,
            },
            headers=self._get_auth_headers(),
            name="POST /api/v1/rag/query",
        )

    # ── System Validation (weight: 10) ──────────────────────────────────────

    @task(5)
    def validate_system(self):
        """Validate a power system model."""
        self.client.post(
            "/api/v1/system/validate",
            json={
                "buses": [
                    {"id": "BUS1", "nominal_kv": 13.8, "type": "swing"},
                    {"id": "BUS2", "nominal_kv": 4.16, "type": "load"},
                    {"id": "BUS3", "nominal_kv": 0.48, "type": "pq"},
                ],
                "branches": [
                    {"from_bus": "BUS1", "to_bus": "BUS2", "r": 0.01, "x": 0.05},
                    {"from_bus": "BUS2", "to_bus": "BUS3", "r": 0.02, "x": 0.08},
                ],
            },
            headers=self._get_auth_headers(),
            name="POST /api/v1/system/validate",
        )

    @task(5)
    def ml_capabilities(self):
        """Check ML/AI capabilities endpoint."""
        self.client.get(
            "/api/v1/ml/capabilities",
            headers=self._get_auth_headers(),
            name="GET /api/v1/ml/capabilities",
        )

    # ── Metrics & Agent Info (weight: 10 each) ─────────────────────────────

    @task(5)
    def get_metrics(self):
        """Retrieve service metrics."""
        self.client.get("/metrics", name="GET /metrics")

    @task(5)
    def get_agents_info(self):
        """Retrieve agent metadata and prompt status."""
        self.client.get(
            "/api/v1/agents/info",
            headers=self._get_auth_headers(),
            name="GET /api/v1/agents/info",
        )

    @task(3)
    def get_prometheus_metrics(self):
        """Scrape Prometheus metrics endpoint."""
        self.client.get("/prometheus/metrics", name="GET /prometheus/metrics")


class LightHealthCheckUser(HttpUser):
    """Lightweight user that only hits health endpoints.

    Simulates k8s liveness/readiness probes or monitoring systems.
    Used to ensure health endpoints remain responsive under load.
    """

    wait_time = between(0.5, 1.5)

    @task(10)
    def health(self):
        self.client.get("/health", name="GET /health [light]")

    @task(10)
    def ready(self):
        self.client.get("/ready", name="GET /ready [light]")

    @task(5)
    def healthz(self):
        self.client.get("/healthz", name="GET /healthz [light]")

    @task(2)
    def root(self):
        self.client.get("/", name="GET / [light]")
