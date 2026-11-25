# Sankalp Channel Guard: pilot

A LangGraph workflow that helps three named users at a pharma company's domestic trade channel recover money:

| User (owner) | Weekly / monthly decision | Screen |
|---|---|---|
| Claims executive, Commercial Finance (Neha Bansal) | Approve, reject or escalate each stockist claim **before** the credit note | Claims desk, Month audit |
| National Sales Manager and RSMs (Arjun Sethi) | Which SKUs go on the next quarter-end circular; which stockists to check | Scheme circular check |
| Head of Supply Chain and RDMs (Kavita Rao, Subhajit Banerjee) | Which stock to pull back from long C&Fs to short ones; where FEFO is broken | Stock rebalance |

Every number on screen shows its source: file and spreadsheet row, or the policy clause. When the data cannot answer,
the tool says **not found** or **needs a person**. It never guesses. The pilot is read-only: it recommends, and owners decide.

Fictional teaching case (FDE Academy). Pfizer Limited is not involved. Keep this repository private.

**Live pilot:** https://sankalp-pilot-five.vercel.app

## Results on the data pack

| Check | Result |
|---|---|
| Unit and API tests | `pytest -q`: 67 passed |
| Hand-agreed check set (20 real awkward records) | `python -m checks.run_checks`: 20 / 20 with `openai/gpt-4o-mini` (locally and on the live URL) and 20 / 20 code-only |
| Claims that fail a hard rule, last 12 months | ₹21.1 lakh across 109 claims, each counted once (duplicates ₹12.9 lakh, >90 days after expiry ₹8.7 lakh, over-quantity ₹0.7 lakh, less ₹1.2 lakh overlap) |

Discovery and sizing scripts are in `analysis/` (run in order `00` to `19`; `19` recomputes every slide number; `16` transcribes the voice notes through OpenRouter). Their outputs are in `analysis/findings.json`.

## Layout
```
app.py              API routes only
config.py           every policy number with its clause
agent/data.py       loads the 7 CSVs once; cleans dates, codes, numbers, duplicates; keeps spreadsheet row numbers
agent/rules.py      CO-POL-014 / SC-AGR-CF-003 rules in plain Python (no model)
agent/tools.py      lookups and the claim pipeline (resolve -> 4 independent checks -> assemble)
agent/reports.py    circular check (Sales) and rebalance + FEFO signal (Supply Chain)
agent/extract.py    email -> fields (model structured output, regex fallback)
agent/prompts.py    every prompt
agent/graph.py      the LangGraph graph
public/             index.html, app.js, style.css (no build step)
tests/              test_rules.py, test_tools.py, test_api.py
checks/             check_set.csv, run_checks.py, check_results.csv
analysis/           discovery notebooks as scripts, findings.json
docs/deliverables/ discovery note, architecture note, SRS, RTM, deck
```

## Run locally
```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt uvicorn pytest httpx
copy .env.example .env            # optional: add OPENROUTER_API_KEY; without it the app runs code-only
pytest -q
python -m checks.run_checks
uvicorn app:app --reload          # http://127.0.0.1:8000
```

## Deploy (Vercel Hobby)
1. Push this folder to a **private** GitHub repo under your personal account.
2. vercel.com → Add New → Project → Import the repo. Framework preset: FastAPI. Root directory: `./`.
3. Environment variables: `OPENROUTER_API_KEY` and `MODEL=openai/gpt-4o-mini`. Deploy.
4. Settings → Functions → Region `bom1` (Mumbai) → redeploy.
5. Open `/api/health`. You should see `"ok": true`, `"model_key_set": true` and the 7 data files.

## Model and cost
Per claim email: 1 extraction call + 1 explanation call ≈ 1.5k input + 0.3k output tokens on `openai/gpt-4o-mini`,
which is a fraction of a rupee. Reports make 1 call or none. The screen shows calls, tokens and seconds for each request.
