"""Draw the LangGraph graph as a clean PNG (colour = code / model / person)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "charts" / "graph.png"
CODE, MODEL, PERSON, IO = ("#ffffff", "#0b1f3a"), ("#f3e8ff", "#7e22ce"), ("#e8f6ee", "#15803d"), ("#eef2f7", "#64748b")
plt.rcParams["font.family"] = "Calibri"
fig, ax = plt.subplots(figsize=(11.5, 6.2)); ax.set_xlim(0, 115); ax.set_ylim(-8, 56); ax.axis("off")
B = {}


def box(key, x, y, text, kind=CODE, w=15, h=5.2, fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.8", fc=kind[0], ec=kind[1], lw=1.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color="#0b1f3a")
    B[key] = (x, y, w, h)


def arrow(a, b, label=None, side="r"):
    xa, ya, wa, ha = B[a]; xb, yb, wb, hb = B[b]
    if side == "r":
        p1, p2 = (xa + wa, ya + ha / 2), (xb, yb + hb / 2)
    else:  # up
        p1, p2 = (xa + wa / 2, ya + ha), (xb + wb / 2, yb)
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=10, color="#475569", lw=1.1))
    if label:
        ax.text((p1[0] + p2[0]) / 2 - 2, (p1[1] + p2[1]) / 2 + 1.2, label, fontsize=7, color="#475569", ha="center")


box("in", 0.5, 24, "Request\nmode + payload", IO, w=12)
box("intake", 15, 24, "intake\nroute by mode", w=13)
box("claim", 32, 44, "load_claim\nclaims register")
box("email", 32, 35, "read_email\nstructured output", MODEL)
box("manual", 32, 26, "manual_line\ntyped claim")
box("status", 51, 44, "claim_status\nregister lookup")
box("build", 51, 35, "build_lines\ntype · units · dupes")
box("resolve", 51, 21, "resolve\nbatch · supply · priors")
checks = (("w", "check_window\n§5.2"), ("q", "check_quantity\n§5.5"), ("dup", "check_duplicate\n§5.6"), ("inv", "check_invoice\n§5.1, §5.3, §5.4"))
for i, (k, t) in enumerate(checks):
    box(k, 70, 37 - i * 7.5, t, h=5)
box("decide", 89, 21, "decide\nAPPROVE · REJECT ·\nNEEDS_PERSON", w=14)
box("explain", 89, 33, "explain\nnumber-guarded note", MODEL, w=14)
box("person", 89, 44, "Claims executive\nraises CN in SAP", PERSON, w=14)
box("month", 32, 10, "batch_month\nmonth audit")
box("circ", 32, 2, "circular_check\n§4.3 – §4.5")
box("reb", 32, -6, "rebalance\ncover · FEFO · allocation")
box("rep", 70, 2, "explain_report\nguarded summary", MODEL)
box("own", 89, 2, "NSM · Head SC ·\nController decide", PERSON, w=14)
for a, b in (("in", "intake"), ("intake", "claim"), ("intake", "email"), ("intake", "manual"), ("intake", "month"), ("intake", "circ"),
             ("intake", "reb"), ("email", "build"), ("claim", "resolve"), ("manual", "resolve"), ("build", "resolve"),
             ("month", "rep"), ("circ", "rep"), ("reb", "rep"), ("rep", "own"), ("status", "explain")):
    arrow(a, b)
arrow("email", "status", "status query")
for k, _ in checks:
    arrow("resolve", k); arrow(k, "decide")
arrow("decide", "explain", side="u"); arrow("explain", "person", side="u")
ax.text(77.5, 43.5, "parallel: one state key each", fontsize=7.5, color="#0f766e", ha="center", style="italic")
for i, (lab, kind) in enumerate((("Plain Python (decides)", CODE), ("Model call (reads / writes)", MODEL), ("A named person (acts)", PERSON))):
    ax.add_patch(FancyBboxPatch((1 + i * 24, 51.5), 2.6, 2.6, boxstyle="round,pad=0.1", fc=kind[0], ec=kind[1], lw=1.4))
    ax.text(4.5 + i * 24, 52.8, lab, fontsize=8.5, va="center")
fig.savefig(OUT, dpi=200, bbox_inches="tight")
print(OUT)
