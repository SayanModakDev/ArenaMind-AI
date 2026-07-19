import os
import pytest

# Ensure required environment variables are set before any application code (like config.py) is imported
os.environ.setdefault("GEMINI_API_KEY", "mock_key_for_testing")
os.environ.setdefault("STADIUM_AUTH_TOKEN", "mock-token-for-tests")

@pytest.fixture
def auth_token():
    return os.environ["STADIUM_AUTH_TOKEN"]
