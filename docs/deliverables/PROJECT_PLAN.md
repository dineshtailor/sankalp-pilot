# Project Sankalp: Phase-wise Delivery Plan

**Engagement:** Pfizer Channel Engagement (FDE Academy Project 1, a fictional teaching case)
**Sponsor:** Rohan Mehta, CFO · **Engagement lead:** Anita Desai, Commercial Excellence
**Today:** Thu 19 Nov 2026 · **Submissions open:** Fri 20 Nov · **Deadline:** Sun 22 Nov, end of day
**Method:** a standard Forward-Deployed-Engineering / consulting delivery: *Mobilise → Discover → Size & Prioritise → Design → Build → Validate → Deploy → Present & Hand over*. Each phase ends at a gate with a fixed output. We don't move on until the gate is met.

---

## 0. The ask and the working hypothesis

| | |
|---|---|
| **What the CFO asked for** | "An AI demand-forecasting tool before the Q4 scheme cycle (January)." |
| **What the CFO actually wants** | Expiry claims (now 2.75% of primary, was 1.18%) back towards 1%, and fill rate (90.9%, was 99.5%) back up. |
| **Our starting hypothesis (to be proven or killed with data)** | Better forecasting won't fix this. The national stock is "sufficient" (QBR §2). The money leaks from **(a)** quarter-end schemes that push stock the market can't absorb, **(b)** stale C&F allocation shares (Lucknow short, Kolkata long), **(c)** possible FEFO failure after the Kolkata WMS migration, and **(d)** claims being credited with no check against billing history (duplicates, over-quantity, out-of-window, no invoice). |
| **Rule for the whole project** | Every number carries its source (file + row, or document + clause). "Not found / needs a person" beats a guess. |

---

## Phase 1: Mobilise and Discover (Day 1, Thu 19 Nov)

**Goal:** know the business, the rules, the beliefs and the data well enough to test every claim.

| Step | What we do | How | Output |
|---|---|---|---|
| 1.1 Read & vocabulary | Read all 6 client documents, the brief, the reader's guide and the build guide. Research trade terms (CFA, PTS/PTR/MRP, NE claim, CN, FEFO, RSL, DPCO/NLEM/NPPA, SSS, Schedule H1, AIOCD/LBE). | Document read-through and public sources (NPPA, CDSCO, DPCO 2013 text, AIOCD) | `discovery/glossary.md`, channel map |
| 1.2 Rule register | Pull every rule that carries a number into one table, e.g. claim windows ±90 d, 7-day breakage/short window, qty ≤ invoiced incl. FOC, RSL ≥ 60%, no dispatch < 60 d to expiry, scheme cap 3%, stock norm 2.5 months, MOQ 1.5× avg, CN within 30 d, replenishment ≤ 2 months / 1.2 months per shipment, C&F fee ₹45 per claim line, verification within 10 working days. | Manual, with clause references | `config.py` (each number with its page/clause) and `discovery/rule_register.md` |
| 1.3 Belief register | For each stakeholder (6 interviews, 26 emails, 6 voice notes): what they believe, and what evidence they gave. | Read the notes; **transcribe and translate the voice notes** (Whisper, run locally; Bengali/Hindi/Telugu/Punjabi/English) | `discovery/voice_notes_transcripts.md`, `discovery/belief_register.md` |
| 1.4 Data audit & cleaning | Load all 7 CSVs. Normalise dates (mixed formats), codes (case/spaces/variants), numbers stored as text. Remove duplicate rows. Join the SKU/batch/stockist masters. Reconcile row counts, date ranges, and totals against the QBR scorecard. | pandas, loaded **once**, in `agent/data.py` | `discovery/data_quality_report.md` (each issue with its row counts) |
| 1.5 Client questions | Log questions only the client can answer. | Each question names its source document and what we'll do with the answer | `discovery/open_questions.md` |

