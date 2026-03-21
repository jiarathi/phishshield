import os
import sys
import csv
import pandas as pd

# -----------------------------
# Path setup (so imports work)
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # .../phishShield/backend
sys.path.append(BASE_DIR)  # so "app." imports work

from app.models.url_analyzer import URLAnalyzer  # noqa: E402

# -----------------------------
# INPUT DATA PATH
# -----------------------------
# Create a test CSV in backend/data/ named url_test.csv with columns:
#   url,actual
# where actual is: phishing OR benign
URL_TEST_CSV = os.path.join(BASE_DIR, "data", "url_test.csv")

# -----------------------------
# OUTPUT ARTIFACT PATHS
# -----------------------------
RESULTS_CSV = os.path.join(BASE_DIR, "url_red_precision_results.csv")
DETAILS_CSV = os.path.join(BASE_DIR, "url_red_precision_details.csv")

DESIGN_CRITERION_RED_PRECISION = 0.90  # 90%


def normalize_actual_label(x: str) -> str:
    s = str(x).strip().lower()
    if s in ("phish", "phishing", "malicious", "bad", "1"):
        return "phishing"
    if s in ("benign", "good", "legit", "legitimate", "0"):
        return "benign"
    raise ValueError(f"Unexpected actual label: {x!r} (expected phishing/benign)")


def normalize_predicted_risk(pred) -> str:
    """
    URLAnalyzer output can vary by implementation.
    This function tries to normalize it to one of: RED / YELLOW / GREEN
    Accepts:
      - string: 'RED'/'YELLOW'/'GREEN'
      - dict: {'risk_level': 'RED'} or {'risk': 'RED'} etc.
      - tuple: ('RED', score)
    """
    # tuple like ('RED', score)
    if isinstance(pred, tuple) and len(pred) >= 1:
        pred = pred[0]

    # dict with a key holding the label
    if isinstance(pred, dict):
        for key in ("risk_level", "risk", "level", "classification", "label"):
            if key in pred:
                pred = pred[key]
                break

    s = str(pred).strip().upper()
    if s in ("RED", "YELLOW", "GREEN"):
        return s

    raise ValueError(f"Unexpected predicted risk output: {pred!r}")


def main():
    if not os.path.exists(URL_TEST_CSV):
        raise FileNotFoundError(
            f"Missing {URL_TEST_CSV}\n\n"
            "Create backend/data/url_test.csv with columns:\n"
            "  url,actual\n"
            "where actual is phishing or benign.\n"
        )

    df = pd.read_csv(URL_TEST_CSV)
    df.columns = [c.strip().lower() for c in df.columns]

    if "url" not in df.columns or "actual" not in df.columns:
        raise ValueError("url_test.csv must have columns: url, actual")

    df["actual"] = df["actual"].apply(normalize_actual_label)

    analyzer = URLAnalyzer()

    # Counts for RED precision
    all_red = 0
    correct_red = 0

    # For saving details
    details_rows = []

    for i, row in df.iterrows():
        url = str(row["url"]).strip()
        actual = row["actual"]  # phishing/benign

        # ---- CALL YOUR URL ANALYZER ----
        # Your URLAnalyzer likely has a method like analyze(url) or assess(url).
        # We try analyze() first; if it doesn't exist, we try assess().
        if hasattr(analyzer, "analyze"):
            pred_raw = analyzer.analyze(url)
        elif hasattr(analyzer, "assess"):
            pred_raw = analyzer.assess(url)
        else:
            raise AttributeError(
                "URLAnalyzer needs an analyze(url) or assess(url) method."
            )

        predicted_risk = normalize_predicted_risk(pred_raw)

        is_red = (predicted_risk == "RED")
        is_correct_red = (is_red and actual == "phishing")

        if is_red:
            all_red += 1
            if is_correct_red:
                correct_red += 1

        details_rows.append([
            i + 1, url, actual, predicted_risk,
            "Y" if is_red else "N",
            "Y" if is_correct_red else "N",
        ])

    red_precision = (correct_red / all_red) if all_red else 0.0
    meets = red_precision >= DESIGN_CRITERION_RED_PRECISION

    print("\nURL RED Precision Evaluation")
    print("----------------------------")
    print(f"Total URLs evaluated: {len(df)}")
    print(f"All URLs predicted RED: {all_red}")
    print(f"Correct RED (RED AND phishing): {correct_red}")
    print(f"RED Precision: {red_precision:.4f} ({red_precision*100:.2f}%)")
    print(f"Design criterion (≥ 90%): {'PASS' if meets else 'FAIL'}")

    # Save summary results
    with open(RESULTS_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["All_RED", "Correct_RED", "RED_Precision", "Criterion_90pct", "PassFail"])
        w.writerow([all_red, correct_red, round(red_precision, 4), 0.90, "PASS" if meets else "FAIL"])

    # Save per-URL details (audit trail)
    with open(DETAILS_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row_id", "url", "actual", "predicted_risk", "pred_red", "correct_red"])
        w.writerows(details_rows)

    print(f"\nSaved summary to:  {RESULTS_CSV}")
    print(f"Saved details to:  {DETAILS_CSV}")


if __name__ == "__main__":
    main()
