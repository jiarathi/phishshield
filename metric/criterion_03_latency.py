#!/usr/bin/env python3
"""
Design Criterion 3: System Speed — median analysis time < 500 ms.

Measures end-to-end analysis latency by calling the PhishShield API.
Kept separate from product code; requires the backend to be running.

Usage:
  1. Start the backend: cd backend && uvicorn app.main:app --reload
  2. Run this script: python metric/criterion_03_latency.py [--base-url URL] [--n N]

  Optional:
    --base-url  Base API URL (default: http://localhost:8000)
    --n         Number of analyses to run (default: 200, per research plan)
    --delay     Seconds to wait between requests (default: 6.0; avoids 429 rate limit)
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
import urllib.error

# Default test messages (cycled to reach --n runs). Mix of lengths and content.
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

TARGET_MEDIAN_MS = 500
DEFAULT_N = 200
DEFAULT_BASE_URL = "http://localhost:8000"


def analyze_once(base_url: str, text: str) -> tuple[float, int | None]:
    """
    Call POST /api/analyze and return (client_elapsed_sec, server_ms or None).
    """
    url = f"{base_url.rstrip('/')}/api/analyze"
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed_sec = time.perf_counter() - start
            server_ms = None
            if "X-Response-Time-ms" in resp.headers:
                try:
                    server_ms = int(resp.headers["X-Response-Time-ms"])
                except (ValueError, TypeError):
                    pass
            return elapsed_sec, server_ms
    except urllib.error.HTTPError as e:
        elapsed_sec = time.perf_counter() - start
        # Still count the attempt; use client time
        raise RuntimeError(f"API returned {e.code} after {elapsed_sec*1000:.0f} ms: {e.read().decode()}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach API at {url}: {e.reason}. Is the backend running?") from e


def main() -> int:
    parser = argparse.ArgumentParser(description="Criterion 3: median analysis time < 500 ms")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base API URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=DEFAULT_N,
        help=f"Number of analyses to run (default: {DEFAULT_N})",
    )
    parser.add_argument(
        "--use-server-header",
        action="store_true",
        help="Use X-Response-Time-ms from server (default: use client elapsed time)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=6.0,
        metavar="SEC",
        help="Seconds to wait between requests to avoid rate limit (default: 6.0)",
    )
    args = parser.parse_args()

    if args.n < 1:
        print("Error: --n must be at least 1", file=sys.stderr)
        return 2

    base_url = args.base_url.rstrip("/")
    print(f"Criterion 3: System speed (median < {TARGET_MEDIAN_MS} ms)")
    print(f"  Base URL: {base_url}")
    print(f"  Runs: {args.n}")
    print(f"  Delay between requests: {args.delay} s (avoids rate limit)")
    print(f"  Time source: {'server (X-Response-Time-ms)' if args.use_server_header else 'client elapsed'}")
    print()

    times_ms: list[float] = []
    server_times_ms: list[float] = []

    for i in range(args.n):
        msg = _SAMPLE_MESSAGES[i % len(_SAMPLE_MESSAGES)]
        try:
            elapsed_sec, server_ms = analyze_once(base_url, msg)
            client_ms = elapsed_sec * 1000
            times_ms.append(client_ms)
            if server_ms is not None:
                server_times_ms.append(float(server_ms))
        except RuntimeError as e:
            print(f"Run {i + 1}/{args.n} failed: {e}", file=sys.stderr)
            return 2
        if (i + 1) % 50 == 0:
            print(f"  Completed {i + 1}/{args.n} runs...")
        # Wait between requests to stay under backend rate limit (default 60/min)
        if args.delay > 0 and i < args.n - 1:
            time.sleep(args.delay)

    # Use client times by default; if --use-server-header and we have them, use server times
    if args.use_server_header and len(server_times_ms) == len(times_ms):
        used = server_times_ms
        label = "Server (X-Response-Time-ms)"
    else:
        used = times_ms
        label = "Client elapsed"

    median_ms = statistics.median(used)
    passed = median_ms < TARGET_MEDIAN_MS

    print()
    print(f"  {label}:")
    print(f"    Median: {median_ms:.1f} ms")
    print(f"    Min:    {min(used):.1f} ms")
    print(f"    Max:    {max(used):.1f} ms")
    if len(used) >= 2:
        print(f"    Mean:   {statistics.mean(used):.1f} ms")
    print()
    print(f"  Criterion 3 (median < {TARGET_MEDIAN_MS} ms): {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
