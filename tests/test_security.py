from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_query_endpoint_missing_auth():
    payload = {
        "query": "Where is the nearest restroom?",
        "context": {
            "match_phase": "PRE_MATCH",
            "sector_id": "100",
            "gate_4_congestion": "NORMAL",
            "restroom_b_status": "OPERATIONAL",
            "accessibility_required": False,
            "user_role": "STAFF"
        }
    }
    # No X-Stadium-Auth header provided
    response = client.post("/api/v1/operations/query", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

def test_stream_endpoint_missing_auth():
    payload = {
        "query": "Where is the nearest restroom?",
        "context": {
            "match_phase": "PRE_MATCH",
            "sector_id": "100",
            "gate_4_congestion": "NORMAL",
            "restroom_b_status": "OPERATIONAL",
            "accessibility_required": False,
            "user_role": "STAFF"
        }
    }
    # No X-Stadium-Auth header provided
    response = client.post("/api/v1/operations/stream", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
