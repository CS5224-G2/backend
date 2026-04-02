import uuid
from locust import HttpUser, task, between, events

class CycleLinkUser(HttpUser):
    # Simulate a user waiting between 1 to 5 seconds between actions
    wait_time = between(1, 5)

    @task(5)
    def check_health(self):
        """Simulate a basic health check (very lightweight)"""
        self.client.get("/health", name="Health Check")

    @task(10)
    def get_popular_routes(self):
        """Simulate users browsing the 'Popular' page (Cached at Edge/Redis)"""
        with self.client.get("/v1/routes/popular?limit=3", name="Browse Popular Routes", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Popular routes failed with {response.status_code}")

    @task(2)
    def generate_complex_route(self):
        """
        The 'Heavy' Task: Simulate a user requesting a custom route suggestion.
        This triggers:
        1. Fargate CPU (Graph Traversal)
        2. ElastiCache (POI Lookups)
        3. RDS (User History)
        4. S3 (GPX Generation)
        """
        payload = {
            "origin": {"lat": 1.3521, "lng": 103.8198}, # central SG
            "destination": {"lat": 1.2902, "lng": 103.8519}, # Downtown
            "preferences": {
                "include_hawker_centres": True,
                "include_parks": True,
                "include_historic_sites": False,
                "include_tourist_attractions": True
            },
            "waypoints": []
        }
        
        headers = {"Content-Type": "application/json"}
        
        # We capture the full journey of the POST request
        with self.client.post("/v1/route-suggestion/recommend", 
                             json=payload, 
                             headers=headers,
                             name="Generate Custom Route",
                             catch_response=True) as response:
            if response.status_code == 200:
                # If path exists, it means the heavy calculation finished successfully
                data = response.json()
                if not data.get("path"):
                    response.failure("Route generated but path is empty")
            else:
                response.failure(f"Route calculation failed: {response.text}")

# Optional: Log the results when the test stops
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print(f"\n--- Load Test for {environment.host} Completed ---")
