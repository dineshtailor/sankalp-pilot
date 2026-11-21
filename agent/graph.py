r"""Sankalp Channel Guard: one LangGraph workflow serving three users.

  intake --(claim)--> load_claim ----------------------\
         --(manual)----------------------------------- resolve --> [window | quantity | duplicate | invoice] --> decide --> explain --> END
         --(email)--> read_email --> build_lines ------/                (parallel nodes, one state key each)
                                       \--(status query)--> claim_status --> explain --> END
         --(month)--> batch_month --------\
         --(circular)--> circular_check ---+--> explain_report --> END
         --(rebalance)--> rebalance -------/

Model calls: read_email (structured output) and explain / explain_report (plain-language note). Everything else is code.
"""
from __future__ import annotations

import json
import operator
import re
from decimal import Decimal
from typing import Annotated, Any, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

from agent import data as d
from agent import extract as X
from agent import prompts
from agent import reports as RP
from agent import rules as R
from agent import tools as T
from agent.llm import Meter, get_llm, has_key, usage_of

MODES = ("claim", "email", "manual", "month", "circular", "rebalance")


class State(TypedDict, total=False):
    mode: str
    payload: dict
    email: dict
    extract_method: str
    fields: dict
    flags: list
    lines: list
    facts: list
    window: list
    quantity: list
    duplicate: list
    invoice: list
    results: list
    decision: str
    status: list
    report: dict
    explanation: str
    explain_method: str
    usage: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]


# ------------------------------------------------------------------ nodes
def intake(state: State) -> dict:
    mode = state.get("mode")
    if mode not in MODES:
        return {"errors": [f"Unknown mode '{mode}'. Use one of {', '.join(MODES)}."]}
    return {}


def route_intake(state: State) -> str:
    if state.get("errors"):
        return "explain"
    return {"claim": "load_claim", "email": "read_email", "manual": "manual_line", "month": "batch_month",
            "circular": "circular_check", "rebalance": "rebalance"}[state["mode"]]


def load_claim(state: State) -> dict:
    rec = T.claim_record(state["payload"].get("claim_no", ""))
    if not rec["found"]:
        return {"lines": [], "results": [], "decision": "NOT_FOUND", "errors": [rec["reason"] + f": {rec['claim_no']}"]}
    line = {"claim_no": rec["claim_no"], "stockist_code": rec["stockist_code"], "batch_no": rec["batch_no"], "sku_code": rec["sku_code"],
            "qty": rec["qty_claimed"], "claim_type": rec["claim_type"], "claim_date": rec["claim_date"],
            "invoice_ref": rec["original_invoice_ref"], "cnf_code": rec["cnf_code"], "expiry_as_claimed": rec["expiry_date_as_claimed"],
            "register_status": rec["status"], "register_cn": rec["credit_note_no"] or None, "source": f"expiry_claims.csv row {rec['src_row']}"}
    return {"lines": [line]}


def manual_line(state: State) -> dict:
    p = dict(state["payload"])
    p.setdefault("claim_date", C_TODAY())
    p["source"] = "typed by user"
    return {"lines": [p]}


def C_TODAY():
    import config
    return config.DATA_CUTOFF


def read_email(state: State) -> dict:
    p = state["payload"]
    if p.get("email_id"):
        e = T.email_record(p["email_id"])
        if not e["found"]:
            return {"errors": [f"Email {e['email_id']} not found in claim_emails.csv"], "lines": []}
    else:
        e = {"email_id": "PASTED", "received_date": d.parse_date(p.get("received_date")) or pd.Timestamp(C_TODAY()),
             "from_name": p.get("from_name", ""), "stockist_code": d.norm_code(p.get("stockist_code", "")),
             "subject": p.get("subject", ""), "body": p.get("body", ""), "src_row": None}
    meter = Meter()
    fields, method = X.extract(e["subject"], e["body"], meter)
    flags = R.injection_flags(e["subject"] + " " + e["body"])
    if fields.contains_instructions and not flags:
        flags = ["model saw instructions addressed to an AI"]
    return {"email": {k: (str(v.date()) if isinstance(v, pd.Timestamp) else v) for k, v in e.items()},
            "fields": fields.model_dump(), "extract_method": method, "flags": flags,
            "usage": [{"node": "read_email", "calls": meter.calls, "in": meter.tok_in, "out": meter.tok_out}]}


KIND = {"breakage": "Breakage in transit", "short_supply": "Short supply"}


