import pytest
from fastapi.testclient import TestClient

from venus_api.app.main import app


@pytest.fixture
def client() -> TestClient:
	return TestClient(app)
