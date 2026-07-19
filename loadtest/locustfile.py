import os
from locust import HttpUser, task, between

class ArenaMindUser(HttpUser):
    # Simulate realistic fan think-time (1-5 seconds between requests)
    wait_time = between(1, 5)

    def on_start(self):
        """Called when a Locust user starts before any task is scheduled."""
        # Read token from environment, default to an empty string to trigger 401s if not set
        self.auth_token = os.environ.get("FAN_AUTH_TOKEN", "mock-fan-token")
        self.headers = {
            "X-Stadium-Auth": self.auth_token,
            "Content-Type": "application/json"
        }
        self.base_payload = {
            "query": "Where is the nearest accessible restroom to Section 101?",
            "context": {
                "match_phase": "INGRESS",
                "sector_id": "SEC-101",
                "gates": {"GATE_4": "MODERATE", "GATE_7": "LOW"},
                "facilities": {"RESTROOM_B": "OPEN", "FIRST_AID_2": "STAFFED"},
                "accessibility_required": True
            }
        }

    @task(3)
    def query_blocking(self):
        """Exercise the standard blocking API endpoint."""
        with self.client.post(
            "/api/v1/operations/query",
            json=self.base_payload,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.success() # Rate limiting is expected under load
            elif response.status_code == 401:
                response.failure("Unauthorized - check FAN_AUTH_TOKEN environment variable")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task(1)
    def query_streaming(self):
        """Exercise the SSE streaming endpoint (less frequently than blocking)."""
        with self.client.post(
            "/api/v1/operations/stream",
            json=self.base_payload,
            headers=self.headers,
            stream=True,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                # Read the stream chunks to completion
                try:
                    for _ in response.iter_lines():
                        pass
                    response.success()
                except Exception as e:
                    response.failure(f"Stream interrupted: {e}")
            elif response.status_code == 429:
                response.success() # Rate limiting is expected
            elif response.status_code == 401:
                response.failure("Unauthorized - check FAN_AUTH_TOKEN environment variable")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
