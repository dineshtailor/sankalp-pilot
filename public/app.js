// Plain JavaScript. Calls /api/run on the same origin. Renders: decision first, then evidence (file, row, clause).
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const inr = (v) => (v === null || v === undefined || v === "" ? "–" : "₹" + Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 }));
let last = null, emails = [];

// ---------- tabs
document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("#tabs button").forEach((x) => x.classList.toggle("on", x === b));
  document.querySelectorAll(".tab").forEach((t) => (t.hidden = t.id !== "tab-" + b.dataset.tab));
  $("#out").hidden = true; $("#state").hidden = true;
}));

// ---------- health + emails
fetch("/api/health").then((r) => r.json()).then((h) => {
  $("#health").textContent = h.model_key_set ? `model: ${h.model}` : "code-only mode (no model key)";
}).catch(() => ($("#health").textContent = "API unreachable"));
fetch("/api/emails").then((r) => r.json()).then((list) => {
  emails = list;
  $("#email-pick").innerHTML = list.map((e) => `<option value="${e.email_id}">${e.email_id} · ${e.received_date} · ${esc(e.from_name)} · ${esc(e.subject)}</option>`).join("");
  showMail();
});
$("#email-pick").addEventListener("change", showMail);
function showMail() {
  const e = emails.find((x) => x.email_id === $("#email-pick").value);
  $("#email-body").textContent = e ? `From: ${e.from_name} (${e.stockist_code || "no stockist code"})\nSubject: ${e.subject}\n\n${e.body}` : "";
}

// ---------- run
document.querySelectorAll("[data-run]").forEach((b) => b.addEventListener("click", () => go(b.dataset.run, b)));
async function go(kind, btn) {
  let mode = kind, payload = {};
  if (kind === "email") payload = { email_id: $("#email-pick").value };
  if (kind === "claim") payload = { claim_no: $("#claim-no").value.trim() };
  if (kind === "paste") { mode = "email"; payload = { stockist_code: $("#p-stk").value, received_date: $("#p-date").value, body: $("#p-body").value, subject: "pasted" }; }
  if (kind === "month") payload = { month: $("#month").value.trim() };
  if (kind === "circular") payload = { skus: $("#skus").value.split(/[\s,]+/).filter(Boolean) };
  if ((kind === "claim" && !payload.claim_no) || (kind === "paste" && !payload.body) || (kind === "email" && !payload.email_id)) return state("Enter or pick something to check first.", true);
  btn.disabled = true; state("Running the checks… (first request after a cold start loads the data, about 5–10 s)");
  $("#out").hidden = true;
  try {
    const r = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode, payload }) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `Server returned ${r.status}`);
    last = data; render(data); $("#state").hidden = true;
  } catch (err) { state(`Something went wrong: ${err.message}. Nothing was decided. Check /api/health.`, true); }
  finally { btn.disabled = false; }
}
function state(msg, err = false) { const s = $("#state"); s.textContent = msg; s.className = "state" + (err ? " err" : ""); s.hidden = false; }

// ---------- render
const LABEL = { APPROVE: "RECOMMEND APPROVE", REJECT: "RECOMMEND REJECT", NEEDS_PERSON: "NEEDS A PERSON", NOT_FOUND: "NOT FOUND", ROUTE: "ROUTE ELSEWHERE", STATUS: "CLAIM STATUS", REPORT: "REPORT" };
const OWNER = { claim: "Decides: claims executive, Commercial Finance (Neha Bansal's team). CN per CO-POL-014 §5.6–5.7.",
  email: "Decides: claims executive, Commercial Finance (Neha Bansal's team). CN per CO-POL-014 §5.6–5.7.",
  month: "Owner: Controller, Commercial Finance (QBR action A2).", circular: "Decides: National Sales Manager (§4.3); CFO for any cap exception (§4.4).",
  rebalance: "Decides: Head of Supply Chain approves each return-to-CDC (SC-AGR-CF-003 Sch.2 2.5)." };
