# PhishShield design criteria — metrics

This folder holds **metric/criteria evaluation code** separate from product code. It is used to verify that the system meets the design criteria from the Engineering Research Plan.

## Criterion 3: System speed (< 500 ms median)

**Requirement:** Total analysis time has a median below 500 milliseconds over at least 200 test messages.

### How to run

1. **Start the backend** (from the project root or `backend/`):
   ```bash
   cd backend
   source .venv/bin/activate   # or: .venv\Scripts\activate on Windows
   uvicorn app.main:app --reload
   ```

2. **Run the criterion 3 script** (from the project root):
   ```bash
   python metric/criterion_03_latency.py
   ```

   Optional arguments:
   - `--base-url URL` — API base URL (default: `http://localhost:8000`)
   - `--n N` — number of analyses to run (default: 200)
   - `--delay SEC` — seconds to wait between requests (default: 6.0). Keeps under the backend rate limit; with 200 runs the script takes ~20 minutes.
   - `--use-server-header` — use server-reported `X-Response-Time-ms` instead of client elapsed time

   Example:
   ```bash
   python metric/criterion_03_latency.py --n 200 --base-url http://127.0.0.1:8000
   ```

3. **Interpret result:** The script exits with code 0 (PASS) if the median latency is below 500 ms, and 1 (FAIL) otherwise.

---

## Criterion 4: Explanation clarity (at least one plain-language reason)

**Requirement:** Each tool-generated response includes at least one clear, plain-language explanation (e.g. “punycode domain,” “IP-based URL,” “look-alike domain”).

### How to run

1. **Start the backend** (same as for Criterion 3).

2. **Run the criterion 4 script** (from the project root):
   ```bash
   python metric/criterion_04_explanations.py
   ```

   Optional arguments:
   - `--base-url URL` — API base URL (default: `http://localhost:8000`)
   - `--delay SEC` — seconds between requests (default: 6.0)

3. **Interpret result:** Exit code 0 (PASS) if every response has ≥1 plain-language reason; 1 (FAIL) otherwise.

---

## Criterion 5: Usability (median SUS ≥ 70)

**Requirement:** After participants use the tool, the median System Usability Scale (SUS) score is approximately 70 or higher.

This criterion is measured via **human participant testing**: participants use PhishShield, then complete the standard 10-item SUS questionnaire (on paper or in a separate form). You collect their responses and run this script on the CSV—**no product code is used or changed**.

### CSV format

- One row per participant.
- Header must include columns **Q1, Q2, … Q10** (optional first column e.g. `Participant`).
- Each Q is a number 1–5 (1 = Strongly disagree, 5 = Strongly agree). Standard SUS item order.

Example (see `metric/sample_sus_responses.csv`):

```csv
Participant,Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9,Q10
1,4,2,4,1,5,2,4,1,5,2
2,5,1,5,1,4,2,4,2,4,2
```

### How to run

From the project root:

```bash
python metric/criterion_05_usability.py --input metric/your_sus_data.csv
```

Optional:
- `--target N` — target median SUS (default: 70)
- `--delimiter C` — CSV delimiter (default: `,`)

Example with sample file:

```bash
python metric/criterion_05_usability.py --input metric/sample_sus_responses.csv
```

**Interpret result:** Exit code 0 (PASS) if median SUS ≥ target; 1 (FAIL) otherwise.

---

### Dependencies

All scripts use only the Python standard library. No `pip install` is required in this folder.
