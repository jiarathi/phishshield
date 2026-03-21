from __future__ import annotations
import json
import os
from dataclasses import dataclass
from pathlib import Path
import joblib
import logging

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "models" / "artifacts"
REGISTRY_PATH = Path(__file__).resolve().parents[2] / "models" / "registry.json"

@dataclass(frozen=True)
class TextModelMeta:
    name: str
    version: str
    threshold: float
    artifact_filename: str

class TextModel:
    def __init__(self) -> None:
        self.meta = self._load_registry()
        self.pipeline = None
        self._try_load_artifact()

    def _load_registry(self) -> TextModelMeta:
        if not REGISTRY_PATH.exists():
            # Safe default until trained
            return TextModelMeta(
                name="tfidf_logreg_calibrated",
                version="untrained",
                threshold=0.65,
                artifact_filename="text_model.joblib",
            )
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        return TextModelMeta(
            name=data.get("name", "tfidf_logreg_calibrated"),
            version=data.get("version", "unknown"),
            threshold=float(data.get("threshold", 0.65)),
            artifact_filename=data.get("artifact_filename", "text_model.joblib"),
        )

    def _try_load_artifact(self) -> None:
        artifact_path = ARTIFACT_DIR / self.meta.artifact_filename
        if artifact_path.exists():
            self.pipeline = joblib.load(artifact_path)
            logger.info("Loaded text model artifact: %s", artifact_path)
        else:
            logger.warning("Text model artifact not found (%s). Run scripts/train_text_model.py", artifact_path)

    def predict_proba(self, text: str) -> float:
        if self.pipeline is None:
            # Conservative fallback: low confidence, rely on policy/url signals.
            return 0.10
        proba = float(self.pipeline.predict_proba([text])[0][1])
        # Clamp for safety
        return max(0.0, min(1.0, proba))