def build_lines(state: State) -> dict:
    """Turn extracted fields into claim lines. Code decides claim type from the batch master, and units from the SKU pack."""
    e, f = state["email"], state["fields"]
    lines = []
    for i, ln in enumerate(f.get("lines", []), 1):
        batch = d.norm_code(ln.get("batch_no") or "")
        bat = T.batch_record(batch) if batch else {"found": False}
        kind = KIND.get(ln.get("claim_kind"))
        if not kind:
            kind = "Expired" if bat.get("found") and bat["expiry_date"] < pd.Timestamp(e["received_date"]) else "Near expiry"
        unit = (ln.get("unit") or "").lower()
        qty, unit_ok, unit_text = ln.get("qty"), True, unit or None
        pack = (bat.get("pack") or "").lower() if bat.get("found") else ""
        if unit.startswith(("box", "carton")):
            unit_ok = False
            if ln.get("units_per_unit") and qty:
                unit_text = f"{qty:g} {unit} x {ln['units_per_unit']:g} = {qty * ln['units_per_unit']:g} strips"
                qty = qty * ln["units_per_unit"]
        elif unit.startswith("strip") and pack and not pack.startswith("strip"):
            unit_ok, unit_text = False, f"'{unit}' for a {pack} SKU"
        lines.append({"line_no": i, "stockist_code": e.get("stockist_code"), "batch_no": batch, "product": ln.get("product"), "qty": qty,
                      "unit_ok": unit_ok, "unit_text": unit_text, "claim_type": kind, "claim_date": e["received_date"],
                      "invoice_ref": ln.get("invoice_ref"), "expiry_written": ln.get("expiry"),
                      "expiry_as_claimed": d.parse_expiry_text(ln.get("expiry")),
                      "source": f"claim_emails.csv row {e.get('src_row')} ({e.get('email_id')})"})
    # the same batch and quantity twice in one email is a duplicate line (CO-POL-014 §5.6)
    seen = {}
    for ln in lines:
        k = (ln["batch_no"], ln["qty"])
        if ln["batch_no"] and k in seen:
            ln["dup_of_line"] = seen[k]
        seen.setdefault(k, ln["line_no"])
    return {"lines": lines}


def route_after_email(state: State) -> str:
    if state.get("errors"):
        return "explain"
    f = state.get("fields") or {}
    if f.get("intent") == "status":
        return "claim_status"
    if not f.get("lines"):
        return "explain"
    return "build_lines"


def claim_status(state: State) -> dict:
    out = []
    import config
    nos = list(state["fields"].get("claim_numbers", []))
    for ln in state["fields"].get("lines", []):  # 'what happened to our claim on batch X' -> find it by stockist + batch
        if ln.get("batch_no") and state["email"].get("stockist_code"):
            found = T.prior_claims(state["email"]["stockist_code"], ln["batch_no"])
            nos += [p["claim_no"] for p in found]
            if not found:
                out.append({"claim_no": f"(batch {d.norm_code(ln['batch_no'])})", "found": False,
                            "detail": "No claim from this stockist on this batch in the claims register"})
    for no in nos:
        r = T.claim_record(no)
        if not r["found"]:
            out.append({"claim_no": r["claim_no"], "found": False, "detail": "Not found in the claims register"})
            continue
        age = (pd.Timestamp(state["email"]["received_date"]) - r["claim_date"]).days
        out.append({"claim_no": r["claim_no"], "found": True, "status": r["status"], "claim_date": str(r["claim_date"].date()),
                    "credit_note_no": r["credit_note_no"] or None, "days_open": age if r["status"] == "Pending" else None,
                    "over_target": r["status"] == "Pending" and age > config.CN_TARGET_DAYS, "evidence": r["evidence"]})
    if not out:
        out.append({"found": False, "detail": "No claim number in the email: needs a person to identify the claim"})
    return {"status": out}


def resolve(state: State) -> dict:
    return {"facts": [T.resolve_line(ln) for ln in state.get("lines", [])]}


def _check_node(name):
    fn = T.PARALLEL_CHECKS[name]

    def node(state: State) -> dict:
        return {name: [None if f["stop"] else fn(f) for f in state.get("facts", [])]}
    node.__name__ = f"check_{name}"
    return node


