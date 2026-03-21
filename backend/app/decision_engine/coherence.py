HIGH_RISK_TLDS = {'xyz','info','top','click','support'}

def brand_domain_coherence(signals) -> float:
    if not signals.brand or not signals.domain:
        return 0.5
    score = 1.0
    score -= min(signals.edit_distance * 0.15, 0.6)
    score -= (1 - signals.brand_token_overlap) * 0.4
    if signals.tld and signals.tld.lower() in HIGH_RISK_TLDS:
        score -= 0.2
    if signals.domain_length > 20:
        score -= 0.1
    return max(0.0, min(score, 1.0))
