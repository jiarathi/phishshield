from fastapi import APIRouter, Request, HTTPException
from app.core.config import settings
from app.core.limiter import limiter
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.services.analyzer import AnalyzerService

router = APIRouter()
analyzer = AnalyzerService()


@router.get("/health")
def health():
    return {"status": "ok"}

@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def analyze(request: Request, req: AnalyzeRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > settings.max_text_length:
        raise HTTPException(status_code=413, detail=f"text too long (max {settings.max_text_length})")
    return await analyzer.analyze(text)
