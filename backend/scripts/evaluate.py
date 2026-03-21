from __future__ import annotations
from pathlib import Path
import pandas as pd
import joblib
import json
import numpy as np
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "models" / "artifacts"
REGISTRY_PATH = ROOT / "models" / "registry.json"

MONEY_RE = r"(\$|usd|gift\s*card|wire|zelle|venmo|cashapp|crypto|bitcoin)"
PHONE_RE = r"(\+?\d[\d\s\-\(\)]{7,}\d)"
URL_RE = r"(https?://)"
OTP_RE = r"(\b\d{4,8}\b|verification\s*code|one\s*time\s*pass)"

def _ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> tuple[float, list[dict]]:
    """Expected Calibration Error (ECE) with equal-width bins."""
    edges = np.linspace(0.0, 1.0, bins + 1)
    out = []
    ece = 0.0
    n = len(y)
    for i in range(bins):
        lo, hi = edges[i], edges[i+1]
        mask = (p >= lo) & (p < hi) if i < bins - 1 else (p >= lo) & (p <= hi)
        if not mask.any():
            out.append({"bin": i, "lo": float(lo), "hi": float(hi), "count": 0})
            continue
        py = p[mask]
        yy = y[mask]
        conf = float(py.mean())
        acc = float(yy.mean())
        cnt = int(mask.sum())
        gap = abs(acc - conf)
        ece += (cnt / n) * gap
        out.append({"bin": i, "lo": float(lo), "hi": float(hi), "count": cnt, "confidence": conf, "accuracy": acc, "gap": gap})
    return float(ece), out

def _slice_metrics(y: np.ndarray, p: np.ndarray, thr: float, name: str) -> dict:
    y_hat = (p >= thr).astype(int)
    cm = confusion_matrix(y, y_hat)
    tn, fp, fn, tp = cm.ravel().tolist()
    # avoid div/0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "slice": name,
        "n": int(len(y)),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }

def main() -> None:
    df_path = ROOT / "data" / "sms_spam.csv"
    df = pd.read_csv(df_path, header=None, names=["label", "text"], encoding="utf-8", engine="python")
    df = df[df["label"].str.lower().isin(["spam", "ham"])].copy()
    df["label"] = (df["label"].str.lower() == "spam").astype(int)
    df["text"] = df["text"].astype(str)
    X = df["text"].values
    y = df["label"].values

    reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    artifact = ARTIFACT_DIR / reg["artifact_filename"]
    pipe = joblib.load(artifact)

    p = pipe.predict_proba(X)[:, 1]
    thr = float(reg.get("threshold", 0.65))
    y_hat = (p >= thr).astype(int)

    print("Artifact:", reg.get("artifact_filename"))
    print("Threshold:", thr)
    print("ROC AUC:", roc_auc_score(y, p))
    print("Avg Precision (PR AUC):", average_precision_score(y, p))
    print("Brier score (lower is better):", brier_score_loss(y, p))
    ece, bins = _ece(y, p, bins=10)
    print("ECE (lower is better):", ece)

    print("\nConfusion Matrix:")
    print(confusion_matrix(y, y_hat))
    print("\nReport:")
    print(classification_report(y, y_hat, digits=3))

    # --- Simple slices (helps find false-positive/false-negative failure modes) ---
    has_url = df["text"].str.contains(URL_RE, regex=True, case=False)
    has_money = df["text"].str.contains(MONEY_RE, regex=True, case=False)
    has_phone = df["text"].str.contains(PHONE_RE, regex=True, case=False)
    has_otp = df["text"].str.contains(OTP_RE, regex=True, case=False)

    slices = [
        ("all", np.ones(len(df), dtype=bool)),
        ("has_url", has_url.values),
        ("no_url", (~has_url).values),
        ("has_money_terms", has_money.values),
        ("has_phone", has_phone.values),
        ("has_otp_terms", has_otp.values),
    ]

    print("\nSlice metrics (precision/recall tradeoffs):")
    for name, mask in slices:
        if mask.sum() < 5:
            continue
        m = _slice_metrics(y[mask], p[mask], thr, name)
        print(f"- {name}: n={m['n']} precision={m['precision']:.3f} recall={m['recall']:.3f} f1={m['f1']:.3f} (fp={m['fp']} fn={m['fn']})")

    # Save a machine-readable report for CI/benchmark tracking
    report = {
        "artifact": reg.get("artifact_filename"),
        "threshold": thr,
        "roc_auc": float(roc_auc_score(y, p)),
        "avg_precision": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "ece": float(ece),
        "calibration_bins": bins,
        "slices": [_slice_metrics(y[mask], p[mask], thr, name) for name, mask in slices if mask.sum() >= 5],
    }
    out_path = ROOT / "models" / "last_eval_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote: {out_path}")

if __name__ == "__main__":
    main()
