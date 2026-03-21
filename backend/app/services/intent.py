from __future__ import annotations
import re

# NOTE: The decision engine expects intents like: login, verify, otp, payment, account_lock, shipping, informational, notification.
# This service therefore emits those same categories to avoid taxonomy mismatches.
INTENT_RULES: list[tuple[str, str, list[str]]] = [
    ("otp", r"\b(otp|one[- ]time|verification code|2fa|auth code)\b", ["Asks for verification codes"]),
    ("payment", r"\b(pay|payment|wire|gift ?card|bitcoin|crypto|zelle|venmo|cashapp|transfer)\b", ["Asks for money/transfer"]),
    ("account_lock", r"\b(account (?:locked|suspended)|unusual activity|security alert)\b", ["Account security pressure"]),
    ("verify", r"\b(verify|confirm|validate)\b", ["Verification request"]),
    ("login", r"\b(log ?in|sign ?in|password reset|reset your password)\b", ["Login / credential flow"]),
    ("shipping", r"\b(order|package|delivery|shipment|tracking|track|delayed|arriv(?:e|ing))\b", ["Shipping / delivery context"]),
]

def detect_intent(text: str) -> tuple[str, float, list[str]]:
    t = (text or "").lower()
    matched: list[tuple[str, list[str]]] = []
    for cat, pat, sig in INTENT_RULES:
        if re.search(pat, t, flags=re.IGNORECASE):
            matched.append((cat, sig))
    if not matched:
        return "unknown", 0.25, []

    # If multiple, pick highest priority by list order; boost confidence with count.
    cat, _ = matched[0]
    confidence = min(0.95, 0.55 + 0.15 * (len(matched) - 1))

    signals: list[str] = []
    for _, s in matched:
        signals.extend(s)

    # Deduplicate
    signals = list(dict.fromkeys(signals))
    return cat, confidence, signals
