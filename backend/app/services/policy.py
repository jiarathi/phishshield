from __future__ import annotations
from dataclasses import dataclass

@dataclass
class PolicyResult:
    override_score: float | None
    override_label: str | None
    reasons: list[str]
    actions: list[str]

DEFAULT_ACTIONS = [
    "Do not click links or reply if the message was unexpected.",
    "Type the official website address yourself (do not use the link).",
    "If it claims to be your bank or a service provider, call the number on the back of your card or in the official app.",
    "Forward suspicious SMS to 7726 (SPAM) in the US, if applicable.",
    "Report scams at ReportFraud.ftc.gov (US).",
]

def apply_policy(text_score: float, max_url_score: float, intent_category: str, intent_conf: float) -> PolicyResult:
    reasons: list[str] = []
    actions = DEFAULT_ACTIONS.copy()

    # Guardrail: high intent + any medium/high URL risk => high
    if intent_category in {"credential_theft", "payment_request", "account_takeover"} and intent_conf >= 0.55:
        if max_url_score >= 0.35:
            reasons.append("High-risk intent combined with a suspicious link.")
            return PolicyResult(override_score=0.90, override_label="high", reasons=reasons, actions=actions)

    # Guardrail: URL is strongly suspicious (shortener + non-https / punycode / high tld)
    if max_url_score >= 0.70:
        reasons.append("Link has high-risk characteristics.")
        return PolicyResult(override_score=0.85, override_label="high", reasons=reasons, actions=actions)

    # If model is low but intent looks like impersonation, raise to medium
    if text_score < 0.35 and intent_category in {"impersonation", "account_takeover"} and intent_conf >= 0.55:
        reasons.append("Message resembles common impersonation/social-engineering patterns.")
        return PolicyResult(override_score=0.55, override_label="medium", reasons=reasons, actions=actions)

    return PolicyResult(override_score=None, override_label=None, reasons=[], actions=actions)
