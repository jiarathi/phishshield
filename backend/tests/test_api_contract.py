from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_analyze_contract():
    r = client.post("/api/analyze", json={"text":"USPS: verify now http://bit.ly/abc"})
    assert r.status_code == 200
    data = r.json()
    # contract fields
    for k in ["risk_label","risk_score","is_scam","summary","reasons","actions","intent","url_findings","model"]:
        assert k in data
    assert isinstance(data["url_findings"], list)
