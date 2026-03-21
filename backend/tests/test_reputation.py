from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_reputation_disabled_by_default():
    r = client.post("/api/analyze", json={"text": "hello http://example.com"})
    assert r.status_code == 200
    data = r.json()
    if data["url_findings"]:
        rep = data["url_findings"][0]["reputation"]
        assert rep["status"] in ("unknown", "error", "clean", "malicious")
        # Default config should not perform outbound checks.
        assert rep["provider"] in ("none", "multi")
