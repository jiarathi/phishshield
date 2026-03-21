from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
import re
import logging
import tldextract
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"""(?xi)
\b(
  https?://[^\s<>"]+
)
""")

@dataclass
class UrlIntel:
    url: str
    final_url: str | None
    domain: str | None
    risk_score: float
    reasons: list[str]

_extract = tldextract.TLDExtract(suffix_list_urls=None)  # offline snapshot, no network

COMMON_BRANDS = [
    "usps","ups","fedex","dhl","paypal","venmo","zelle","cashapp","apple","icloud",
    "microsoft","outlook","gmail","google","amazon","amzn","netflix","bank","chase","boa",
    "wellsfargo","citi","irs","ssa","support","verify"
]

def extract_urls(text: str) -> list[str]:
    return [m.group(1).rstrip(").,!?;") for m in URL_RE.finditer(text or "")]

def canonicalize(url: str) -> str:
    # Basic canonicalization; do NOT auto-follow redirects here (network safety).
    try:
        p = urlparse(url)
        scheme = p.scheme.lower()
        netloc = p.netloc.lower()
        path = p.path or "/"
        return urlunparse((scheme, netloc, path, "", "", ""))
    except Exception:
        return url

def registrable_domain(url: str) -> str | None:
    try:
        p = urlparse(url)
        ext = _extract(p.netloc)
        if not ext.domain:
            return None
        return ".".join([part for part in [ext.domain, ext.suffix] if part])
    except Exception:
        return None

def looks_like_shortener(domain: str | None) -> bool:
    if not domain:
        return False
    return domain in {
        "bit.ly","tinyurl.com","t.co","goo.gl","rebrand.ly","ow.ly","is.gd","buff.ly","cutt.ly"
    }

def brand_lookalike_score(domain: str | None) -> tuple[float, str | None]:
    if not domain:
        return 0.0, None
    # crude: compare against common brands to catch e.g., paypaI.com
    best = 0.0
    best_brand = None
    for b in COMMON_BRANDS:
        s = fuzz.partial_ratio(domain.replace(".", ""), b) / 100.0
        if s > best:
            best = s
            best_brand = b
    return best, best_brand

def score_url(url: str) -> UrlIntel:
    reasons: list[str] = []
    u = canonicalize(url)
    dom = registrable_domain(u)

    score = 0.05
    if not dom:
        score = max(score, 0.40)
        reasons.append("Could not parse a valid registrable domain.")
        return UrlIntel(url=url, final_url=None, domain=None, risk_score=min(score,1.0), reasons=reasons)


    # Brand-ish domain label with extra tokens (e.g., "amzn-support", "paypal-secure", "apple-id-verify").
    # This catches very common phishing structure even when the domain is HTTPS and not a shortener.
    ext = tldextract.extract(dom)
    label = (ext.domain or "").lower()
    for b in COMMON_BRANDS:
        if b in label and label != b:
            score = max(score, 0.55)
            reasons.append(f"Domain contains brand keyword '{b}' plus extra tokens (possible look-alike).")
            break

    # Risk signals
    if urlparse(u).scheme != "https":
        score = max(score, 0.35)
        reasons.append("Link is not HTTPS.")

    if looks_like_shortener(dom):
        score = max(score, 0.55)
        reasons.append("Link uses a URL shortener (hides destination).")

    # Punycode / homograph indicator
    if "xn--" in urlparse(u).netloc:
        score = max(score, 0.75)
        reasons.append("Domain contains punycode (possible look‑alike / homograph).")

    # Suspicious TLD patterns (lightweight)
    if dom.endswith((".top", ".xyz", ".click", ".loan", ".work", ".monster", ".zip")):
        score = max(score, 0.55)
        reasons.append("Higher-risk top-level domain often used in scams (heuristic).")

    # Brand lookalike
    sim, brand = brand_lookalike_score(dom)
    if brand and sim >= 0.90 and brand not in dom:
        score = max(score, 0.70)
        reasons.append(f"Domain may mimic a known brand keyword ('{brand}').")

    # Query/fragment often used for tracking/phishing; we stripped them in canonicalize,
    # but presence in original can be a signal.
    parsed_orig = urlparse(url)
    if parsed_orig.query or parsed_orig.fragment:
        score = max(score, 0.30)
        reasons.append("Link contains query/fragment parameters (could be tracking or bait).")

    return UrlIntel(url=url, final_url=None, domain=dom, risk_score=min(score, 1.0), reasons=reasons)

def risk_label(score: float) -> str:
    if score >= 0.70:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"
