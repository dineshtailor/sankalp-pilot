"""Build the Project Sankalp document set (Word) from the analysis outputs. Run from anywhere:
    python "D:/FDE/Mini Project/docs/build/build_docs.py"
Every figure comes from sankalp-pilot/analysis/findings.json or the live modules, so numbers match the pilot."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(HERE))
os.chdir(REPO)

from theme import MUTE, RED, Doc  # noqa: E402
from agent import reports as rp  # noqa: E402

F = json.load(open(REPO / "analysis" / "findings.json"))
VOICE = json.load(open(DOCS / "voice_notes.json", encoding="utf-8")) if (DOCS / "voice_notes.json").exists() else []
CH = DOCS / "charts"


def L(x):  # rupees -> lakh string
    return f"₹{x / 1e5:,.1f} lakh"


def CR(x):
    return f"₹{x / 1e7:,.2f} cr"


cc = rp.circular_check()
drop = [r for r in cc["rows"] if r.get("decision") == "DROP"]
drop_ret = F["P2_returns_net_of_bad_claims_inr"]
drop_foc = sum(r["foc_cost_l12m_inr"] or 0 for r in drop)
P1 = F["P1_claim_leakage"]; P1i = P1["items"]
P2_cap = F["P2_scheme_driven_expiry"]["foc_over_3pct_cap_l12m_inr"]
P2_hard = drop_ret + P2_cap
P3 = F["P3_rebalance"]["inr_per_year_revenue_protected"]
REB = F["module_B_rebalance_now"]
TAT = F["P5_tat"]
TOTAL_CASH = P1["inr_per_year"] + P2_hard
REFUNDS = P1["inr_per_year"] + drop_ret

# =====================================================================================================================
def discovery():
    d = Doc("Discovery Note", "What is actually wrong in the GM trade channel, what it costs, and our view on the CFO's forecasting ask",
            "SNK-DN-01", owner="FDE team for Anita Desai (Commercial Excellence)", base_size=9, margins_cm=1.4)
    d.callout("Bottom line for the steering group", [
        f"Expiry claims (now **{F['expiry_claims_logged_l12m_cr']:.2f} cr** a year, 2.7% of primary) and the fall in fill rate are **not a forecasting failure**. "
        "They come from three things a forecast cannot fix: quarter-end schemes that push stock the market does not absorb, C&F allocation shares that "
        "were never re-set (Lucknow empty while Kolkata sits on 3.5–6.5 months), and claims credited without a check against billing history.",
        f"We recommend a three-user pilot that saves about **{CR(TOTAL_CASH)} a year** ({CR(REFUNDS)} in refunds and {L(P2_cap)} of free goods at PTS) and protects **{CR(P3)} a year of revenue at PTS**, "
        "and that the 12-month demand-sensing vendor pilot is deferred. This takes expiry claims from 2.71% to about 2.2% of primary; reaching 1% also needs incentive and scheme-volume changes."])
    d.h1("1. Ranked problems")
    d.table(["#", "Problem (owner)", "Evidence (file · rows / page)", "₹ a year", "Method"], [
        ["P1", "**Stockists are short in the North while Kolkata is long.** Allocation shares not reviewed since FY25 (Kavita Rao, Vaishali Kapoor)",
         "cnf_stock_snapshot.csv: cover 30-Sep-26 Lucknow 0.24 m, 23 SKUs at zero; Kolkata 3.8 m (3.5–6.5 across Apr–Sep). Demand share Lucknow 15.3%→20.8%, Kolkata 17.8%→13.3% (primary_sales.csv ordered_qty). Doc 4 p.1; Doc 5 CF-N02 3rd request; Doc 3 Annexure",
         f"{CR(P3)} revenue protected", "Per SKU-month Apr–Sep 26: min(50% of North unsupplied packs, stock above 2 months at other C&Fs) × PTS, annualised"],
        ["P2", "**Quarter-end schemes create the expiry.** 10+2 since Dec 2024; FOC above the cap; a 100%-or-zero incentive drives the push (Arjun Sethi; CFO approves exceptions)",
         "15 scheme SKUs = 61% of primary but 95% of expiry claims (L12M). Scheme lots come back at 3.1–9.4% vs 1.1–8.3% without scheme (PFL1302: 6.9% vs 1.4%) (analysis/11). 25–34% of each quarter billed in the 9-day window. FOC on orders below the 1.5× minimum: ₹1.05 cr L12M. Voice AUD-1001, AUD-1003. Doc 2 §4.4, Annex B",
         f"{CR(P2_hard)} (up to {CR(drop_ret + drop_foc)})", f"Excess returns on {len(drop)} SKUs recommended for drop, net of P3 ({L(drop_ret)}) + FOC above the 3% cap ({L(P2_cap)}); upside if FOC on dropped SKUs is not replaced. FOC is at PTS; true cost is lower"],
        ["P3", "**Claims credited that break the policy.** Two people, no check against sales (Neha Bansal)",
         f"expiry_claims.csv L12M: {P1i['duplicate_same_stockist_batch_qty']['claims']} repeats of same stockist+batch+qty (e.g. rows 3269/3596, ₹26,846, Doc 5 11-Aug); {P1i['expired_claim_after_90_days']['claims']} filed >90 days after expiry (e.g. row 1785, 112 days, ₹10,333); {P1i['qty_above_invoiced_excess_only']['claims']} above packs invoiced. 55% of repeats have no invoice ref; C&F told parties to resend (CALL 8662). Doc 2 §5.2, §5.5, §5.6",
         f"{L(P1['inr_per_year'])} refunds", "Value of credited/pending L12M claims failing a hard rule (over-quantity: excess packs only; each claim counted once)"],
        ["P4", "**FEFO broke at Kolkata after the WMS change** (Subhajit Banerjee; Hooghly C&F)",
         "From Mar-26, 64–79% of Kolkata packs ship from a newer batch while an older one ships the same month vs 10–56% elsewhere; 7 idle lots at Kolkata only, 92% Cardio and Pain, first blocked 1 Mar 2027 (cnf_stock_snapshot). Voice AUD-1014; Doc 3 cl. 4.3, 6.3",
         "₹11.8 lakh at risk (one-off)", "Value at PTS of lots idle 90+ days while a newer batch shipped; not in the annual total"],
        ["P5", "**Claim-to-credit-note takes 45 days** vs 30 in policy (Neha Bansal)",
         f"Mean {TAT['mean_days']} days, {TAT['share_over_30d_pct']}% over 30; {TAT['pending_claims']} pending worth {L(TAT['pending_inr'])}, oldest Jun-26 (expiry_claims.csv). Stockists holding payment (Doc 5, 10-Sep, EML-024)",
         "Working capital, trust", "Tool pre-checks claims and auto-finds the invoice for the 20% with none"],
        ["–", "**Breakage in the East** (Neha, Subhajit belief)", f"Breakage claims {L(F['P6_breakage_l12m_inr'])} L12M = {F['P6_breakage_pct_primary']}% of primary", "Not material", "Deprioritised"],
    ], widths_cm=[0.7, 4.3, 7.6, 2.2, 3.4], size=7)
    d.h1("2. Our view on the CFO's ask (an AI demand-forecasting tool)")
    d.image(CH / "kpis.png", width_cm=8.6, caption="Claims % of primary and fill rate by quarter, recomputed from the raw extracts")
    d.bullets([
        "**The fill-rate fall is about where stock goes, not how much.** Partly filled lines have held at 96–97% since FY26; the decline comes from lines not supplied at all, "
        "concentrated where a C&F is at zero while another holds 3–6 months (P1). A national forecast is split by the same stale allocation tab (Doc 4, Vaishali).",
        "**Planning already reports about 14% SKU-month MAPE** (voice note AUD-1013; not testable, no forecast file).",
        "**The expiry is pushed, not forecast.** 95% of expiry value sits on scheme SKUs and scheme lots return far more often (P2). A model trained on primary sales "
        "would learn the 9-day scheme spike as demand and plan more of it.",
        "**What the forecasting ask would recover:** at most part of P1, and only after allocation is fixed; nothing of P2 or P3. The vendor's 30% accuracy claim is "
        "unverified (Doc 5, 5-Oct). We recommend deferring it and re-testing after two clean quarters.",
    ])
    d.h1("3. Users and problems we chose")
    d.table(["User and weekly decision", "Problems", "Screen in the pilot"], [
        ["Claims executive, Commercial Finance (Neha Bansal): approve, reject or escalate each claim before the CN", "P3, P5", "Claims desk; Month audit (batch mode)"],
        ["NSM and RSMs (Arjun Sethi): which SKUs go on the next quarter-end circular; which stockists to check (§4.5)", "P2", "Scheme circular check"],
        ["Head of Supply Chain and RDMs (Kavita Rao, Subhajit Banerjee): month-end return-to-CDC moves; FEFO investigation", "P1, P4", "Stock rebalance"],
    ], widths_cm=[9.5, 2.0, 6.3], size=8)
    if VOICE:
        d.h1("4. What the voice notes add")
        d.table(["Recording", "Language", "Gist (translated)", "Tested against data"], [[v["file"], v["language"], v["gist"], v["test"]] for v in VOICE],
                widths_cm=[2.9, 1.5, 6.7, 6.7], size=6.8)
    d.h1(("5" if VOICE else "4") + ". Open questions for the client")
    d.table(["Question", "Source", "What we do with the answer"], [
        ["How is the QBR fill rate computed? The extract gives 95.5% for Q1 FY26 vs 99.5% reported", "Doc 6 §1", "Align the KPI the pilot reports"],
        ["What are the current allocation shares, and when did they last change?", "Doc 4 (Kavita, Vaishali); Doc 3 §2.2", "Replace the order-share proxy in Rebalance"],
        ["Kolkata WMS go-live date; did Distribution confirm FEFO rules in writing (cl. 4.3)?", "Doc 3 cl. 4.3; Doc 4 p.2", "Confirm P4 cause; trigger Sch.4 root-cause report"],
        ["Can the 46 repeat claims already credited be recovered against open balances?", "Doc 5, 11/12-Aug", "Turn P3 into recovered cash"],
        ["Does ordered_qty include re-orders after a cancelled line?", "Doc 1 §5.4; Doc 3 §2.4", "Tighten the lost-sales estimate (we assume 50%)"],
        ["Can ERP give expiry dates for batches made before Oct 2023 (971 claims)?", "Doc 1 §5.2", "Close the 'batch archived' needs-a-person route"],
        ["What are the incentive terms? Is payout really zero below 100%?", "Voice AUD-1003; Doc 6 §4", "Size the incentive fix"],
        ["How is the 1.5× minimum measured: per order or per month?", "Doc 2 Annex B", "Firm up the ₹1.05 cr"],
        ["Are orders refused before SAP missing from primary_sales?", "Voice CALL 9935", "Correct lost-sales sizing"],
    ], widths_cm=[8.6, 3.6, 6.0], size=7)
    if not VOICE:
        d.p("The six voice notes are **not yet transcribed**, so no finding above relies on them.", size=8)
    d.p("Method: all figures recomputed from the raw extracts after cleaning (746 duplicate sales rows and 23 duplicate claim rows removed, repeated order quantities on 2,834 split lines counted once, three date formats, "
        "code variants such as CFE01 and PFL-1001 normalised). Scripts: sankalp-pilot/analysis/00–19. L12M = 01-Oct-25 to 30-Sep-26. Rows are spreadsheet rows (header = row 1).",
        size=7, color=MUTE, italic=True)
    return d.save(DOCS / "01_Discovery_Note.docx")


# =====================================================================================================================
def architecture():
    d = Doc("Architecture Note", "Sankalp Channel Guard: one LangGraph workflow, three users, code decides and the model reads and writes",
            "SNK-AN-01", owner="FDE team", base_size=9.5, margins_cm=1.6)
    d.h1("1. Graph")
    d.image(CH / "graph.png", width_cm=17.5, caption="agent/graph.py. Black = plain Python, purple = model call, green = the named person who acts. "
            "The four checks run as parallel nodes, each writing its own state key, joined by decide.")
    d.h1("2. Code and model split")
    d.table(["Step", "Done by", "Why"], [
        ["Clean and join the 7 extracts; keep spreadsheet row of every record", "Code (agent/data.py)", "Exact facts; loaded once in memory, never pasted into a prompt"],
        ["Read a messy stockist email (English, Hindi, tables) into fields", "**Model**, structured output (EmailFields schema); regex fallback", "Language understanding; schema means code can act on it; fallback keeps the desk running"],
        ["Classify non-claim mail into a fixed label list (MRP, transit, scheme, supply)", "**Model** (same call); keyword fallback", "Fixed labels, routed to an owner by code"],
        ["Claim type, unit conversion, batch, expiry, packs invoiced, earlier claims", "Code (build_lines, resolve)", "Every number from a file and row; the stockist's label is not trusted"],
        ["Window §5.2 · quantity §5.5 · duplicate §5.6 · invoice §5.3/5.4 · billing C&F §5.1 · value §5.7", "Code (agent/rules.py), parallel nodes", "Each rule has a number, so it is a formula with tests"],
        ["APPROVE / REJECT / NEEDS_PERSON routing", "Code (rules.decide)", "Moves money: never the model"],
        ["Plain-language note and reply to stockist", "**Model**, guarded", "Discarded and replaced by a template if it contains any number not in the evidence"],
        ["Circular check, rebalance, FEFO signal, month audit", "Code (agent/reports.py)", "Sums, windows and joins"],
        ["Raise the CN, change a circular, approve a return-to-CDC", "**A named person**", "Charter: read-only pilot; owners decide (Doc 1 §6)"],
    ], widths_cm=[7.0, 4.6, 6.2], size=7.5)
    d.h1("3. Tools and the data each reads")
    d.table(["Tool / function", "Reads", "Returns"], [
        ["batch_record", "batch_master.csv, sku_master.csv", "SKU, expiry, PTS, pack; not found + close matches (never a guess)"],
        ["supply_of_batch_to_stockist", "primary_sales.csv", "Invoices, packs incl. free, billing C&F, rows"],
        ["prior_claims / claim_record", "expiry_claims.csv", "Earlier non-rejected claims on stockist + batch, status, CN"],
        ["stockist_record / stockist_candidates", "stockist_master.csv", "Code, C&F, city; suggestions only when sender is unknown"],
        ["email_record", "claim_emails.csv", "Raw message as received (treated as untrusted)"],
        ["circular_check / stockist_watchlist", "primary_sales, expiry_claims, sku_master", "Scheme vs non-scheme claim-back by SKU; FOC; drop/keep/review"],
        ["rebalance / fefo_signal / stranded_lots / allocation_shares", "cnf_stock_snapshot, primary_sales, batch_master", "Moves to short C&Fs; FEFO proxy; idle older lots; share drift"],
    ], widths_cm=[4.6, 5.4, 7.8], size=7.5)
    d.h1("4. Failure handling")
    d.table(["Failure", "What the tool does"], [
        ["Batch, claim, stockist or SKU not found", "Says not found / needs a person, with close matches as hints (e.g. K23O0830 → K2300830). Never fills in."],
        ["Quantity in boxes, or strips for a syrup", "Converts only when stated (43 boxes × 10); still routes to a person to confirm"],
        ["Email contains instructions to the AI (EML-017)", "Flags it, ignores it, never approves; the rules still run (705 > 441 packs → reject)"],
        ["Model down, timeout, bad JSON, or no key", "Regex reader and template note; screen shows which path was used"],
        ["Model note invents a number", "Note dropped, template shown (tested)"],
        ["Data gap (batches archived before Oct 2023, no secondary sales)", "Routes to a person; estimates state their method on screen"],
        ["Cold start / slow request", "CSVs load once per instance (~3–6 s); no tool loop, so no runaway trips"],
    ], widths_cm=[6.0, 11.8], size=7.5)
    d.h1("5. Cost and speed per run")
    d.table(["Request", "Model calls", "Tokens (approx.)", "Cost (gpt-4o-mini via OpenRouter, list price)", "Time"], [
        ["Claim from register", "1 (note)", "≈1.2k in / 0.15k out", "≈ ₹0.03", "< 1 s warm + model"],
        ["Mailbox email", "2 (read + note)", "≈2.3k in / 0.35k out", "≈ ₹0.05", "2–5 s"],
        ["Month audit (≈200 claims)", "1 (summary)", "≈0.5k in / 0.15k out", "≈ ₹0.01", "≈ 4 s"],
        ["Circular check / rebalance", "1", "≈0.8k in / 0.15k out", "≈ ₹0.01", "1–3 s"],
        ["Code-only mode (no key)", "0", "0", "₹0", "same"],
    ], widths_cm=[4.2, 2.4, 3.4, 5.3, 2.5], size=7.5)
    d.p(f"At about 4,500 claim lines a year the model cost is a few hundred rupees a year, against the C&F claim-handling fee of ₹45 a line (Doc 3 cl. 5.1). "
        "Measured: the 20-record check set used 37 model calls, about 28.8k input and 3.7k output tokens, about $0.007. Calls, tokens and seconds are shown on every result. Prices: confirm on the provider's pricing page at deployment.", size=8)
    d.h1("6. Design choices we can defend")
    d.bullets([
        "**No forecasting model, no RAG, no vector store.** Documents are short; rules are numbers (brief §05). Discovery shows the money is in claims, schemes and allocation.",
        "**Parallel check nodes** rather than one function, so each rule is visible in the graph, tested alone and easy to extend (e.g. a breakage-window check).",
        "**No interrupt()/checkpointer:** the person acts in SAP, outside the tool; nothing to resume.",
        "**Stack:** FastAPI + plain HTML on Vercel (recommended path), region bom1; secrets in environment variables; 67 tests and a 20-record check set run in CI or on a laptop.",
    ], size=8.5)
    return d.save(DOCS / "02_Architecture_Note.docx")


# =====================================================================================================================
def srs():
    d = Doc("Software Requirements Specification, Traceability and Test Report", "SDLC artefacts for the Sankalp Channel Guard pilot (requirements → design → code → test)",
            "SNK-SRS-01", owner="FDE team", base_size=9.5)
    d.h1("1. Purpose, scope and users")
    d.p("The pilot helps three named users recover money in the GM domestic trade channel by checking stockist claims before credit notes, reviewing quarter-end "
        "schemes before the circular, and re-balancing C&F stock at month-end. It is read-only on static extracts (Doc 1 §6): it recommends; owners decide.")
    d.table(["User", "Goal", "Frequency"], [
        ["Claims executive, Commercial Finance", "Approve, reject or escalate each claim with evidence; audit a month", "Daily / monthly"],
        ["National Sales Manager, RSMs", "Decide which SKUs go on the circular; check high-risk stockists", "Quarterly, 2 weeks before circular"],
        ["Head of Supply Chain, RDMs", "Approve return-to-CDC moves; investigate FEFO", "Monthly at month-end"],
    ], widths_cm=[5.5, 9.0, 3.4], size=8)
    d.h1("2. Functional requirements")
    FR = [
        ("FR-01", "Load and clean the 7 extracts once; normalise dates, codes, numbers; remove exact duplicate rows; keep the source spreadsheet row of every record", "Doc 1 §5", "agent/data.py", "test_tools: normalisers, duplicates, joins"),
        ("FR-02", "Check a claim from the claims register by claim number", "Doc 2 §5", "graph: load_claim", "test_api: claim mode; check set C19–C20"),
        ("FR-03", "Read a mailbox email (English/Hindi/table) into claim lines; regex fallback without a model", "Doc 1 §5.7", "extract.py, read_email, build_lines", "test_tools: regex reader; check set C01–C16"),
        ("FR-04", "Claim window: near expiry −90 d to expiry; expired to +90 d; transit 7 d; expiry from batch master", "Doc 2 §5.2", "rules.check_window", "test_rules: window ×4"),
        ("FR-05", "Quantity ≤ packs of the batch invoiced to the stockist incl. free, net of earlier claims", "Doc 2 §5.5", "rules.check_quantity", "test_rules: quantity; C13, C15"),
        ("FR-06", "Duplicate: same stockist, batch and quantity as an earlier claim → reject; other repeats → person; repeats within one email", "Doc 2 §5.6; Doc 3 Sch.2 2.6", "rules.check_duplicate, build_lines", "test_rules; test_tools Neha case; C12, C16, C19"),
        ("FR-07", "Invoice reference: verify quoted invoice; find the supplying invoice when missing; person when none", "Doc 2 §5.3–5.4", "rules.check_invoice_ref", "test_rules: invoice; C04"),
        ("FR-08", "Returns only at the billing C&F", "Doc 2 §5.1", "rules.check_billing_cfa", "test_rules: billing CFA"),
        ("FR-09", "Value claims at PTS from sku_master", "Doc 2 §5.7; Doc 1 §5.1", "rules.claim_value", "test_rules: value"),
        ("FR-10", "Route APPROVE / REJECT / NEEDS_PERSON; say NOT FOUND for unknown records", "Brief §05", "rules.decide, finalise", "test_rules: routing; test_api: not found; C05–C09"),
        ("FR-11", "Treat mailbox content as untrusted; flag and ignore instructions", "Doc 1 §5.7", "rules.injection_flags, decide", "test_rules; test_api: injection; C15"),
        ("FR-12", "Answer claim-status queries from the register; route non-claim mail to the owner", "Doc 5; Doc 1 §4", "claim_status, ROUTE", "test_tools; C17, C18"),
        ("FR-13", "Month audit: run every claim in a month and total value failing rules", "Brief §07", "batch_month", "Smoke run (analysis/13); UI"),
        ("FR-14", "Circular check: scheme vs non-scheme claim-back by SKU; FOC vs 3% cap; drop/keep/review; stockist watchlist", "Doc 2 §4.3–4.5", "reports.circular_check", "test_api: reports; backtest analysis/09–11"),
        ("FR-15", "Rebalance: C&F cover, moves from >2 months to <1 month, allocation drift, FEFO signal", "Doc 3 Sch.2 2.2, 2.5, cl. 6.3", "reports.rebalance", "test_api: reports"),
        ("FR-18", "List lots idle 90+ days while a newer batch shipped, with value and 60-day block date", "Doc 3 cl. 6.3; voice AUD-1014", "rules.is_stranded, reports.stranded_lots", "test_rules; test_api: stranded"),
        ("FR-19", "Report free goods given below the 1.5× minimum order", "Doc 2 Annex B; voice AUD-1001", "rules.scheme_moq_met, reports.moq_breach", "test_rules; test_api: minimum order"),
        ("FR-16", "Export an audit trail (checks, clauses, evidence rows) as CSV", "Brief §07", "public/app.js", "Manual UI test"),
        ("FR-17", "Show model calls, tokens and seconds for each request", "Brief §07", "llm.Meter, graph.run", "test_api: meter counts the call"),
    ]
    d.table(["ID", "Requirement", "Source", "Design / code", "Verified by"], [list(x) for x in FR], widths_cm=[1.2, 6.8, 2.6, 3.3, 3.9], size=7.2)
    d.h1("3. Non-functional requirements")
    d.table(["ID", "Requirement", "How met / verified"], [
        ["NFR-01", "Every number on screen has a source (file and row, or clause)", "Evidence table on every result; spreadsheet rows; test_api checks every evidence item has file and row"],
        ["NFR-02", "Nothing invented: 'not found' beats a guess", "No auto-correction of codes; model note guarded; test_api invented-number test"],
        ["NFR-03", "Works without a model key and when the model fails", "Regex reader + template; check set 20/20 with the model and 20/20 code-only"],
        ["NFR-04", "Warm response under 5 s per claim; cold start under 15 s", "Measured locally ≈0.1–4 s warm; CSVs load once (≈3–6 s)"],
        ["NFR-05", "Usable by a stranger on a phone", "Single page, plain HTML, responsive layout (≤760 px stacks)"],
        ["NFR-06", "Security: read-only; secrets only in environment variables; repository private", ".env ignored by git; no write-back endpoints"],
        ["NFR-07", "Maintainability: every policy number in one config with its clause", "config.py; test asserts the values match the documents"],
    ], widths_cm=[1.6, 7.0, 9.2], size=7.5)
    d.h1("4. Test plan and results (19 Nov 2026)")
    d.table(["Level", "What", "Command", "Result"], [
        ["Unit", "Each rule just below, at and just above its limit; normalisers", "pytest -q tests/test_rules.py tests/test_tools.py", "pass"],
        ["Integration / API", "Graph end to end, not-found, injection, guarded note, reports", "pytest -q tests/test_api.py", "pass"],
        ["Acceptance (check set)", "20 real awkward records agreed by hand against raw rows", "python -m checks.run_checks", "**20 / 20** with gpt-4o-mini and code-only"],
        ["Total", "", "pytest -q", "**67 passed**"],
    ], widths_cm=[3.0, 6.8, 5.0, 3.0], size=8)
    d.callout("Honest limits", ["Check set scored both ways: with gpt-4o-mini (all 18 emails read by the model; 19 of 20 notes by the model, C18 is a fixed routing message) and with the code-only fallback. The six voice notes are machine-transcribed; each claim was tested in the data, and untestable claims are open questions.",
                                "Circular-check and rebalance estimates have no secondary-sales ground truth; they state their method on screen and are decisions for a person."], fill="warn", size=8.5)
    d.h1("5. Change control and configuration")
    d.bullets(["New or changed rule: update the SRS row, add the test first, change config.py / rules.py, re-run tests and the check set, one commit per slice.",
               "Decision log: sankalp-pilot/docs/decision_log.md (10 decisions with evidence and rejected alternatives).",
               "Release: v1.0 = this document set + commit on main; deployment runbook in README.md and 05_Deployment_Runbook."], size=8.5)
    return d.save(DOCS / "03_SRS_Traceability_Test_Report.docx")


# =====================================================================================================================
def plan():
    d = Doc("Project Plan", "Phase-wise delivery plan with SDLC governance", "SNK-PLAN-01", owner="FDE team", base_size=9.5)
    d.h1("1. Objective")
    d.p("Find what is actually wrong in the GM trade channel, size it in rupees, and deliver a deployed LangGraph pilot that named users run every week; defend it to the steering group (CFO, Head SC, NSM). Deadline Sun 22 Nov 2026.")
    d.h1("2. Phases, outputs and gates")
    d.table(["Phase", "SDLC stage", "What we do", "Output", "Gate", "Status"], [
        ["1 Mobilise & discover", "Requirements gathering", "Read 6 docs, 26 emails, 6 voice notes; policy rules into config.py; clean 7 CSVs", "Cleaned data; voice transcripts", "Sales and FOC reconcile to QBR", "Done"],
        ["2 Test, size, prioritise", "Requirements analysis", "10 hypotheses tested in pandas; ranked by ₹ with owner", "Discovery note; findings.json", "Every number has rows", "Done"],
        ["3 Design", "System design", "Users, graph, code/model split, failure handling, cost", "Architecture note; SRS", "Each FR mapped to a component", "Done"],
        ["4 Build in slices", "Implementation", "Data → rules → claim checker → email → batch → reports → UI", "Repo with AGENTS.md", "Diff reviewed; tests green", "Done"],
        ["5 Validate", "Testing", "67 unit/API tests; 20-record check set", "Test report; RTM", "Check set recorded", "Done (model + code-only)"],
        ["6 Deploy", "Deployment", "Private GitHub → Vercel Hobby, bom1, env vars", "Live URL; /api/health", "Works on a new phone", "Ready, needs owner's accounts"],
        ["7 Present & hand over", "Maintenance", "≤12-slide deck, demo script, rollout plan", "Deck", "SteerCo sign-off", "Deck done"],
    ], widths_cm=[3.0, 2.6, 4.6, 3.0, 2.6, 2.0], size=7.5)
    d.h1("3. Risks")
    d.table(["Risk", "Mitigation"], [
        ["Machine transcription of Indian-language voice notes can be wrong", "Every spoken claim tested in the data; untestable ones are open questions"],
        ["No model key during demo", "Code-only mode passes the full check set"],
        ["Deployment on the last day", "Repo ready and tested locally; runbook with exact commands"],
        ["Estimates without secondary data", "Method on screen; backtested; a person decides"],
    ], widths_cm=[7.0, 10.8], size=8)
    return d.save(DOCS / "00_Project_Plan.docx")


def runbook():
    d = Doc("Deployment Runbook and Release Notes", "Release v1.0: from this folder to a live URL on Vercel (recommended path)", "SNK-RUN-01", owner="Deploy owner", base_size=9.5)
    d.h1("1. What you need (deploy owner)")
    d.bullets(["A personal GitHub account (the repository must be **private** and under your personal account, not an organisation)",
               "A Vercel account on the free Hobby plan, signed up with 'Continue with GitHub'",
               "An OpenRouter API key (optional: without it the pilot runs in code-only mode and passes the full check set)"])
    d.h1("2. Verify locally (5 minutes)")
    d.table(["Step", "Command (PowerShell, in D:\\FDE\\Mini Project\\sankalp-pilot)"], [
        ["Install", "pip install -r requirements.txt uvicorn pytest httpx"],
        ["Tests", "python -m pytest -q        → 67 passed"],
        ["Check set", "python -m checks.run_checks        → 20/20 correct"],
        ["Run", "python -m uvicorn app:app --reload        → open http://127.0.0.1:8000"],
    ], widths_cm=[3, 14.8], size=8.5)
    d.h1("3. Put the repository on GitHub")
    d.callout("Important: Vercel Hobby deploys only commits authored by the account owner",
              ["The local repository was committed with a placeholder author. Set your own identity and re-author before pushing:",
               "git config user.name \"<your GitHub name>\"   ·   git config user.email \"<your GitHub email>\"",
               "git rebase -r --root --exec \"git commit --amend --no-edit --reset-author\""], fill="warn", size=8.5)
    d.table(["Step", "Command"], [
        ["Create repo", "github.com/new → name sankalp-pilot → Private → Create (no README)"],
        ["Link and push", "git remote add origin https://github.com/<you>/sankalp-pilot.git   then   git push -u origin main"],
        ["Check", ".env is NOT in the repo (it is in .gitignore); data/*.csv ARE in the repo"],
    ], widths_cm=[3, 14.8], size=8.5)
    d.h1("4. Deploy on Vercel")
    d.bullets(["vercel.com → Add New → Project → Import sankalp-pilot.",
               "Framework preset **FastAPI**, root directory **./**.",
               "Environment variables: **OPENROUTER_API_KEY** = your key; **MODEL** = openai/gpt-4o-mini → Deploy.",
               "Settings → Functions → Function Region **bom1 (Mumbai)** → Redeploy.",
               "Smoke test: open <url>/api/health → \"ok\": true, \"model_key_set\": true, 7 data files. Then Claims desk → CLM-2605-04488 → REJECT with evidence rows.",
               "Re-run the check set with the key set: python -m checks.run_checks (locally with .env), and update the deck if any record changes.",
               "Open the URL on a phone that has never seen it (no log-in needed). Wake the app before the panel (first request loads the data, ≈5–10 s)."], numbered=True)
    d.h1("5. When it breaks")
    d.table(["Symptom", "Fix"], [
        ["No module named … at build", "Add it to requirements.txt with a pinned version; push"],
        ["model_key_set: false", "Add the variable in Settings → Environment Variables, then redeploy"],
        ["CSV not found", "data/ must be committed; paths are built from Path(__file__)"],
        ["Push by someone else does not deploy", "Owner merges, or owner runs: npm i -g vercel; vercel login; vercel --prod"],
        ["504 timeout", "Should not happen (no tool loop); check Logs within one hour"],
    ], widths_cm=[6, 11.8], size=8.5)
    d.h1("6. Release notes v1.0")
    d.bullets(["Claims desk: register claim, mailbox email or pasted email → 6 policy checks (4 in parallel) → APPROVE / REJECT / NEEDS A PERSON with evidence rows and clause.",
               "Month audit with CSV audit-trail export · Scheme circular check (drop / keep / review supply) with stockist watchlist · Stock rebalance with FEFO and allocation signals.",
               "Code-only mode without a model key; model note guarded against invented numbers; untrusted-email handling.",
               "Known limits: circular and rebalance are estimates without secondary sales; batches made before Oct 2023 route to a person."])
    return d.save(DOCS / "05_Deployment_Runbook.docx")


def evidence():
    E = json.load(open(REPO / "analysis" / "evidence_map.json", encoding="utf-8"))
    rows = [[r["slides"], r["number"], r["shown"], r["source"], r["script"]] for r in E["rows"]]
    ok = sum(r["ok"] for r in E["rows"])
    d = Doc("Evidence Appendix", f"Every calculated number on the 12 slides, traced to its file and method: {ok} of {len(rows)} reproduce", "SNK-EA-01", owner="FDE team", base_size=8, margins_cm=1.1)
    d.table(["Slide", "Number", "Value", "File and filter", "Script"], rows, widths_cm=[1.5, 5.6, 3.5, 5.8, 2.4], size=5.7)
    S = F["P3_rebalance"]["sensitivity_inr_per_year"]
    d.p(f"**The 50% assumption:** the extract cannot separate a new order from a re-order after a cancellation. Sales protected a year: {CR(S['10'])} at 10% real demand, {CR(S['25'])} at 25%, **{CR(S['50'])} at 50%**, {CR(S['75'])} at 75%, {CR(S['100'])} at 100% (capped by surplus stock).", size=6.5)
    d.p("**Re-run:** python -m analysis.19_evidence_map recomputes every row and fails on any mismatch. Scripts are in sankalp-pilot/analysis/. L12M = Oct 25–Sep 26. "
        "**From documents, not calculated:** QBR 90.9% and 99.5% (Doc 6 §1); 3% cap, 1.5×, 90 and 30 days (Doc 2); 14% MAPE and 100%/96% incentive (voice notes, unverified); WPI 0.64956% (NPPA order, 25-Mar-2026).", size=6.5)
    return d.save(DOCS / "07_Evidence_Appendix.docx")


def before_after():
    B = json.load(open(REPO / "analysis" / "evidence_map.json", encoding="utf-8"))["before_after"]
    T3 = B["pending_triage"]
    d = Doc("Before and After Report", "Today's process against the pilot, in time and in rupees, with the method stated", "SNK-BA-01", owner="FDE team", base_size=9, margins_cm=1.5)
    d.callout("Bottom line", [f"The pilot targets **{CR(TOTAL_CASH)} a year saved** ({CR(REFUNDS)} in refunds and {L(P2_cap)} of free goods at PTS) and protects **{CR(P3)} of sales**. It takes expiry claims from **{B['expiry_now_pct']}% to about {B['expiry_after_pct']}%** of primary.",
                              f"That does **not** reach the CFO's 1% goal: a further **{CR(B['gap_to_1pct_inr'])}** a year has to come from changing the incentive and scheme volumes."])
    d.h1("1. Process")
    d.table(["Step", "Today (evidence)", "With the pilot", "Who still decides"], [
        ["Check claim against billing", "Not done: two people, about 4,000 lines a year (Doc 4, Doc 6)", "6 policy checks with evidence rows; 4.4 s per record on the live URL", "Claims executive"],
        ["Find duplicates", f"'Could not complete the duplicate check' (Doc 5, 1 Oct); {P1['repeat_claims_credited']} repeat claims credited in L12M", "Flagged before the credit note, citing the earlier claim", "Claims executive"],
        ["Claim with no invoice", f"{B['no_invoice_claims']} claims ({L(B['no_invoice_inr'])}) in L12M on an 'approved' email (Doc 4)", f"Supplying invoice found for all {B['no_invoice_matched']}", "Area Manager, Finance"],
        ["Clear the backlog", f"{TAT['pending_claims']} pending ({L(TAT['pending_inr'])}); {B['tat_mean']} days to CN, {B['tat_over_30_pct']}% over the 30-day policy", f"Sorted now: {T3['APPROVE']['claims']} pass ({L(T3['APPROVE']['inr'])}), {T3['REJECT']['claims']} fail ({L(T3['REJECT']['inr'])}), {T3['NEEDS_PERSON']['claims']} need a person ({L(T3['NEEDS_PERSON']['inr'])})", "Commercial Finance"],
        ["Monthly claims audit", "Register consolidated by hand (Doc 5)", "All 229 September claims re-checked in about 6 s", "Controller"],
        ["Approve a scheme", "'Nobody had an estimate' of returns (Doc 6 minutes)", "Claim-back, FOC cost and drop/keep per SKU", "NSM; CFO for cap"],
        ["Rebalance stock", "Lucknow's third request since May (Doc 5); FY25 split (voice note)", f"{REB['moves']} moves worth {L(REB['value_inr'])} listed from the month-end snapshot", "Head of Supply Chain"],
        ["Spot FEFO failure", "C&F self-declares 'Yes' (Doc 3 Annexure)", "7 stranded Kolkata lots with batch, value and block date", "RDM East"],
    ], widths_cm=[3.3, 6.0, 5.6, 3.1], size=7.5)
    d.h1("2. Rupees a year")
    d.table(["Lever", "Today", "With the pilot", "Method and assumption"], [
        ["Bad claims", f"{L(P1['inr_per_year'])} credited or pending", "Stopped before the CN", "L12M claims failing §5.2, §5.5 or §5.6; each counted once"],
        ["Excess scheme returns", L(drop_ret), "Avoided", f"{len(drop)} SKUs dropped; assumes those lots then behave like non-scheme lots; net of bad claims"],
        ["FOC above 3% cap", L(P2_cap), "₹0", f"Enforcing the 1.5× minimum removes ₹1.05 cr, taking FOC from {B['foc_now_pct']}% to {B['foc_after_moq_pct']}%"],
        ["**Total saved**", f"**{CR(TOTAL_CASH)}**", f"**{CR(REFUNDS)} refunds + {L(P2_cap)} free goods**", "Assumes owners act on each recommendation"],
        ["North sales lost", CR(P3), "Protected (revenue, not profit)", f"Apr–Sep 26: {CR(F['P3_rebalance']['unsupplied_inr_window'])} unsupplied; 50% = {CR(F['P3_rebalance']['half_of_unsupplied_inr_window'])}; surplus covers {CR(F['P3_rebalance']['movable_inr_in_window'])}; × 2 for a year"],
        ["Kolkata stranded lots", "₹11.8 lakh at risk", "Picked before the 60-day block", "One-off; not in the annual total"],
    ], widths_cm=[3.7, 3.5, 3.6, 7.2], size=7.5)
    d.p("**Examples:** CLM-2605-04488 repeated CLM-2603-01616 and both were credited (₹26,846; expiry_claims rows 3269, 3596). CLM-2505-00135 was paid 112 days after expiry (₹10,333; row 1785). "
        "PFL1302 scheme lots came back at 6.9% against 1.4% for normal purchases.", size=8)
    d.h1("3. What we are not claiming")
    d.bullets(["**All ₹1.70 cr as cash:** ₹1.02 cr is refund money. The ₹68.3 lakh of free goods is valued at selling price (PTS); making cost is not in the data, so the true saving is lower unless those packs are sold instead.",
               "**Hours saved:** the pack has no measured time per claim. Measure minutes per claim for one week before and after go-live.",
               "**Faster credit notes:** the tool prepares the decision; reaching 30 days also depends on Finance capacity and C&F verification.",
               "**Sales impact of dropping schemes:** not measurable from primary data alone; test on the December circular."], size=8)
    return d.save(DOCS / "08_Before_After_Report.docx")


if __name__ == "__main__":
    for fn in (plan, discovery, architecture, srs, runbook, evidence, before_after):
        print("wrote", fn())
