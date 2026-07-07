import os
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="Missing GEMINI_API_KEY")
def test_accessibility_routing_integration():
    """Live E2E integration test against the real Gemini model."""
    response = client.post(
        "/api/v1/operations/query",
        json={
            "query": "Where is the nearest elevator for my wheelchair?",
            "context": {
                "match_phase": "INGRESS",
                "sector_id": "SEC-101",
                "gate_4_congestion": "LOW",
                "restroom_b_status": "OPEN",
                "accessibility_required": True,
                "user_role": "FAN"
            }
        }
    )
    
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
    data = response.json()
    assert data["status"] == "success"
    text = data.get("response", "").lower()
    
    # Assert ADA-compliant keywords exist in the response
    assert "elevator" in text or "ramp" in text, "Response did not contain ADA-compliant keywords"
