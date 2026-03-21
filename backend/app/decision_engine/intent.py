INTENT_RISK_CLASS = {
    'login': 'high',
    'verify': 'high',
    'otp': 'high',
    'payment': 'high',
    'account_lock': 'high',
    'shipping': 'low',
    'informational': 'low',
    'notification': 'low',
}

INTENT_MULTIPLIER = {
    'login': 1.8,
    'verify': 1.6,
    'otp': 1.8,
    'payment': 2.0,
    'account_lock': 1.7,
    'shipping': 1.05,
    'informational': 0.95,
    'notification': 1.0,
}