function render(d) {
  const dec = d.decision || "NEEDS_PERSON";
  $("#verdict").innerHTML = `<span class="tag ${dec}">${LABEL[dec] || dec}</span><small>${esc(OWNER[d.mode] || "")}</small>
    <p>${esc(d.explanation || "")}</p><small>Note written by: ${esc(d.explain_method || "template")}${d.extract_method ? " · email read by: " + esc(d.extract_method) : ""}</small>
    ${d.flags && d.flags.length ? `<p class="flag">⚠ Email contains instructions aimed at the tool (${esc(d.flags.join(", "))}). They were ignored.</p>` : ""}`;
  let h = "";
  if (d.results) h += d.results.map(lineCard).join("");
  if (d.status) h += statusTable(d.status);
  if (d.report && d.report.kind === "month") h += monthView(d.report);
  if (d.report && d.report.kind === "circular") h += circularView(d.report);
  if (d.report && d.report.kind === "rebalance") h += rebalanceView(d.report);
  if (d.errors && d.errors.length) h += `<p class="state err">${esc(d.errors.join("; "))}</p>`;
  $("#body").innerHTML = h;
  const m = d.meter || {};
  $("#meter").textContent = `${m.model || ""} · ${m.model_calls ?? 0} model call(s) · ${m.tokens_in ?? 0} in / ${m.tokens_out ?? 0} out tokens · ${m.seconds ?? "?"} s`;
  $("#out").hidden = false;
}
function lineCard(r) {
  const l = r.line || {};
  const checks = r.checks.map((c) => `<tr><td><span class="st ${c.status}">${c.status}</span></td><td>${esc(c.check)}</td><td>${esc(c.detail)}</td><td class="src">${esc(c.clause)}</td></tr>`).join("");
  const ev = (r.evidence || []).map((e) => `<tr><td class="src">${esc(e.file)}</td><td class="num">${e.row ?? "–"}</td><td class="src">${esc(Object.entries(e.values).map(([k, v]) => `${k}=${v}`).join(" · "))}</td></tr>`).join("");
  return `<div class="line"><b>${l.line_no ? "Line " + l.line_no + " · " : ""}${esc(l.batch_no || "no batch")} · ${esc(r.product || l.product || "")}</b>
    — <span class="tag ${r.decision} st">${LABEL[r.decision] || r.decision}</span> · qty ${esc(l.qty ?? "–")} · value at PTS ${inr(r.value_inr)}
    <div class="src">Input: ${esc(l.source || "")}${l.claim_type ? " · " + esc(l.claim_type) : ""}${l.claim_date ? " · claim date " + esc(l.claim_date) : ""}${l.expiry_written ? " · expiry written " + esc(l.expiry_written) : ""}</div>
    <h3>Checks</h3><div class="scroll"><table><tr><th>Result</th><th>Check</th><th>What the data says</th><th>Rule</th></tr>${checks}</table></div>
    <h3>Evidence rows</h3><div class="scroll"><table><tr><th>File</th><th>Row</th><th>Values used</th></tr>${ev || "<tr><td colspan=3>No matching rows</td></tr>"}</table></div></div>`;
}
function statusTable(st) {
  return `<h3>Claims register</h3><div class="scroll"><table><tr><th>Claim</th><th>Status</th><th>Logged</th><th>Credit note</th><th>Days open</th><th>Source</th></tr>${st.map((s) => s.found
    ? `<tr><td>${esc(s.claim_no)}</td><td>${esc(s.status)}</td><td>${esc(s.claim_date)}</td><td>${esc(s.credit_note_no || "–")}</td><td class="num">${s.days_open ?? "–"}${s.over_target ? " ⚠ >30" : ""}</td><td class="src">expiry_claims.csv row ${s.evidence[0].row}</td></tr>`
    : `<tr><td>${esc(s.claim_no || "")}</td><td colspan=5>${esc(s.detail)}</td></tr>`).join("")}</table></div>`;
}
function kpis(items) { return `<div class="kpis">${items.map(([v, k]) => `<div class="kpi"><b>${v}</b><span>${esc(k)}</span></div>`).join("")}</div>`; }
function monthView(r) {
  const s = r.summary || {};
  return kpis([[s.claims ?? 0, "claims logged"], [s.approve ?? 0, "pass all checks"], [s.reject ?? 0, "fail a policy rule"], [s.needs_person ?? 0, "need a person"], [inr(s.reject_value_inr), "value failing a rule"], [inr(s.reject_value_already_credited_inr), "of which already credited"]]) +
    `<h3>Claims, worst first</h3><div class="scroll"><table><tr><th>Claim</th><th>Row</th><th>Stockist</th><th>Batch</th><th>Type</th><th>Qty</th><th>Value</th><th>Register</th><th>Tool</th><th>Why</th></tr>${(r.rows || []).map((x) =>
      `<tr><td>${esc(x.claim_no)}</td><td class="num src">${x.row}</td><td>${esc(x.stockist_code)}</td><td>${esc(x.batch_no)}</td><td>${esc(x.claim_type)}</td><td class="num">${x.qty ?? "–"}</td><td class="num">${inr(x.value_inr)}</td><td>${esc(x.register_status)}</td><td><span class="st ${x.tool_decision === "APPROVE" ? "PASS" : x.tool_decision === "REJECT" ? "FAIL" : "PERSON"}">${esc(x.tool_decision)}</span></td><td>${esc((x.reasons || []).join(" | "))}</td></tr>`).join("")}</table></div><p class="src">Source: expiry_claims.csv (row = record number), checked against primary_sales.csv and batch_master.csv.</p>`;
}
function circularView(r) {
  const s = r.summary || {};
  return kpis([[s.drop ?? 0, `of ${s.skus ?? 0} SKUs: recommend drop`], [inr(s.saving_if_dropped_inr_per_year), "FOC + excess returns a year"], [(s.foc_share_of_primary_l12m_pct ?? "–") + "%", `free goods / primary, cap ${s.cap_pct}%`], [inr((r.moq || {}).foc_inr), `free goods below the 1.5x minimum order (${(r.moq || {}).pairs_below ?? 0} of ${(r.moq || {}).pairs ?? 0} stockist-SKU-months), last 12 m`]]) +
    `<h3>SKUs on the circular</h3><div class="scroll"><table><tr><th>SKU</th><th>Product</th><th>Scheme lots claimed back</th><th>Non-scheme</th><th>FOC cost, last 12 m</th><th>Excess returns, last 12 m</th><th>Recommendation</th></tr>${r.rows.map((x) =>
      `<tr><td>${esc(x.sku_code)}</td><td>${esc(x.product || "")}</td><td class="num">${x.scheme_claimback_pct ?? "–"}%</td><td class="num">${x.non_scheme_claimback_pct ?? "–"}%</td><td class="num">${inr(x.foc_cost_l12m_inr)}</td><td class="num">${inr(x.excess_returns_l12m_inr)}</td><td><span class="st ${x.decision === "DROP" ? "FAIL" : x.decision === "KEEP" ? "PASS" : x.decision === "REVIEW SUPPLY" ? "PERSON" : "INFO"}">${esc(x.decision)}</span> ${esc(x.reason || "")}</td></tr>`).join("")}</table></div>
    <p class="src">${esc(r.clause)}. Method: expiry claims attributed pro rata to the invoice lines of the same stockist and batch; only batches expired by 30-09-2026. Sources: primary_sales.csv, expiry_claims.csv, sku_master.csv.</p>
    <h3>Stockist watchlist: RSM to confirm closing stock before accepting a scheme order (§4.5)</h3><div class="scroll"><table><tr><th>Stockist</th><th>C&amp;F</th><th>SKU</th><th>Scheme packs bought</th><th>Claimed back</th><th>Rows</th></tr>${(r.watchlist || []).map((w) =>
      `<tr><td>${esc(w.stockist_code)} ${esc(w.name)}</td><td>${esc(w.cnf_code)}</td><td>${esc(w.sku_code)}</td><td class="num">${w.scheme_packs}</td><td class="num">${w.claimback_pct}%</td><td class="src">primary_sales.csv ${esc(w.evidence_rows["primary_sales.csv"].join(", "))}</td></tr>`).join("")}</table></div>`;
}
function strandedTable(x) {
  if (!x) return "";
  const rows = x.rows.map((l) => `<tr><td>${esc(l.cnf_code)}</td><td>${esc(l.batch_no)}</td><td>${esc(l.sku_code)} ${esc(l.product)}</td><td>${esc(l.therapy_area)}</td><td class="num">${l.packs}</td><td class="num">${inr(l.value_inr)}</td><td>${esc(l.last_dispatch)}</td><td>${esc(l.blocked_from)}</td><td class="src">cnf_stock_snapshot.csv ${esc(l.evidence_rows["cnf_stock_snapshot.csv"].join(", "))}; primary_sales.csv ${esc(l.evidence_rows["primary_sales.csv"].join(", "))}</td></tr>`).join("");
  return `<h3>Stranded lots to pick first: ${x.summary.lots} lots, ${inr(x.summary.value_inr)}</h3><div class="scroll"><table><tr><th>C&amp;F</th><th>Batch</th><th>Product</th><th>Therapy</th><th>Packs</th><th>Value at PTS</th><th>Last shipped</th><th>Blocked from</th><th>Rows</th></tr>${rows || "<tr><td colspan=9>None found</td></tr>"}</table></div><p class="src">${esc(x.method)} ${esc(x.clause)}.</p>`;
}
function rebalanceView(r) {
  const fefo = (r.fefo || []).map((f) => `<tr><td>${esc(f.cnf_code)}</td><td class="num">${f.fefo_breach_proxy_pct}%</td><td class="num">${f.low_rsl_packs_pct}%</td><td>${f.flag ? '<span class="st FAIL">INVESTIGATE</span>' : '<span class="st PASS">OK</span>'}</td></tr>`).join("");
  const cov = (r.cnf_cover || []).map((c) => `<tr><td>${esc(c.cnf_code)}</td><td class="num">${c.cover_months}</td><td class="num">${c.skus_zero_stock}</td></tr>`).join("");
  const al = (r.allocation || []).map((a) => `<tr><td>${esc(a.cnf_code)}</td><td class="num">${a.demand_share_fy25}%</td><td class="num">${a.demand_share_last6m}%</td><td class="num">${a.supply_share_last6m}%</td></tr>`).join("");
  return kpis([[r.moves.length, "SKU moves proposed"], [inr(r.total_value_inr), "stock value to move"], [r.snapshot_date, "snapshot used"]]) +
    `<h3>Proposed moves (return to CDC, then re-dispatch)</h3><div class="scroll"><table><tr><th>SKU</th><th>Product</th><th>To</th><th>Cover now (months)</th><th>From (cover)</th><th>Packs</th><th>Value at PTS</th><th>Snapshot rows</th></tr>${r.moves.map((m) =>
      `<tr><td>${esc(m.sku_code)}</td><td>${esc(m.product)}</td><td>${esc(m.to_cnf)}</td><td class="num">${m.to_cover_months ?? 0}</td><td>${esc(m.from_cnfs)}</td><td class="num">${m.packs}</td><td class="num">${inr(m.value_inr)}</td><td class="src">cnf_stock_snapshot.csv ${esc(m.evidence_rows["cnf_stock_snapshot.csv"].join(", "))}</td></tr>`).join("")}</table></div>
    ${strandedTable(r.stranded)}
    <h3>Months of cover by C&amp;F</h3><table><tr><th>C&amp;F</th><th>Cover</th><th>SKUs at zero</th></tr>${cov}</table>
    <h3>Allocation: share of orders vs share of supply</h3><table><tr><th>C&amp;F</th><th>Demand share FY25</th><th>Demand share last 6 m</th><th>Supply share last 6 m</th></tr>${al}</table>
    <h3>FEFO signal, last 3 months (SC-AGR-CF-003 cl. 6.3)</h3><table><tr><th>C&amp;F</th><th>Packs from a newer batch while older shipped</th><th>Packs below 60% shelf life</th><th></th></tr>${fefo}</table>
    <p class="src">${esc(r.clause)}. Target cover 2 months (Sch.2 2.2). Sources: cnf_stock_snapshot.csv, primary_sales.csv, batch_master.csv.</p>`;
}

