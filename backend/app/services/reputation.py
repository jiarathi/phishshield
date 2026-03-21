from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_HOSTS = {
    "safebrowsing.googleapis.com",
    "www.virustotal.com",
}

@dataclass
class ReputationResult:
    provider: str  # "multi" / "gsb" / "virustotal" / "none"
    status: str    # "clean" | "malicious" | "unknown" | "error"
    details: dict[str, Any]

def _outbound_enabled() -> bool:
    return bool(settings.enable_reputation_lookups)

def _safe_host(url: str) -> bool:
    try:
        host = httpx.URL(url).host
        return host in ALLOWED_HOSTS
    except Exception:
        return False

class ReputationClient:
    """Optional outbound reputation checks (disabled by default).

    Safety design:
    - Controlled by settings.enable_reputation_lookups
    - Requires keys
    - Uses short timeouts
    - Never raises (non-fatal), returns status="unknown"/"error"
    """

    def __init__(self) -> None:
        self.timeout = settings.http_timeout_seconds

    async def check(self, url: str) -> ReputationResult:
        if not _outbound_enabled():
            return ReputationResult(provider="none", status="unknown", details={"enabled": False})

        gsb_key = settings.google_safe_browsing_api_key
        vt_key = settings.virustotal_api_key

        if not gsb_key and not vt_key:
            return ReputationResult(provider="none", status="unknown", details={"enabled": True, "reason": "no_keys"})

        details: dict[str, Any] = {"enabled": True, "sources": {}}
        statuses: list[str] = []

        if gsb_key:
            st, det = await self._check_google_safe_browsing(url, gsb_key)
            details["sources"]["gsb"] = {"status": st, "details": det}
            statuses.append(st)

        if vt_key:
            st, det = await self._check_virustotal(url, vt_key)
            details["sources"]["virustotal"] = {"status": st, "details": det}
            statuses.append(st)

        # Combine statuses conservatively.
        if "malicious" in statuses:
            combined = "malicious"
        elif statuses and all(s == "clean" for s in statuses):
            combined = "clean"
        elif "error" in statuses and all(s in ("error", "unknown") for s in statuses):
            combined = "error"
        else:
            combined = "unknown"

        return ReputationResult(provider="multi", status=combined, details=details)

    async def _check_google_safe_browsing(self, url: str, key: str) -> tuple[str, dict[str, Any]]:
        try:
            target = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
            if not _safe_host(target):
                return "error", {"error": "blocked_host"}

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{target}?key={key}",
                    json={
                        "client": {"clientId": "phishshield", "clientVersion": "1.0.0"},
                        "threatInfo": {
                            "threatTypes": [
                                "MALWARE",
                                "SOCIAL_ENGINEERING",
                                "UNWANTED_SOFTWARE",
                                "POTENTIALLY_HARMFUL_APPLICATION",
                            ],
                            "platformTypes": ["ANY_PLATFORM"],
                            "threatEntryTypes": ["URL"],
                            "threatEntries": [{"url": url}],
                        },
                    },
                )
                data = resp.json()
                matches = data.get("matches") or []
                if matches:
                    return "malicious", {"matches_count": len(matches)}
                return "clean", {}
        except Exception as e:
            logger.info("GSB check failed (non-fatal)")
            return "error", {"error": str(e)}

    async def _check_virustotal(self, url: str, key: str) -> tuple[str, dict[str, Any]]:
        """VirusTotal v3 URL scan / lookup.

        Flow:
          1) POST /api/v3/urls with form url=<url> -> returns data.id
          2) GET  /api/v3/urls/{id} -> returns last_analysis_stats
        """
        try:
            post_target = "https://www.virustotal.com/api/v3/urls"
            if not _safe_host(post_target):
                return "error", {"error": "blocked_host"}

            headers = {"x-apikey": key}
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                post_resp = await client.post(post_target, data={"url": url})
                post_data = post_resp.json()
                vt_id = (post_data.get("data") or {}).get("id")
                if not vt_id:
                    return "unknown", {"note": "no_id_returned"}

                get_target = f"https://www.virustotal.com/api/v3/urls/{vt_id}"
                if not _safe_host(get_target):
                    return "error", {"error": "blocked_host"}

                get_resp = await client.get(get_target)
                data = get_resp.json()
                attrs = ((data.get("data") or {}).get("attributes") or {})
                stats = attrs.get("last_analysis_stats") or {}
                malicious = int(stats.get("malicious", 0) or 0)
                suspicious = int(stats.get("suspicious", 0) or 0)

                # Conservative: treat any confirmed malicious as malicious.
                if malicious >= 1:
                    return "malicious", {"last_analysis_stats": stats}
                if suspicious >= 3:
                    # Many engines suspicious is also meaningful; keep conservative threshold.
                    return "malicious", {"last_analysis_stats": stats, "note": "high_suspicious_count"}
                return "clean", {"last_analysis_stats": stats}
        except Exception as e:
            logger.info("VT check failed (non-fatal)")
            return "error", {"error": str(e)}
