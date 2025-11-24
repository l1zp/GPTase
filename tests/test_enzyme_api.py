import pytest
from fastapi.testclient import TestClient
from src.web.app import create_app

def test_enzyme_extract_endpoint():
    app = create_app()
    client = TestClient(app)
    payload = {
        "document": {"source_type": "text", "content": "computational design; kinetic assay; directed evolution"}
    }
    r = client.post("/api/enzyme/extract", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert "data" in data
