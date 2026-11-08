"""Check that numbers recomputed from the recorded trials match the report. Exits non-zero on a mismatch.

Run from the repo root: python scripts/check_numbers.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsyco_lite import load_items, load_run  # noqa: E402
from memsyco_lite.stats import effect, fmt  # noqa: E402

M = "−"
checks = []
main = load_run("1-effect", "main")
facts = main[main.item.isin(load_items("longtail"))]
for model, want in [("mistral-nemo", "+41 [+28, +54]"), ("mistral-small", "+12 [+6, +23]"), ("llama-8b", f"+1 [{M}7, +10]")]:
    checks.append((f"Part 1 {model}", fmt(effect(facts[facts.model == model], "stored_incorrect", "no_belief")), want))
nemo = facts[facts.model == "mistral-nemo"]
checks.append(("Part 1 unrelated", fmt(effect(nemo, "stored_unrelated", "no_belief")), f"+1 [{M}2, +5]"))
checks.append(("Part 1 stated vs stored", fmt(effect(nemo, "stated_incorrect", "stored_incorrect")), f"{M}7 [{M}17, +1]"))
for run, want in [("weak-passage", "+17 [+8, +28]"), ("strong-passage", "+1 [0, +5]")]:
    d = load_run("2-evidence", run)
    checks.append((f"Part 1 {run}", fmt(effect(d[d.model == "mistral-nemo"], "stored_incorrect", "no_belief")), want))
mm = load_run("4-mmlu", "default", scoring="harness_score")
n = mm[mm.model == "mistral-nemo"]
for name, got, want in [
    ("H1", effect(n, "stored_incorrect", "no_belief", paired=False), "+55 [+47, +63]"),
    ("H2", effect(mm[mm.model == "mistral-small"], "stored_incorrect", "no_belief", paired=False), "+35 [+28, +43]"),
    ("H3", effect(n, "stored_incorrect", "stored_incorrect_labelled", paired=False), "+15 [+10, +21]"),
    ("H4", effect(n, "stored_incorrect_labelled", "no_belief", paired=False), "+40 [+32, +48]"),
    ("H5", effect(n, "stored_correct", "no_belief", "correct", paired=False), "+44 [+37, +52]"),
    ("H6 Llama", effect(mm[mm.model == "llama-8b-deepinfra"], "stored_incorrect", "no_belief", paired=False), "+30 [+23, +38]"),
]:
    checks.append((f"Part 3 {name}", fmt(got, halves="up"), want))

charts = json.loads((ROOT / "docs/data/charts.json").read_text())
tut = {r["label"]: (r["a"], r["b"]) for r in charts["6-tutoring"][0]["rows"]}
checks.append(("Site: Haiku told wrong", str(tut["Claude Haiku 5.5"]), "(72, 2)"))
checks.append(("Site: Nemo told wrong", str(tut["Mistral Nemo 12B"]), "(13, 7)"))
f3 = {r["label"]: (r["a"], r["b"]) for r in charts["5-frontier"][1]["rows"]}
checks.append(("Site: Sonnet F3", str(f3["Claude Sonnet 5.5"]), "(25, 85)"))

bad = 0
for name, got, want in checks:
    ok = got == want
    bad += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name:28} {got:18} report: {want}")
print(f"\n{len(checks) - bad} of {len(checks)} match")
sys.exit(1 if bad else 0)
