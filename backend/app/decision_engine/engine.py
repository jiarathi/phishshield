from .coherence import brand_domain_coherence
from .risk import compute_risk
from .explain import explain

def analyze_message(signals):
    coherence = brand_domain_coherence(signals)

    # DEBUG: print the exact inputs to the risk function
    print(
        "[DECISION_ENGINE] intent=", signals.intent,
        "has_url=", signals.has_url,
        "coherence=", round(coherence, 3),
        "text=", round(signals.text_score, 3),
        "url=", round(signals.url_score, 3),
        "reputation=", signals.reputation,
        flush=True
    )

    final_score = compute_risk(signals, coherence)

    if final_score >= 0.75:
        label = "HIGH"
    elif final_score >= 0.45:
        label = "MEDIUM"
    else:
        label = "LOW"

    return {
        "final_risk_score": round(final_score, 2),
        "final_risk_label": label,
        "coherence_score": round(coherence, 2),
        "explanations": explain(signals, coherence, final_score),
    }
