from __future__ import annotations
import asyncio
import logging
import re
from typing import Optional, Tuple

import tldextract
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from app.core.config import settings
from app.schemas import AnalyzeResponse, IntentInfo, UrlFinding, ReputationInfo, ModelInfo
from app.services.text_model import TextModel
from app.services.url_intel import extract_urls, score_url, risk_label
from app.services.intent import detect_intent
from app.services.reputation import ReputationClient

from app.decision_engine.engine import analyze_message
from app.decision_engine.signals import DetectionSignals

logger = logging.getLogger(__name__)

_extract = tldextract.TLDExtract(suffix_list_urls=None)  # offline snapshot, no network

# Generic tokenization for "claimed brand/entity" inference without whitelists.
_WORD_RE = re.compile(r"[a-zA-Z0-9]{3,}")

def _infer_brand_token(text: str, domain: Optional[str]) -> Optional[str]:
    """Infer a likely claimed entity token from the message, without a static brand list.

    Strategy:
      - If no domain, return None (coherence will be neutral).
      - Tokenize text, ignore short tokens.
      - Score tokens by similarity to the domain (partial ratio) and token length.
      - Return best token if it beats a conservative threshold.
    """
    if not domain:
        return None
    dom_key = domain.replace(".", "").lower()
    tokens = [t.lower() for t in _WORD_RE.findall(text or "")]
    # Remove very generic tokens that frequently appear but carry little entity info.
    stop = {"your","account","support","service","secure","verify","update","alert","delivery","package","tracking","track","help","customer"}
    cand = [t for t in tokens if t not in stop and len(t) >= 4]
    if not cand:
        return None

    best_tok = None
    best_score = 0.0
    for tok in cand:
        s = fuzz.partial_ratio(dom_key, tok) / 100.0
        # Slightly favor longer, more specific tokens.
        s = s * (1.0 + min(0.3, (len(tok) - 4) * 0.05))
        if s > best_score:
            best_score = s
            best_tok = tok

    # Require a minimum match to avoid hallucinating a "brand".
    return best_tok if best_score >= 0.60 else None

def _domain_features(domain: Optional[str], brand: Optional[str]) -> Tuple[float, int, Optional[str], int]:
    """Compute relationship features for the decision engine."""
    if not domain:
        return 0.0, 99, None, 0

    ext = _extract(domain)
    tld = ext.suffix or (domain.split(".")[-1] if "." in domain else None)
    domain_len = len(domain.replace(".", ""))

    if not brand:
        return 0.0, 99, tld, domain_len

    # Use registrable label (domain part) for edit distance.
    label = ext.domain or domain.split(".")[0]
    edit = int(Levenshtein.distance(brand.lower(), label.lower()))

    # Token overlap as similarity score (0..1). This is relationship-based, not a whitelist.
    overlap = fuzz.partial_ratio(domain.replace(".", "").lower(), brand.lower()) / 100.0
    return float(overlap), edit, tld, domain_len