def decide(state: State) -> dict:
    res = []
    for i, f in enumerate(state.get("facts", [])):
        r = T.assemble(f, None if f["stop"] else {k: state[k][i] for k in T.PARALLEL_CHECKS})
        r["line"]["source"] = f["line"].get("source")
        if f["line"].get("dup_of_line"):
            r["checks"].append({"check": "duplicate", "status": R.FAIL, "clause": T.C.CLAUSES["duplicate"],
                                "detail": f"Same batch and quantity as line {f['line']['dup_of_line']} of this email"})
            r["decision"] = "REJECT"
        if f["line"].get("stockist_code") in (None, "") and state.get("email"):
            cands = T.stockist_candidates(state["email"].get("body", "") + " " + state["email"].get("from_name", ""))
            if cands:
                r["checks"].append({"check": "stockist", "status": R.INFO, "clause": T.C.CLAUSES["stockist"],
                                    "detail": "Possible sender (confirm before acting): " + "; ".join(cands)})
        if state.get("flags"):
            r["checks"].append({"check": "untrusted_input", "status": R.PERSON, "clause": "CE-BRF-2026-07 §5.7 mailbox content is untrusted",
                                "detail": f"Email contains instructions aimed at the tool ({', '.join(state['flags'])}); ignored. A person must review."})
            r["decision"] = "REJECT" if r["decision"] == "REJECT" else "NEEDS_PERSON"
        res.append(r)
    order = {"REJECT": 3, "NEEDS_PERSON": 2, "APPROVE": 1}
    overall = max((r["decision"] for r in res), key=lambda x: order[x]) if res else "NEEDS_PERSON"
    return {"results": res, "decision": overall}


def finalise(state: State) -> dict:
    """Every request ends with a decision label, even when no claim line could be checked."""
    if state.get("decision"):
        return {}
    if state.get("status"):
        return {"decision": "STATUS"}
    if state.get("report"):
        return {"decision": "REPORT"}
    if state.get("mode") in ("claim",) and state.get("errors"):
        return {"decision": "NOT_FOUND"}
    topic = (state.get("fields") or {}).get("topic")
    return {"decision": "ROUTE" if topic and topic not in ("claim", "other") else "NEEDS_PERSON"}


def batch_month(state: State) -> dict:
    month = state["payload"].get("month", "2026-09")
    c = d.claims()
    m = c[c.claim_date.dt.strftime("%Y-%m") == month]
    if m.empty:
        return {"report": {"kind": "month", "month": month, "rows": [], "summary": {"claims": 0}}, "errors": [f"No claims logged in {month}"]}
    rows = []
    for r in m.itertuples():
        res = T.check_claim_line({"claim_no": r.claim_no, "stockist_code": r.stockist_code, "batch_no": r.batch_no, "sku_code": r.sku_code,
                                  "qty": r.qty_claimed, "claim_type": r.claim_type, "claim_date": r.claim_date, "invoice_ref": r.original_invoice_ref,
                                  "cnf_code": r.cnf_code, "expiry_as_claimed": r.expiry_date_as_claimed})
        fails = [f"{x['check']}: {x['detail']}" for x in res["checks"] if x["status"] in (R.FAIL, R.PERSON)]
        rows.append({"claim_no": r.claim_no, "row": int(r.src_row), "stockist_code": r.stockist_code, "batch_no": r.batch_no, "claim_type": r.claim_type,
                     "qty": r.qty_claimed, "value_inr": res["value_inr"], "register_status": r.status, "tool_decision": res["decision"],
                     "reasons": fails[:3]})
    df = pd.DataFrame(rows)
    rej = df[df.tool_decision == "REJECT"]
    summ = {"claims": len(df), "approve": int((df.tool_decision == "APPROVE").sum()), "reject": len(rej),
            "needs_person": int((df.tool_decision == "NEEDS_PERSON").sum()),
            "reject_value_inr": round(float(rej.value_inr.fillna(0).sum()), 2),
            "reject_value_already_credited_inr": round(float(rej[rej.register_status == "Credited"].value_inr.fillna(0).sum()), 2),
            "cfa_fee_inr_at_45_per_line": len(df) * 45}
    order = {"REJECT": 0, "NEEDS_PERSON": 1, "APPROVE": 2}
    df = df.sort_values(by="tool_decision", key=lambda s: s.map(order))
    return {"report": {"kind": "month", "month": month, "summary": summ, "rows": df.to_dict("records")}}


def circular_check(state: State) -> dict:
    skus = state["payload"].get("skus") or None
    return {"report": {"kind": "circular", **RP.circular_check(skus)}}


def rebalance(state: State) -> dict:
    return {"report": {"kind": "rebalance", **RP.rebalance()}}


