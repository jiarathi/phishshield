
from pydantic import BaseModel, Field
from typing import Any, Literal

RiskLabel = Literal["low", "medium", "high"]

class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)

class IntentInfo(BaseModel):
    category: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    signals: list[str]

class ReputationInfo(BaseModel):
    provider: str
    status: Literal["clean", "malicious", "unknown", "error"]
    details: dict[str, Any]

class UrlFinding(BaseModel):
    url: str
    final_url: str | None
    domain: str | None
    risk_label: RiskLabel
    risk_score: float = Field(..., ge=0.0, le=1.0)
    reasons: list[str]
    reputation: ReputationInfo

class ModelInfo(BaseModel):
    name: str
    version: str
    threshold: float = Field(..., ge=0.0, le=1.0)

class AnalyzeResponse(BaseModel):
    risk_label: RiskLabel
    risk_score: float = Field(..., ge=0.0, le=1.0)
    is_scam: bool
    summary: str
    reasons: list[str]
    actions: list[str]
    intent: IntentInfo
    url_findings: list[UrlFinding]
    model: ModelInfo
