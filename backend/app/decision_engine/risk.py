# backend/app/decision_engine/risk.py

from .intent import INTENT_MULTIPLIER, INTENT_RISK_CLASS


def compute_risk(signals, coherence: float) -> float:
    """
    Coherence-based risk with intent conditioning.

    Key behaviors:
    - High-risk intents (login/verify/payment/otp) amplify uncertainty.
    - Low-risk intents (shipping/info) tolerate uncertainty ONLY when there is NO URL.
    - Shipping + URL requires stronger coherence; weak coherence escalates.
    """

    # Base relational risk
    # Only include coherence component when a URL is actually present.
    # Without a URL, coherence defaults to 0.5 (neutral) which would
    # incorrectly contribute 0.15 to the score for link-free messages.
    coherence_component = 0.3 * (1.0 - float(coherence)) if bool(signals.has_url) else 0.0
    base = (
        0.4 * float(signals.text_score) +
        0.3 * float(signals.url_score) +
        coherence_component
    )

    # Intent-weighted amplification
    multiplier = float(INTENT_MULTIPLIER.get(signals.intent, 1.2))
    risk = min(base * multiplier, 1.0)

    intent_risk = INTENT_RISK_CLASS.get(signals.intent, "high")

    # --- Escalation rule: shipping + URL + weak coherence is dangerous ---
    # Rationale: a "track your package" link is a common phishing vector.
    # If coherence is not strong, escalate even if text is mild.
    if signals.intent == "shipping" and bool(signals.has_url):
        if coherence < 0.60:
            risk = max(risk, 0.75)  # force into HIGH band

    # --- Low-risk tolerance: ONLY for low-risk intents with NO URL ---
    # Keeps legit, link-free informational messages LOW.
    if intent_risk == "low" and (not bool(signals.has_url)) and coherence >= 0.75:
        risk = min(risk, 0.30)

    return float(min(max(risk, 0.0), 1.0))