// ---------- audit-trail export (client-side CSV, no library)
$("#export").addEventListener("click", () => {
  if (!last) return;
  const rows = [["mode", "decision", "item", "check_or_field", "status", "detail", "rule_or_source"]];
  (last.results || []).forEach((r) => r.checks.forEach((c) => rows.push([last.mode, r.decision, r.line.batch_no || r.line.claim_no || "", c.check, c.status, c.detail, c.clause])));
  (last.results || []).forEach((r) => (r.evidence || []).forEach((e) => rows.push([last.mode, r.decision, r.line.batch_no || "", "evidence", "", JSON.stringify(e.values), `${e.file} row ${e.row}`])));
  if (last.report && last.report.rows) last.report.rows.forEach((x) => rows.push([last.mode, x.tool_decision || x.decision, x.claim_no || x.sku_code, "", "", (x.reasons || [x.reason || ""]).join(" | "), x.row ? `expiry_claims.csv row ${x.row}` : ""]));
  if (last.report && last.report.moves) last.report.moves.forEach((m) => rows.push([last.mode, "MOVE", m.sku_code, m.to_cnf, m.packs, m.value_inr, "cnf_stock_snapshot.csv " + m.evidence_rows["cnf_stock_snapshot.csv"].join(" ")]));
  const csv = rows.map((r) => r.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = `sankalp_audit_${last.mode}_${new Date().toISOString().slice(0, 10)}.csv`; a.click();
});
