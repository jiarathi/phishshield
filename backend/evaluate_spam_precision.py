import os
import sys
import pandas as pd

# -----------------------------
# Path setup (so imports work)
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # .../phishShield/backend
sys.path.append(BASE_DIR)  # so "app." imports work

from app.services.text_model import TextModel  # noqa: E402

CSV_PATH = os.path.join(BASE_DIR, "data", "sms_spam.csv")


def load_sms_spam_dataset(csv_path: str) -> pd.DataFrame:
    """
    Robust loader for SMS spam datasets that may be:
    - tab-separated (common for the original SMS Spam Collection)
    - comma-separated but with unquoted commas in the message
    Returns DataFrame with columns: label, message
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at: {csv_path}")

    # 1) Try tab-separated first (most common)
    try:
        df = pd.read_csv(
            csv_path,
            sep="\t",
            header=None,
            names=["label", "message"],
            encoding="utf-8",
            engine="python",
        )
        if df["label"].astype(str).str.lower().isin(["spam", "ham"]).mean() > 0.8:
            return df
    except Exception:
        pass

    # 2) Try a forgiving CSV parse
    try:
        df = pd.read_csv(
            csv_path,
            header=None,
            names=["label", "message"],
            encoding="utf-8",
            engine="python",
        )
        if df["label"].astype(str).str.lower().isin(["spam", "ham"]).mean() > 0.8:
            return df
    except Exception:
        pass

    # 3) Fallback: manual parse line-by-line; split ONLY on the first comma/tab
    labels, messages = [], []
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            lower = line.lower()
            if lower.startswith("label,") or lower.startswith("label\t"):
                continue

            if "\t" in line:
                parts = line.split("\t", 1)
            else:
                parts = line.split(",", 1)

            if len(parts) != 2:
                continue

            label = parts[0].strip().lower()
            msg = parts[1].strip()

            if label not in ("spam", "ham"):
                continue

            labels.append(label)
            messages.append(msg)

    if not labels:
        raise ValueError("Could not parse dataset into (label, message).")

    return pd.DataFrame({"label": labels, "message": messages})


def main():
    print("Loading dataset from:", CSV_PATH)

    df = load_sms_spam_dataset(CSV_PATH)
    df["label"] = df["label"].astype(str).str.strip().str.lower()
    df["message"] = df["message"].astype(str)

    print(f"Loaded {len(df)} rows.")
    print("Label distribution:", df["label"].value_counts().to_dict())

    text_model = TextModel()

    tp = 0  # predicted spam AND actually spam
    fp = 0  # predicted spam BUT actually ham

    for _, row in df.iterrows():
        text = row["message"]
        actual = row["label"]  # 'spam' or 'ham'

        predicted = "spam" if text_model.predict_proba(text) >= text_model.meta.threshold else "ham"

        if predicted == "spam":
            if actual == "spam":
                tp += 1
            else:
                fp += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0

    print("\nSpam Detection Precision Evaluation")
    print("-----------------------------------")
    print(f"True Positives (TP): {tp}")
    print(f"False Positives (FP): {fp}")
    print(f"Precision: {precision:.4f} ({precision * 100:.2f}%)")

    import csv
    results_path = os.path.join(BASE_DIR, "spam_precision_results.csv")

    with open(results_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["TP", "FP", "Precision"])
        writer.writerow([tp, fp, round(precision, 4)])

    print(f"\nResults saved to: {results_path}")

if __name__ == "__main__":
    main()