**Gate 1:** the rule register, belief register, voice transcripts and a cleaned data layer exist, and the cleaned totals match the QBR to within a stated tolerance.

---

## Phase 2: Test, Size and Prioritise (Day 1–2)

**Goal:** a **hypothesis log** that runs *question → test → result → ₹ per year → owner*, ranked by money.

| # | Hypothesis (who raised it) | Test in the data | Sizing method (₹/yr) |
|---|---|---|---|
| H1 | Duplicate claims, same stockist + batch credited twice (Neha; email of 11 Aug) | Group `expiry_claims` by stockist × batch (× qty); find repeats with a CN on both | Sum of second-credit values, annualised |
| H2 | Claims break policy §5: outside the window, qty > invoiced to that stockist incl. FOC, wrong C&F | Join claims to primary_sales by stockist × batch; apply each rule | Value credited on failing lines |
| H3 | Claims with no invoice reference (19%) approved on a blanket "Approved" email (§5.4, v4.2) | Share and value with no reference; how many have *no* matching sale at all | Value with no supporting primary sale |
| H4 | Quarter-end schemes (10+2 since Dec 2024, above the 3% cap every quarter) cause the expiry claims | Cap breach per quarter; last-9-days phasing; claims traced back to the scheme invoice they were bought on; §4.5 stock-norm breaches inferred from stockist purchase vs. run-rate | Claims value traceable to scheme lots, plus FOC above the cap |
| H5 | Stale allocation shares: Lucknow stocks out, Kolkata overstocked (Kavita, Subhajit, CF-N02 emails) | Each C&F's share of supply vs. its share of demand (orders), before and after FY25; months of cover per C&F from `cnf_stock_snapshot` | Lost sales (ordered − invoiced) at PTS in short C&Fs, plus expiry at long C&Fs |
| H6 | Kolkata WMS migration (Feb 2026) broke FEFO, so short-RSL stock was dispatched (STK0061 email, voice notes) | For each invoice, was an older batch still on hand at that C&F? RSL at invoice < 60% (§7.1)? Trend before/after Feb 2026 | Claims on non-FEFO / low-RSL dispatches |
| H7 | C&F stock that will expire before it sells (Kavita: "tell me before it expires") | Stock on hand vs. avg monthly outward vs. months to expiry, per batch per C&F | Projected write-off ₹ that early return-to-CDC could save |
| H8 | Claim-to-CN takes 46 days against a 30-day policy | Claim date → CN date distribution | Working capital and stockist friction (secondary in ₹) |
| H9 | Breakage in the East is a transporter problem (Neha, Subhajit) | Breakage claim value by state | Expected to be immaterial (QBR says 0.02%); confirm and deprioritise |
| H10 | **The CFO's ask: forecasting is the cause** | National supply vs. national demand; is the error *where* the stock goes rather than *how much*? | ₹ a better national forecast could recover vs. the levers above |

Other edge cases to check: claims raised for sub-stockists (§8.3), claims on batches missing from the batch master, PTS valuation on the claim date (§5.7), stockists with no licence or GSTIN.

**Gate 2:** a ranked problem list with a ₹ size, the evidence rows and the owner for each. An evidenced view on the CFO's ask. A chosen user and scope.

**Deliverable 1, the Discovery note (2 pages):** ranked problems, our view on the forecasting ask, chosen users, open questions.

---

## Phase 3: Solution Design (Day 2, Fri 20 Nov)

**Design principle:** *code decides, the model reads and writes.* Every exact fact and every numbered rule lives in Python with tests. The LLM only parses messy emails into fields, classifies, and explains.

### Working concept: one LangGraph workflow, "Sankalp Channel Guard," serving three users. The final scope depends on Phase 2.

