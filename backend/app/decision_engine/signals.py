from dataclasses import dataclass
from typing import Optional

@dataclass
class DetectionSignals:
    brand: Optional[str]
    intent: Optional[str]
    intent_confidence: float
    has_url: bool
    domain: Optional[str]
    brand_token_overlap: float
    edit_distance: int
    tld: Optional[str]
    domain_length: int
    text_score: float
    url_score: float
    reputation: str
