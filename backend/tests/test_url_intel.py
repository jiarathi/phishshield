from app.services.url_intel import score_url, risk_label

def test_score_url_shortener():
    intel = score_url("http://bit.ly/abc123")
    assert intel.domain in {"bit.ly"}
    assert intel.risk_score >= 0.50
    assert risk_label(intel.risk_score) in {"medium","high"}