| Module | User and weekly decision | Problems hit |
|---|---|---|
| **A. Claim Checker** (core) | Neha Bansal's claims executives (Commercial Finance), daily and weekly: *approve, reject, or send to a person* before a CN is raised | H1, H2, H3, H6 (evidence), H8 |
| **B. Expiry-Risk & Rebalance Radar** | Kavita Rao / Subhajit Banerjee (Supply Chain), monthly before replenishment: *which batches to pull back to the CDC; hold or raise allocation per C&F* | H5, H7 |
| **C. Scheme Stock-Norm Screen** | Arjun Sethi's RSMs (Sales), before each quarter-end circular: *which stockist × SKU should not get the scheme* (§4.5) | H4 |

### Graph shape (draft)

```
START → classify_input (code: claim id / email / batch / stockist)
   ├─ email → parse_email (LLM, structured output) → resolve_entities (code)
   ├─ claim → load_claim (code)
   └─ radar / scheme → run_report (code) → explain (LLM, optional) → END
resolve/load → [parallel checks: window | qty_vs_invoiced | duplicate | invoice_ref | rsl_at_dispatch | stockist_valid]
   → decide (code: APPROVE / REJECT / NEEDS_PERSON + rule clause)
   → explain (LLM: plain-language note; numbers come only from the check results)
   → END
```

Other design choices: a check that touches money always routes to a named person; failure handling covers not found, ambiguous, LLM down (falls back to code-only output), and untrusted email text (prompt-injection safe: the email is data, never instructions). Cost per run is logged as model calls, tokens and seconds.

**Gate 3 / Deliverable 2, the Architecture note (2 pages):** graph diagram, code-vs-model table with reasons, tools and the data each reads, failure handling, cost per run.

---

## Phase 4: Build in Vertical Slices (Day 2–3)

Repo layout follows the build guide (`app.py`, `config.py`, `agent/{llm,data,rules,tools,graph,prompts}.py`, `public/`, `tests/`, `checks/`). Each slice ends with **one testable behaviour, pytest green, and a check-set run.**

| Slice | Done means |
|---|---|
| S1 Data layer | All CSVs cleaned and loaded once; typed lookups; tests on dirty codes and dates |
| S2 Rules | Every numbered rule in `rules.py` with tests just below, at and just above each limit |
| S3 Claim Checker (one claim in, one decision out) | Claim ID → checks → decision → evidence table (file, row, clause) |
| S4 Email intake | Raw `claim_emails` message → LLM structured fields → same checks; regex fallback when no API key |
| S5 Batch mode | Run every claim in a month; show ₹ that would have been caught; CSV audit-trail export |
| S6 Radar (Module B) | Batch-level expiry risk and C&F cover table, with recommended actions |
| S7 Scheme screen (Module C) | Stockist × SKU flags before a circular |
| S8 Frontend | One page with tabs per user: input → decision first → evidence → states (loading, not found, needs a person, error); cost and speed shown |

---

## Phase 5: Validate (continuous, finalised Day 3)

* **Unit tests:** every rule, every tool, the API (no API key needed; the model is faked).
* **Check set:** 15–20 real, awkward records (duplicates, missing invoice, out-of-window, over-quantity, unknown batch, sub-stockist, injection-style email), with the right output agreed by hand in `checks/check_set.csv`. `run_checks.py` scores them after every change. The honest score goes on a slide.
* **Number reconciliation:** every figure in the notes and deck is reproduced by a script (`analysis/`) and listed in an evidence appendix.

**Gate 5:** tests green and the check-set score recorded.

---

## Phase 6: Deploy (start early, finalise Day 3)

* Target: **Vercel Hobby** (the recommended path), FastAPI plus static `public/`, region `bom1`.
* Env vars: `OPENROUTER_API_KEY`, `MODEL`. The app still works in code-only mode without a key.
* Check `/api/health` and a test on a phone that has never opened the URL.
* **Needed from you:** a GitHub account (private repo), a Vercel account, and an OpenRouter API key. This machine currently has no `git`, `node` or API key, so I prepare everything locally and you push and deploy. I'll give exact commands.

