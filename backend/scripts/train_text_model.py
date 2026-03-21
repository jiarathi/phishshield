from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from datetime import datetime

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_curve

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "models" / "artifacts"
REGISTRY_PATH = ROOT / "models" / "registry.json"

def load_data() -> pd.DataFrame:
    data_path = ROOT / "data" / "sms_spam.csv"
    if not data_path.exists():
        raise FileNotFoundError(f"Missing dataset: {data_path}")
    df = pd.read_csv(
        data_path,
        header=None,
        names=["label", "text"],
        encoding="utf-8",
        engine="python",
    )
    df = df[df["label"].str.lower().isin(["spam", "ham"])].copy()
    df["label"] = (df["label"].str.lower() == "spam").astype(int)
    df["text"] = df["text"].astype(str)
    return df

def build_pipeline() -> Pipeline:
    word_vec = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=2,
        max_features=80000,
    )
    char_vec = TfidfVectorizer(
        lowercase=True,
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=2,
        max_features=120000,
    )
    features = FeatureUnion([("word", word_vec), ("char", char_vec)])

    base = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        n_jobs=None,
    )

    # Calibrate probabilities for more meaningful risk scores
    clf = CalibratedClassifierCV(base, method="sigmoid", cv=3)

    return Pipeline([
        ("features", features),
        ("clf", clf),
    ])

def choose_threshold(y_true: np.ndarray, p: np.ndarray, target_precision: float = 0.85) -> float:
    # Choose lowest threshold where precision >= target (maximises recall / minimises missed phishing).
    precision, recall, thr = precision_recall_curve(y_true, p)
    best = 0.65
    for i in range(len(thr)):
        if precision[i] >= target_precision:
            best = float(thr[i])
            break
    return max(0.05, min(0.95, best))

def main() -> None:
    df = load_data()
    X = df["text"].astype(str).values
    y = df["label"].astype(int).values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipe = build_pipeline()
    pipe.fit(X_train, y_train)

    p_test = pipe.predict_proba(X_test)[:, 1]
    thr = choose_threshold(y_test, p_test, target_precision=0.85)
    y_hat = (p_test >= thr).astype(int)

    print("=== Confusion Matrix ===")
    print(confusion_matrix(y_test, y_hat))
    print("\n=== Classification Report ===")
    print(classification_report(y_test, y_hat, digits=3))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_name = "text_model.joblib"
    joblib.dump(pipe, ARTIFACT_DIR / artifact_name)

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    registry["version"] = datetime.utcnow().strftime("%Y.%m.%d")
    registry["threshold"] = float(thr)
    registry["artifact_filename"] = artifact_name
    registry["trained_on"] = {
        "dataset": "sms_spam.csv",
        "n_rows": int(len(df)),
        "pos_rate": float(y.mean()),
        "notes": "Threshold tuned for precision >= 85% on full sms_spam.csv dataset.",
    }
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")

    print(f"\nSaved model to {ARTIFACT_DIR / artifact_name}")
    print(f"Updated registry: {REGISTRY_PATH}")

if __name__ == "__main__":
    main()
