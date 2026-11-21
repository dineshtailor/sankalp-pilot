"""Read a stockist email into fields. The model fills a schema; a regex reader is the fallback (no key / model error).
Neither decides anything: the output is only a list of candidate claim lines for the rules to check."""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from agent import prompts
from agent.llm import get_llm, has_key


class Line(BaseModel):
    product: Optional[str] = None
    batch_no: Optional[str] = None
    expiry: Optional[str] = None
    qty: Optional[float] = None
    unit: Optional[str] = None
    units_per_unit: Optional[float] = None
    invoice_ref: Optional[str] = None
    claim_kind: Literal["near_expiry", "expired", "breakage", "short_supply", "unclear"] = "unclear"


TOPICS = ("claim", "claim_status", "mrp_price", "transit_delay", "scheme_query", "supply_shortage", "other")


class EmailFields(BaseModel):
    intent: Literal["claim", "status", "other"]
    topic: Literal["claim", "claim_status", "mrp_price", "transit_delay", "scheme_query", "supply_shortage", "other"] = "other"
    lines: list[Line] = Field(default_factory=list)
    claim_numbers: list[str] = Field(default_factory=list)
    says_resubmission: bool = False
    contains_instructions: bool = False


BATCH = r"\b([A-Z][0-9O]{7})\b"
INV = r"(INV[-/][NEWS]\d\d[-/]\d{4}[-/]\d{6})"
CLM = r"(CLM-\d{4}-\d{5})"
QTY = r"(?:qty\s*)?(\d[\d,]*)\s*(strips?|packs?|boxes|box|bottles?|tubes?|cartons?)?"


def regex_extract(subject: str, body: str) -> EmailFields:
    text = f"{subject}\n{body}"
    low = text.lower()
    claims = re.findall(CLM, text.upper())
    lines = []
    for raw in body.splitlines():
        b = re.search(BATCH, raw.upper())
        if not b:
            continue
        rest = raw.upper().replace(b.group(1), " ")
        inv = re.search(INV, rest)
        rest_noinv = rest.replace(inv.group(1), " ") if inv else rest
        # quantity: number followed by a unit word, else 'qty N', else a bare number in a table column
        q = re.search(r"(\d[\d,]*)\s*(STRIPS?|PACKS?|BOXES|BOX|BOTTLES?|TUBES?|CARTONS?)\b", rest_noinv)
        if not q:
            q = re.search(r"QTY\s*(\d[\d,]*)", rest_noinv) or re.search(r"\|\s*(\d{1,5})\s*\|", rest_noinv)
        per = re.search(r"\((\d+)\s*STRIPS?\s*EACH\)", rest_noinv)
        exp = re.search(r"(EXP(?:IRY|IRING)?\.?\s*)?((?:\d{1,2}[-/])?(?:\d{1,2}|[A-Z]{3})[-/ ]\d{2,4})", rest_noinv)
        prod = re.split(r",|\|| BATCH", raw)[0].strip(" -1234567890).")
        lines.append(Line(product=prod or None, batch_no=b.group(1), expiry=exp.group(2) if exp else None,
                          qty=float(q.group(1).replace(",", "")) if q else None,
                          unit=(q.group(2).lower() if q and q.lastindex and q.lastindex >= 2 and q.group(2) else None),
                          units_per_unit=float(per.group(1)) if per else None, invoice_ref=inv.group(1) if inv else None,
                          claim_kind="expired" if "expired" in raw.lower() else "unclear"))
    if not lines and not claims:
        # a claim that names a product and quantity but no batch (e.g. 'Amlo 5 ... 168 strips')
        q = re.search(r"(\d[\d,]*)\s*(strips?|packs?|boxes)", low)
        if q and any(w in low for w in ("expiry", "expired", "return", "claim", "credit")):
            lines.append(Line(product=body[:60], qty=float(q.group(1).replace(",", "")), unit=q.group(2)))
    asks_status = bool(claims) or any(w in low for w in ("status", "what happened", "credit note?", "not received", "pending"))
    if lines and asks_status and all(ln.qty is None for ln in lines):
        intent = "status"  # e.g. 'what happened to our claim, batch H2410154?'
    elif lines:
        intent = "claim"
    elif asks_status:
        intent = "status"
    else:
        intent = "claim" if any(w in low for w in ("expired stock", "take back", "expiry return")) else "other"
    topic = {"claim": "claim", "status": "claim_status"}.get(intent, "other")
    if intent == "other":
        if "mrp" in low or "price" in low:
            topic = "mrp_price"
        elif any(w in low for w in ("transit", "took", "days again", "delay", "transport")):
            topic = "transit_delay"
        elif "scheme" in low or "offer" in low:
            topic = "scheme_query"
        elif any(w in low for w in ("out of stock", "no supply", "not available")):
            topic = "supply_shortage"
    from agent.rules import injection_flags
    return EmailFields(intent=intent, topic=topic, lines=lines, claim_numbers=claims,
                       says_resubmission=any(w in low for w in ("resend", "resubmit", "sending again", "again")),
                       contains_instructions=bool(injection_flags(text)))


def extract(subject: str, body: str, meter=None) -> tuple[EmailFields, str]:
    """Returns (fields, method). Model first when a key is set; regex fallback otherwise or on any model error."""
    if has_key():
        try:
            llm = get_llm().with_structured_output(EmailFields, include_raw=True)
            out = llm.invoke([("system", prompts.EXTRACT_SYSTEM), ("human", f"SUBJECT: {subject}\n\nBODY:\n{body}")])
            if meter is not None and out.get("raw") is not None:
                meter.add(out["raw"])
            if out.get("parsed") is not None:
                return out["parsed"], "model"
        except Exception as err:  # model down, bad JSON, timeout: fall back, and say so
            return regex_extract(subject, body), f"regex (model failed: {type(err).__name__})"
    return regex_extract(subject, body), "regex (no model key)"
