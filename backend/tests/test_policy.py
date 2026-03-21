from app.services.policy import apply_policy

def test_policy_high_intent_plus_url():
    res = apply_policy(text_score=0.10, max_url_score=0.40, intent_category="credential_theft", intent_conf=0.70)
    assert res.override_label == "high"
    assert res.override_score is not None
