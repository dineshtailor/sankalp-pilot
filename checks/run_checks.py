"""Run the hand-agreed check set through the full graph. Run after every change:  python -m checks.run_checks
Prints a scorecard and writes checks/check_results.csv."""
import csv
import json
import sys
from pathlib import Path

from agent.graph import run

HERE = Path(__file__).parent


def main() -> int:
    rows = list(csv.DictReader(open(HERE / "check_set.csv", encoding="utf-8")))
    out, ok = [], 0
    for r in rows:
        payload = {"email_id": r["input"]} if r["mode"] == "email" else {"claim_no": r["input"]}
        res = run(r["mode"], payload)
        text = json.dumps(res, default=str)
        hit = res["decision"] == r["expected_decision"] and (not r["expected_reason_contains"] or r["expected_reason_contains"] in text)
        ok += hit
        out.append({"id": r["id"], "input": r["input"], "expected": r["expected_decision"], "got": res["decision"], "pass": hit,
                    "model_calls": res["meter"]["model_calls"], "seconds": res["meter"]["seconds"], "explanation": (res["explanation"] or "")[:200]})
        print(f"{r['id']} {r['input']:15s} expected {r['expected_decision']:13s} got {str(res['decision']):13s} {'PASS' if hit else 'FAIL'}")
    with open(HERE / "check_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    print(f"\nCheck set: {ok}/{len(rows)} correct")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
