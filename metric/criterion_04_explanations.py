#!/usr/bin/env python3
"""
Design Criterion 4: Explanation clarity — at least one plain-language reason per warning.

Checks that each analysis response includes at least one clear, plain-language explanation
(e.g. "punycode domain," "IP-based URL," "look-alike domain"). Uses the PhishShield API;
kept separate from product code.

Usage:
  1. Start the backend: cd backend && uvicorn app.main:app --reload
  2. Run: python metric/criterion_04_explanations.py [--base-url URL] [--delay SEC]

  Optional:
    --base-url  Base API URL (default: http://localhost:8000)
    --delay     Seconds between requests (default: 6.0; avoids rate limit)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

# Test messages chosen to get a mix of risk levels and URL/no-URL (so we exercise reasons).
_SAMPLE_MESSAGES = [
    "Your package is ready for pickup. Track here: https://example.com/track/123",
    "URGENT: Your bank account has been locked. Verify at https://secure-bank.com/verify",
    "Hi, just checking in. Can you send me the report by EOD?",
    "You've won a $1000 gift card! Claim now: http://prizes.xyz/claim",
    "Your delivery will arrive tomorrow. No link, just a heads up.",
    "Click here to reset your password: https://login-service.com/reset?id=abc",
    "Mom: Can you pick up milk on your way home?",
    "FedEx: Your shipment 1Z999AA10123456784 has been delivered.",
    "Your Apple ID was used to sign in. If this wasn't you: https://apple-id.secure.com",
    "Reminder: Your appointment is tomorrow at 10am. Reply YES to confirm.",
]

DEFAULT_BASE_URL = "http://localhost:8000"


def is_plain_language(s: str) -> bool:
    """True if the string looks like a plain-language explanation (not just a number/code)."""
    s = (s or "").strip()
    if len(s) < 10:
        return False
    return any(c.isalpha() for c in s)


def analyze(base_url: str, text: str) -> dict:
    """Call POST /api/analyze and return the response JSON."""
    url = f"{base_url.rstrip('/')}/api/analyze"
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API returned {e.code}: {e.read().decode()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach API at {url}: {e.reason}. Is the backend running?") from e


def response_has_plain_language_reason(response: dict) -> tuple[bool, str]:
    """
    Check that the response has at least one plain-language reason.
    Returns (passed, detail_string).
    """
    reasons = response.get("reasons") or []
    if not reasons:
        return False, "no reasons in response"
    plain = [r for r in reasons if is_plain_language(r)]
    if not plain:
        return False, f"reasons present but none plain-language (count={len(reasons)})"
    return True, f"ok ({len(plain)} plain-language reason(s))"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Criterion 4: at least one plain-language reason per response"
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base API URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=6.0,
        metavar="SEC",
        help="Seconds between requests (default: 6.0)",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    n = len(_SAMPLE_MESSAGES)

    print("Criterion 4: Explanation clarity (at least one plain-language reason)")
    print(f"  Base URL: {base_url}")
    print(f"  Test messages: {n}")
    print(f"  Delay between requests: {args.delay} s")
    print()

    passed = 0
    failed_details: list[tuple[int, str, str]] = []  # (index, message_preview, detail)

    for i, text in enumerate(_SAMPLE_MESSAGES):
        try:
            response = analyze(base_url, text)
        except RuntimeError as e:
            print(f"  Request {i + 1}/{n} failed: {e}", file=sys.stderr)
            return 2
        ok, detail = response_has_plain_language_reason(response)
        if ok:
            passed += 1
        else:
            preview = (text[:50] + "…") if len(text) > 50 else text
            failed_details.append((i + 1, preview, detail))
        if args.delay > 0 and i < n - 1:
            time.sleep(args.delay)

    print(f"  Responses with ≥1 plain-language reason: {passed}/{n}")
    if failed_details:
        print()
        for idx, preview, detail in failed_details:
            print(f"  Failed {idx}: {detail}")
            print(f"    Message: {preview}")
        print()
        print("  Criterion 4 (at least one plain-language reason per response): FAIL")
        return 1
    print()
    print("  Criterion 4 (at least one plain-language reason per response): PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
