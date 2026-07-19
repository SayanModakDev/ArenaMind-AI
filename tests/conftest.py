import os
import pytest

# Ensure required environment variables are set before any application code (like config.py) is imported
os.environ.setdefault("GEMINI_API_KEY", "mock_key_for_testing")
os.environ.setdefault("FAN_AUTH_TOKEN", "mock-fan-token")
os.environ.setdefault("VOLUNTEER_AUTH_TOKEN", "mock-volunteer-token")
os.environ.setdefault("STAFF_AUTH_TOKEN", "mock-staff-token")

@pytest.fixture
def auth_token():
    return os.environ["FAN_AUTH_TOKEN"]
