def explain(signals, coherence, final_score):
    reasons = []
    if signals.has_url and coherence < 0.35:
        reasons.append("The message claims to represent a brand, but the link does not closely match that brand's real web presence.")
    if signals.intent in {"login", "verify", "otp", "payment", "account_lock"}:
        reasons.append("The message asks you to take a sensitive account or payment-related action.")
    if signals.has_url and signals.reputation == "unknown":
        reasons.append("The destination of the link is not a well-established or widely recognized site.")
    if not reasons:
        reasons.append("The message content and link are consistent with a low-risk informational notification.")
    return reasons
