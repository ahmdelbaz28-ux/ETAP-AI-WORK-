from locust import HttpUser, between, task


class EngineeringServiceUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(5)
    def health_check(self):
        self.client.get("/health")

    @task(3)
    def readiness_check(self):
        self.client.get("/ready")

    @task(2)
    def get_metrics(self):
        self.client.get("/metrics")

    @task(1)
    def run_load_flow(self):
        self.client.post("/api/v1/studies/run", json={
            "study_type": "load_flow",
            "config": {
                "max_iterations": 100,
                "tolerance": 1e-6,
                "algorithm": "newton_raphson"
            }
        })

    @task(1)
    def validate_system(self):
        self.client.post("/api/v1/system/validate", json={
            "buses": [
                {"id": "BUS1", "nominal_kv": 13.8, "type": "swing"},
                {"id": "BUS2", "nominal_kv": 4.16, "type": "load"}
            ],
            "branches": [
                {"from_bus": "BUS1", "to_bus": "BUS2", "r": 0.01, "x": 0.05}
            ]
        })
