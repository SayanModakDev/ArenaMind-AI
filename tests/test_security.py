import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_query_endpoint_missing_auth():
    payload = {
        "query": "Where is the nearest restroom?",
        "context": {
            "match_phase": "PRE_MATCH",
            "sector_id": "100",
            "gates": {"GATE_4": "NORMAL"},
            "facilities": {"RESTROOM_B": "OPERATIONAL"},
            "accessibility_required": False,
        }
    }
    # No X-Stadium-Auth header provided
    response = client.post("/api/v1/operations/query", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing X-Stadium-Auth token"

def test_stream_endpoint_missing_auth():
    payload = {
        "query": "Where is the nearest restroom?",
        "context": {
            "match_phase": "PRE_MATCH",
            "sector_id": "100",
            "gates": {"GATE_4": "NORMAL"},
            "facilities": {"RESTROOM_B": "OPERATIONAL"},
            "accessibility_required": False,
        }
    }
    # No X-Stadium-Auth header provided
    response = client.post("/api/v1/operations/stream", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing X-Stadium-Auth token"



def test_rbac_fan_denied_security():
    payload = {
        "query": "Where is the security camera blind spot?",
        "context": {}
    }
    response = client.post("/api/v1/operations/query", json=payload, headers={"X-Stadium-Auth": os.environ["FAN_AUTH_TOKEN"]})
    assert response.status_code == 403
    assert response.json()["detail"] == "Security clearance denied."

def test_rbac_staff_allowed_security():
    payload = {
        "query": "Where is the security camera blind spot?",
        "context": {}
    }
    with patch('agents.operational_brain.OperationalBrain.generate_response') as mock_gen:
        mock_gen.return_value = 'Staff response'
        response = client.post("/api/v1/operations/query", json=payload, headers={"X-Stadium-Auth": os.environ["STAFF_AUTH_TOKEN"]})
        assert response.status_code == 200

def test_invalid_token_rejected():
    payload = {
        "query": "Where is the restroom?",
        "context": {}
    }
    response = client.post("/api/v1/operations/query", json=payload, headers={"X-Stadium-Auth": "invalid-token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing X-Stadium-Auth token"