ROUTE = {  # who owns each non-claim topic (CE-BRF-2026-07 §4 owners table)
    "mrp_price": "Regulatory Affairs mailbox (price revision queries, CO-POL-014 §6)",
    "transit_delay": "Subhajit Banerjee, RDM East / regional distribution manager (transporter performance)",
    "scheme_query": "Arjun Sethi's Sales Ops team (scheme circulars)",
    "supply_shortage": "Kavita Rao's Supply Chain team (C&F replenishment)",
    "claim": "a claims executive (claim with no readable line: ask the stockist for batch, quantity and invoice)",
    "other": "a claims executive to read and route",
}


# ------------------------------------------------------------------ explanation (model, guarded) with template fallback
NUM = re.compile(r"\d[\d,]*\.?\d*")


def _numbers(s: str) -> set:
    """Numbers as values, so 18,130 and 18130.00 count as the same figure."""
    return {format(Decimal(n.replace(",", "").rstrip(".")).normalize(), "f") for n in NUM.findall(s or "")}


def _guarded_llm(system: str, content: str, node: str) -> tuple[str | None, str, list]:
    """Model writes prose; we reject it if it contains any number that is not in the input."""
    if not has_key():
        return None, "template (no model key)", []
    try:
        msg = get_llm().invoke([("system", system), ("human", content)])
        u = usage_of(msg)
        usage = [{"node": node, "calls": 1, "in": u["in"], "out": u["out"]}]
        extra = _numbers(msg.content) - _numbers(content)
        extra = {n for n in extra if len(n.replace(".", "")) > 1}  # allow '1'-'9' list markers
        if extra:
            return None, f"template (model note dropped: numbers not in evidence {sorted(extra)[:5]})", usage
        return msg.content.strip(), "model", usage
    except Exception as err:
        return None, f"template (model failed: {type(err).__name__})", []


def _template(state: State) -> str:
    if state.get("errors") and not state.get("results"):
        return "Not found / cannot run: " + "; ".join(state["errors"])
    if state.get("status"):
        parts = []
        for s in state["status"]:
            if not s.get("found"):
                parts.append(f"{s.get('claim_no', 'Claim')}: {s['detail']}.")
            else:
                parts.append(f"{s['claim_no']} logged {s['claim_date']} is {s['status']}" + (f", CN {s['credit_note_no']}" if s.get("credit_note_no") else "")
                             + (f", open {s['days_open']} days (over the 30-day target)" if s.get("over_target") else "") + ".")
        return " ".join(parts)
    if not state.get("results"):
        topic = (state.get("fields") or {}).get("topic", "other")
        owner = ROUTE.get(topic, ROUTE["other"])
        return f"Not a claim the tool can check (topic: {topic.replace('_', ' ')}). Route to {owner}. No credit note action."
    out = []
    for r in state["results"]:
        bad = [c for c in r["checks"] if c["status"] in (R.FAIL, R.PERSON)]
        head = f"Line {r['line'].get('line_no', 1)}: {r['decision'].replace('_', ' ')}"
        if r["value_inr"] is not None:
            head += f" (INR {r['value_inr']:,.2f} at PTS)"
        out.append(head + (". " + " ".join(f"{c['check']}: {c['detail']}." for c in bad) if bad else ". All checks passed."))
    return " ".join(out)


def explain(state: State) -> dict:
    base = _template(state)
    if state.get("results") or state.get("status"):
        payload = json.dumps({"decision": state.get("decision"), "results": [{"line": r["line"], "decision": r["decision"], "value_inr": r["value_inr"],
                              "checks": r["checks"]} for r in state.get("results", [])], "status": state.get("status")}, default=str, ensure_ascii=False)  # keep § literal so the number guard reads clauses correctly
        text, method, usage = _guarded_llm(prompts.EXPLAIN_SYSTEM, payload, "explain")
        return {"explanation": text or base, "explain_method": method, "usage": usage}
    return {"explanation": base, "explain_method": "template"}


