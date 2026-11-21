"""FastAPI entrypoint: API routes only, no business logic. Vercel finds the FastAPI instance named `app` here.

Run locally:   uvicorn app:app --reload        then open http://127.0.0.1:8000
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from agent import data as d
from agent.graph import MODES, mermaid, run
from agent.llm import DEFAULT_MODEL, has_key

app = FastAPI(title="Sankalp Channel Guard")
ROOT = Path(__file__).resolve().parent


class RunRequest(BaseModel):
    mode: str
    payload: dict = {}


@app.get("/api/health")
def health():
    """Deployment alive, key configured, data present."""
    return {"ok": True, "model_key_set": has_key(), "model": DEFAULT_MODEL,
            "data_files": sorted(p.name for p in d.DATA.glob("*.csv"))}


@app.post("/api/run")
def run_graph(body: RunRequest):
    if body.mode not in MODES:
        return JSONResponse({"error": f"mode must be one of {MODES}"}, status_code=400)
    try:
        return run(body.mode, body.payload)
    except Exception as err:  # never a bare 500: say what failed
        return JSONResponse({"error": f"{type(err).__name__}: {err}"}, status_code=500)


@app.get("/api/emails")
def list_emails():
    e = d.emails().reset_index(drop=True).sort_values(["received_date", "email_id"])
    return [{"email_id": r.email_id, "received_date": str(r.received_date.date()), "from_name": r.from_name,
             "subject": r.subject, "body": r.body, "stockist_code": r.stockist_code_by_mailbox_rule} for r in e.itertuples()]


@app.get("/api/graph", response_class=PlainTextResponse)
def graph_diagram():
    return mermaid()


@app.get("/")
def index():
    return FileResponse(ROOT / "public" / "index.html")


# On Vercel the public/ folder is served by the platform. Locally nothing serves it, so mount it.
if not os.getenv("VERCEL"):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=ROOT / "public"), name="public")
