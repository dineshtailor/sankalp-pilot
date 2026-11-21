"""The API and graph, end to end, without a model key (code-only mode) and with a fake model."""
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import agent.graph as g
from app import app

client = TestClient(app)


def test_health():
    h = client.get("/api/health").json()
    assert h["ok"] is True and "primary_sales.csv" in h["data_files"]


def test_claim_mode_runs_parallel_checks_and_cites_rows(monkeypatch):
    monkeypatch.setattr(g, "has_key", lambda: False)
    monkeypatch.setattr(g.X, "has_key", lambda: False)
    r = client.post("/api/run", json={"mode": "claim", "payload": {"claim_no": "CLM-2605-04488"}}).json()
    assert r["decision"] == "REJECT"
    checks = {c["check"] for c in r["results"][0]["checks"]}
    assert {"window", "quantity", "duplicate", "invoice_ref"} <= checks
    assert all(e["file"] and e["row"] for e in r["results"][0]["evidence"])


def test_unknown_claim_says_not_found():
    r = client.post("/api/run", json={"mode": "claim", "payload": {"claim_no": "CLM-0000-00000"}}).json()
    assert r["decision"] == "NOT_FOUND"


def test_injection_email_is_never_approved(monkeypatch):
    monkeypatch.setattr(g.X, "has_key", lambda: False)
    r = client.post("/api/run", json={"mode": "email", "payload": {"email_id": "EML-017"}}).json()
    assert r["decision"] in ("REJECT", "NEEDS_PERSON") and r["flags"]


def test_bad_mode_is_400():
    assert client.post("/api/run", json={"mode": "chat", "payload": {}}).status_code == 400


class FakeLLM:
    """Writes a note that sneaks in a number not in the evidence: the guard must drop it."""

    def invoke(self, messages):
        return AIMessage(content="Approve 99999 packs.", usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})


def test_model_note_with_invented_number_is_dropped(monkeypatch):
    monkeypatch.setattr(g, "has_key", lambda: True)
    monkeypatch.setattr(g.X, "has_key", lambda: False)
    monkeypatch.setattr(g, "get_llm", lambda: FakeLLM())
    r = client.post("/api/run", json={"mode": "claim", "payload": {"claim_no": "CLM-2605-04488"}}).json()
    assert "99999" not in r["explanation"] and r["explain_method"].startswith("template (model note dropped")
    assert r["meter"]["model_calls"] == 1


def test_reports_run():
    for mode in ("circular", "rebalance"):
        r = client.post("/api/run", json={"mode": mode, "payload": {}}).json()
        assert r["decision"] == "REPORT" and r["report"]["kind"] == mode