class AnalyzerService:
    def __init__(self) -> None:
        self.text_model = TextModel()
        self.rep = ReputationClient()
        self._sem = asyncio.Semaphore(5)  # cap concurrent outbound checks

    async def _score_one_url(self, url: str) -> UrlFinding:
        intel = score_url(url)

        # Optional outbound reputation checks (disabled by default)
        rep_status = "unknown"
        rep_provider = "none"
        rep_details = {"enabled": settings.enable_reputation_lookups}

        if settings.enable_reputation_lookups and (settings.google_safe_browsing_api_key or settings.virustotal_api_key):
            async with self._sem:
                rep = await self.rep.check(url)
            rep_status = rep.status
            rep_provider = rep.provider
            rep_details = rep.details

            # If a reputation source says malicious, force URL risk high.
            if rep_status == "malicious":
                intel.risk_score = max(float(intel.risk_score), 1.0)
                intel.reasons.append("Reputation sources flagged this URL as malicious.")
            elif rep_status == "clean":
                intel.reasons.append("Reputation sources did not flag this URL (clean).")
            elif rep_status == "error":
                intel.reasons.append("Reputation lookup errored; treated as unknown (non-fatal).")

        return UrlFinding(
            url=url,
            final_url=intel.final_url,
            domain=intel.domain,
            risk_label=risk_label(float(intel.risk_score)),
            risk_score=float(intel.risk_score),
            reasons=intel.reasons,
            reputation=ReputationInfo(provider=rep_provider, status=rep_status, details=rep_details),
        )

    async def analyze(self, text: str) -> AnalyzeResponse:
        text = (text or "").strip() or ""

        # 1) Text model probability (calibrated)
        p_scam = float(self.text_model.predict_proba(text))

        # 2) Intent extraction (used as context, not as hard rules)
        intent_cat, intent_conf, intent_signals = detect_intent(text)

        # 3) URL intel + optional reputation
        urls = extract_urls(text)[: settings.max_urls_per_message]
        url_findings: list[UrlFinding] = []
        max_url_score = 0.0
        primary_domain: Optional[str] = None
        primary_rep: str = "unknown"

        if urls:
            url_findings = await asyncio.gather(*[self._score_one_url(u) for u in urls])
            max_url_score = max((u.risk_score for u in url_findings), default=0.0)

            # Choose the domain of the riskiest URL as the "primary" relationship anchor.
            riskiest = max(url_findings, key=lambda u: u.risk_score)
            primary_domain = riskiest.domain
            if riskiest.reputation:
                primary_rep = riskiest.reputation.status or "unknown"

        # 4) Relationship-based decision engine (no whitelists)
        brand = _infer_brand_token(text, primary_domain)
        overlap, edit_dist, tld, domain_len = _domain_features(primary_domain, brand)

        signals = DetectionSignals(
            brand=brand,
            intent=intent_cat if intent_cat != "unknown" else None,
            intent_confidence=float(intent_conf),
            has_url=bool(urls),
            domain=primary_domain,
            brand_token_overlap=float(overlap),
            edit_distance=int(edit_dist),
            tld=tld,
            domain_length=int(domain_len),
            text_score=float(p_scam),
            url_score=float(max_url_score),
            reputation=("malicious" if primary_rep == "malicious" else "safe" if primary_rep == "clean" else "unknown"),
        )

        decision = analyze_message(signals)
        final_score = float(decision["final_risk_score"])
        # decision label is LOW/MEDIUM/HIGH; API expects lowercase.
        final_label = str(decision["final_risk_label"]).lower()

        # 5) Reasons/explanations
        reasons: list[str] = []
        reasons.append(f"Text model score={p_scam:.2f} (calibrated probability estimate).")
        if urls:
            reasons.append(f"Detected {len(urls)} link(s); max URL risk={max_url_score:.2f}.")
        if intent_cat != "unknown":
            reasons.append(f"Detected intent: {intent_cat} (confidence={intent_conf:.2f}).")
        # Relationship engine transparency
        reasons.append(f"Brand–domain coherence score={float(decision.get('coherence_score', 0.0)):.2f}.")
        for r in decision.get("explanations", []):
            reasons.append(str(r))

        is_scam = final_label == "high" or final_score >= float(settings.scam_threshold)

        summary = {
            "low": "Likely safe based on current signals, but stay cautious with unexpected messages.",
            "medium": "Suspicious. Verify independently before clicking or sharing information.",
            "high": "High risk. Do not engage; verify via official channels and consider reporting.",
        }[final_label]

        actions = [
            "Do not click links or reply if the message was unexpected.",
            "Type the official website address yourself (do not use the link).",
            "If it claims to be your bank or a service provider, call the number on the back of your card or in the official app.",
            "Forward suspicious SMS to 7726 (SPAM) in the US, if applicable.",
            "Report scams at ReportFraud.ftc.gov (US).",
        ]

        return AnalyzeResponse(
            risk_label=final_label,  # type: ignore
            risk_score=float(max(0.0, min(1.0, final_score))),
            is_scam=bool(is_scam),
            summary=summary,
            reasons=reasons,
            actions=actions,
            intent=IntentInfo(category=intent_cat, confidence=float(intent_conf), signals=intent_signals),
            url_findings=url_findings,
            model=ModelInfo(
                name=self.text_model.meta.name,
                version=self.text_model.meta.version,
                threshold=float(settings.scam_threshold),
            ),
        )