def explain_report(state: State) -> dict:
    rep = state.get("report") or {}
    summ = {k: rep.get(k) for k in ("summary", "total_value_inr", "snapshot_date", "month", "cnf_cover", "fefo") if rep.get(k) is not None}
    if rep.get("kind") == "rebalance":
        summ["top_moves"] = [{k: m[k] for k in ("sku_code", "to_cnf", "packs", "value_inr", "from_cnfs")} for m in rep.get("moves", [])[:5]]
    if rep.get("kind") == "circular":
        summ["drop"] = [r["sku_code"] for r in rep.get("rows", []) if r.get("decision") == "DROP"]
    content = json.dumps(summ, default=str, ensure_ascii=False)
    text, method, usage = _guarded_llm(prompts.REPORT_SYSTEM, content, "explain_report")
    if not text:
        k = rep.get("kind")
        s = rep.get("summary", {})
        if k == "month":
            text = (f"{s.get('claims', 0)} claims in {rep.get('month')}: {s.get('approve', 0)} pass, {s.get('reject', 0)} fail a policy rule "
                    f"(INR {s.get('reject_value_inr', 0):,.0f}, of which INR {s.get('reject_value_already_credited_inr', 0):,.0f} already credited), "
                    f"{s.get('needs_person', 0)} need a person. Commercial Finance decides each one.")
        elif k == "circular":
            text = (f"{s.get('drop', 0)} of {s.get('skus', 0)} scheme SKUs return as expiry claims far above their non-scheme rate. Dropping them would save about "
                    f"INR {s.get('saving_if_dropped_inr_per_year', 0):,.0f} a year (FOC plus excess returns). Free goods ran at {s.get('foc_share_of_primary_l12m_pct')}% of primary "
                    f"against the {s.get('cap_pct')}% cap. The NSM decides; the CFO approves any cap exception.")
        elif k == "rebalance":
            text = (f"At {rep.get('snapshot_date')}, {len(rep.get('moves', []))} SKU moves worth INR {rep.get('total_value_inr', 0):,.0f} would bring short C&Fs to one month "
                    f"of cover from C&Fs holding more than two months. Each move is a return-to-CDC that the Head of Supply Chain approves.")
        else:
            text = "; ".join(state.get("errors", [])) or "Report ready."
    return {"explanation": text, "explain_method": method, "usage": usage}


# ------------------------------------------------------------------ wiring
builder = StateGraph(State)
for name, fn in [("intake", intake), ("load_claim", load_claim), ("manual_line", manual_line), ("read_email", read_email),
                 ("build_lines", build_lines), ("claim_status", claim_status), ("resolve", resolve), ("decide", decide),
                 ("batch_month", batch_month), ("circular_check", circular_check), ("rebalance", rebalance),
                 ("explain", explain), ("explain_report", explain_report)]:
    builder.add_node(name, fn)
for name in T.PARALLEL_CHECKS:
    builder.add_node(f"check_{name}", _check_node(name))

builder.add_edge(START, "intake")
builder.add_conditional_edges("intake", route_intake, ["load_claim", "read_email", "manual_line", "batch_month", "circular_check", "rebalance", "explain"])
builder.add_conditional_edges("load_claim", lambda s: "explain" if s.get("errors") else "resolve", ["resolve", "explain"])
builder.add_edge("manual_line", "resolve")
builder.add_conditional_edges("read_email", route_after_email, ["build_lines", "claim_status", "explain"])
builder.add_edge("build_lines", "resolve")
builder.add_edge("claim_status", "explain")
for name in T.PARALLEL_CHECKS:  # fan out: independent checks run in parallel, each writes its own key
    builder.add_edge("resolve", f"check_{name}")
builder.add_edge([f"check_{n}" for n in T.PARALLEL_CHECKS], "decide")  # fan in
builder.add_edge("decide", "explain")
for n in ("batch_month", "circular_check", "rebalance"):
    builder.add_edge(n, "explain_report")
builder.add_node("finalise", finalise)
builder.add_edge("explain", "finalise")
builder.add_edge("explain_report", "finalise")
builder.add_edge("finalise", END)
graph = builder.compile()


def run(mode: str, payload: dict | None = None) -> dict:
    meter = Meter()
    final = graph.invoke({"mode": mode, "payload": payload or {}, "usage": [], "errors": []})
    calls = sum(u.get("calls", 0) for u in final.get("usage", []))
    tin = sum(u.get("in", 0) for u in final.get("usage", []))
    tout = sum(u.get("out", 0) for u in final.get("usage", []))
    m = meter.as_dict()
    m.update(model_calls=calls, tokens_in=tin, tokens_out=tout)
    return json.loads(json.dumps({
        "mode": mode, "decision": final.get("decision"), "explanation": final.get("explanation"), "explain_method": final.get("explain_method"),
        "email": final.get("email"), "extract_method": final.get("extract_method"), "fields": final.get("fields"), "flags": final.get("flags"),
        "results": final.get("results"), "status": final.get("status"), "report": final.get("report"), "errors": final.get("errors"),
        "meter": m}, default=lambda o: None if (isinstance(o, float) and pd.isna(o)) else str(o)))


def mermaid() -> str:
    return graph.get_graph().draw_mermaid()