**Deliverable 3, the private repo:** README, AGENTS.md, tests. **Deliverable 4:** the live URL.

---

## Phase 7: Present and Hand Over (Day 3–4, by Sun 22 Nov)

* **Deck (≤ 12 slides):** problem in ₹, the CFO's ask answered, design, live demo script (including a "fail on purpose" record), check-set score, ₹ recovered per year with method, risks and asks, rollout plan. Appendix: sources and the evidence map.
* **Demo script** for the 4-minute live demo, plus likely panel questions per persona (CFO, Head SC, NSM) with answers.
* **Rollout plan:** pilot C&F, metrics to watch (claims % of primary, duplicate catch rate, CN TAT, fill rate by C&F), and what we need from the client.

---

## SDLC mapping (how development is governed)

Delivery is iterative: the sequence below is followed in order, and Phases 4 and 5 are built and tested in short slices. Each stage has an entry/exit gate and a versioned artifact.

| SDLC stage | Plan phase | Artifact (location) | Exit gate |
|---|---|---|---|
| 1. Requirements gathering | Phase 1 | Rule register, belief register, voice transcripts (`docs/discovery/`) | Every rule has a clause; every belief has an owner |
| 2. Requirements analysis / specification | Phase 2 | **Software Requirements Specification (SRS)** with functional reqs (FR-xx), non-functional reqs (NFR-xx), users and acceptance criteria (`docs/02_SRS`) | SRS reviewed; each FR traces to a discovery finding |
| 3. System design | Phase 3 | **Architecture / design document** (HLD: graph, components; LLD: state schema, tools, rules, API contract) (`docs/03_Architecture_Note`) | Each FR mapped to a component |
| 4. Implementation | Phase 4 | Source in the git repo; one slice = one commit (conventional commit messages); AGENTS.md; config.py | Code review of each diff; lint clean |
| 5. Testing | Phase 5 | **Test plan + Requirements Traceability Matrix (RTM)**; unit tests (pytest), integration/API tests, check set (UAT-style acceptance), test report | 100% of rules have tests; check-set score recorded |
| 6. Deployment / release | Phase 6 | Release notes v1.0, deployment runbook, `/api/health` smoke test | Live URL passes the smoke test on a new device |
| 7. Maintenance / handover | Phase 7 | Rollout plan, monitoring KPIs, known-issues log, decision log | Steering-group sign-off |

Supporting controls: requirement → design → code → test traceability (RTM); a decision log (`docs/decision_log.md`); configuration management (all policy numbers in `config.py`, secrets only in env vars); change control (any new rule = SRS update + test first).

## Timeline

| Day | Phases | Key outputs |
|---|---|---|
| Thu 19 Nov | 1, 2 (start) | Transcripts, rule and belief registers, clean data, first hypothesis tests |
| Fri 20 Nov | 2, 3, 4 (S1–S4) | Discovery note, architecture note, working Claim Checker locally |
| Sat 21 Nov | 4 (S5–S8), 5, 6 | All modules, check set, repo ready, **deployed** |
| Sun 22 Nov | 7 | Deck, demo script, final checks, **submit** |

## Deliverables checklist (from the brief)

1. ☐ Discovery note (2 pages)
2. ☐ Architecture note (2 pages)
3. ☐ Private repository: LangGraph graph, README, AGENTS.md, tests for every rule
4. ☐ Deployed pilot: live URL
5. ☐ Deck (≤ 12 slides) and demo

## Risks

| Risk | Mitigation |
|---|---|
| Voice-note transcription quality in Bengali/Telugu/Punjabi | Whisper medium plus translate; flag low-confidence passages and treat them as leads to verify in data, never as facts |
| No API key on the machine | Design runs deterministic by default; the LLM is additive |
| Deployment on the last evening | Deploy the skeleton on Day 2 |
| Over-scoping | Module A first and complete; B and C only if A is green |
