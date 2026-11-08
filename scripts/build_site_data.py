"""Build the site's data files (docs/data) from the recorded trials and tables in data/.

Run from the repo root: python scripts/build_site_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsyco_lite import load_items, load_prompts, load_run, load_table, model_name  # noqa: E402
from memsyco_lite.stats import effect, fmt  # noqa: E402

OUT = ROOT / "docs" / "data"
(OUT / "runs").mkdir(parents=True, exist_ok=True)


def pct(x):
    return round(100 * float(x))


def ci(e, halves="even"):
    return {"est": e["effect"], "low": e["low"], "high": e["high"], "text": fmt(e, halves)}


# ------------------------------------------------------------------ playground data, one file per run
def mcq_run(exp, run, scoring="score"):
    df = load_run(exp, run, scoring=scoring)
    cols = ["model", "item", "condition", "rep", scoring, "selected", "prompt_id", "response", "date"]
    df = df[[c for c in cols if c in df]].astype(object).fillna("")
    out = {"kind": "mcq", "trials": df.values.tolist(), "columns": [c if c != scoring else "score" for c in df.columns],
           "prompts": load_prompts(exp, run)}
    (OUT / "runs" / f"{exp}--{run}.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))


def text_run(exp, run, cols):
    df = load_run(exp, run)
    df = df[[c for c in cols if c in df]].astype(object).fillna("")
    out = {"kind": "text", "trials": df.values.tolist(), "columns": list(df.columns), "prompts": load_prompts(exp, run)}
    (OUT / "runs" / f"{exp}--{run}.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))


RUNS = {
    "1-effect": [("main", "Main study, 27 Oct", "mcq")],
    "2-evidence": [("weak-passage", "Weak passage", "mcq"), ("strong-passage", "Passage states the answer", "mcq"),
                   ("false-passage", "False passage vs true memory", "mcq")]
    + [(f"wording-{w}", f"Wording: {w.replace('_', ' ')}", "mcq") for w in
       ["base", "notes", "may_be_wrong", "bare_fact", "said_once", "verified_profile"]]
    + [("base-model", "Nemo base (local)", "mcq"), ("instruct-model", "Nemo instruct (local)", "mcq")],
    "3-fixes": [("fix-tutor", "Tutor frame", "mcq"), ("fix-patient", "Patient frame", "mcq"), ("fix-rule", "Rule on the memory block", "mcq"),
                ("fix-answer_first", "Answer first, then revise", "mcq"), ("fix-memory_gate", "Memory gate", "mcq")],
    "4-mmlu": [("default", "Default wording", "mcq"), ("tutor-frame", "Tutor frame", "mcq"), ("patient-frame", "Patient frame", "mcq"),
               ("wording-may_be_wrong", "Caveat: may be out of date or wrong", "mcq"), ("claude", "Claude check", "mcq")],
    "5-frontier": [("f3-frontier", "F3 free text: Claude Haiku, GPT Terra", "f3"), ("f3-main-models", "F3 free text: main models", "f3"),
                   ("f2f4-frontier-base", "F1 headroom items: frontier", "frontier"), ("f2f4-main-models-base", "F1 headroom items: main models", "frontier"),
                   ("f2f4-frontier-pushback", "F4 pushback: frontier", "frontier"), ("f2f4-main-models-authority", "F4 expert memory: main models", "frontier")],
    "6-tutoring": [("planned", "Planned run (500 tokens)", "tutor"), ("rerun-1500-tokens", "Rerun at 1,500 tokens", "tutor"),
                   ("frame-tutor_b", "Frame test: tutor wording B", "tutor"), ("frame-assistant_b", "Frame test: assistant wording B", "tutor")],
}
for exp, runs in RUNS.items():
    for run, _, kind in runs:
        if kind == "mcq":
            mcq_run(exp, run, "harness_score" if exp == "4-mmlu" else "score")
        elif kind == "f3":
            text_run(exp, run, ["model", "item", "condition", "rep", "outcome", "response"])
        elif kind == "frontier":
            text_run(exp, run, ["model", "item", "condition", "rep", "score", "selected", "response", "transcript"])
        else:
            text_run(exp, run, ["model", "item", "condition", "answer_1_judge_a", "told_wrong_1_judge_a", "answer_2_judge_a",
                                "prompt_id", "reply_1", "student_second", "reply_2"])

# items the playground can show
items = {}
for name in ["longtail", "useful_memory", "mmlu", "frontier_headroom"]:
    for k, v in load_items(name).items():
        items[k] = {"q": v["question"], "o": v["options"], "a": v["answer"], "f": v.get("incorrect_option"),
                    "b": (v.get("beliefs") or {}).get("incorrect") or v.get("memory_record")}
for m in json.loads((ROOT / "data/items/frontier_myths.json").read_text()):
    items[m["id"]] = {"q": m["generate_task"], "draft": m["edit_draft"], "myth": m["false_claim"], "truth": m["truth"]}
(OUT / "items.json").write_text(json.dumps(items, ensure_ascii=False, separators=(",", ":")))

# ------------------------------------------------------------------ headline numbers and charts
MAIN6 = ["mistral-nemo", "mistral-small", "llama-8b", "gemma-moe", "qwen-small", "claude-sonnet"]
main = load_run("1-effect", "main")
facts = main[main.item.isin(load_items("longtail"))]
nemo = facts[facts.model == "mistral-nemo"]
e1 = [{"label": model_name(m), **ci(effect(facts[facts.model == m], "stored_incorrect", "no_belief"))} for m in MAIN6]

weak, strong = load_run("2-evidence", "weak-passage"), load_run("2-evidence", "strong-passage")
dose = [{"label": "No passage", **ci(effect(nemo, "stored_incorrect", "no_belief"))},
        {"label": "Weak passage", **ci(effect(weak[weak.model == "mistral-nemo"], "stored_incorrect", "no_belief"))},
        {"label": "Passage states the answer", **ci(effect(strong[strong.model == "mistral-nemo"], "stored_incorrect", "no_belief"))}]
wordings = []
for w, label in [("notes", "Plain \"Notes:\" heading"), ("may_be_wrong", "\"may be out of date or wrong\""), ("verified_profile", "\"Verified profile facts\""),
                 ("base", "Main wording (rerun)"), ("said_once", "\"User once said that\""), ("bare_fact", "Drop \"User believes that\"")]:
    d = load_run("2-evidence", f"wording-{w}")
    s = d[(d.condition == "stored_incorrect") & (d.model == "mistral-nemo")]
    wordings.append({"label": label, "value": pct(s["false"].mean())})

trade = load_table("3_fix_tradeoff")
trade = trade[trade.model == "mistral-nemo"]
fixnames = {"label": "Label", "rule": "Rule on memory block", "answer_first": "Answer first", "memory_gate": "Memory gate",
            "tutor": "Tutor frame", "patient": "Patient frame"}
fixes = [{"label": fixnames[r.variant], "a": pct(r.harm_removed / r.main_effect), "b": pct(r.benefit_kept / r.main_benefit)}
         for r in trade.itertuples() if r.variant in fixnames]

mm = load_run("4-mmlu", "default", scoring="harness_score")
E = lambda d, c, r, v="false": ci(effect(d, c, r, v, paired=False), "up")  # noqa: E731
mn = mm[mm.model == "mistral-nemo"]
hyp = [{"label": "H1 Harm, Nemo", **E(mn, "stored_incorrect", "no_belief")},
       {"label": "H2 Harm, Mistral Small", **E(mm[mm.model == "mistral-small"], "stored_incorrect", "no_belief")},
       {"label": "H3 Label cuts Nemo's harm", **E(mn, "stored_incorrect", "stored_incorrect_labelled")},
       {"label": "H4 Labelled memory still harms, Nemo", **E(mn, "stored_incorrect_labelled", "no_belief")},
       {"label": "H5 Benefit, Nemo", **E(mn, "stored_correct", "no_belief", "correct")}] + [
       {"label": f"H6 Harm, {n}", **E(mm[mm.model == m], "stored_incorrect", "no_belief")}
       for m, n in [("llama-8b-deepinfra", "Llama 3.1 8B"), ("qwen-small", "Qwen3.5-9B"), ("gemma-moe", "Gemma 4 26B")]]
ts = load_table("4_truth_sensitivity").set_index("model")
truth = [{"label": model_name(m).split(" (")[0], "a": pct(ts.loc[m, "knew"]), "b": pct(ts.loc[m, "unsure"])}
         for m in ["mistral-nemo", "llama-8b-deepinfra", "mistral-small", "gemma-moe", "qwen-small"]]

f3 = pd.concat([load_run("5-frontier", "f3-frontier"), load_run("5-frontier", "f3-main-models")])
f3w = f3[f3.task == "generate"]
order5 = ["claude-sonnet", "claude-haiku", "gpt-terra-openai", "mistral-nemo", "mistral-small", "llama-8b-deepinfra", "qwen-small", "gemma-moe"]
f3bars = [{"label": model_name(m).split(" (")[0], "a": pct(f3w[(f3w.model == m) & (f3w.memory == "none")].outcome.eq("corrects_openly").mean()),
           "b": pct(f3w[(f3w.model == m) & (f3w.memory == "stored")].outcome.eq("corrects_openly").mean())} for m in order5]
f1 = pd.concat([load_run("5-frontier", "f1-frontier"), load_run("5-frontier", "f1-main-models")])
f1acc = []
for m in order5:
    sc = f1[f1.model == m].score
    right, answered = int((sc == "correct").sum()), int(sc.isin(["correct", "false_option", "other_wrong"]).sum())
    f1acc.append({"label": f"{model_name(m).split(' (')[0]} ({right}/{answered})", "value": pct(right / answered)})

rr = load_table("6_by_model_rerun").set_index("model")
tut = []
for m in ["mistral-nemo", "llama-8b-deepinfra", "mistral-small", "claude-haiku", "claude-sonnet"]:
    r = rr.loc[m]
    tut.append({"label": model_name(m).split(" (")[0], "a": pct(r["told_note_false"]), "b": pct(r["told_note_true"])})

(OUT / "charts.json").write_text(json.dumps({
    "1-effect": [{"type": "forest", "title": "Rise in false answers with a stored false belief (points, 95% interval)", "rows": e1}],
    "2-evidence": [{"type": "forest", "title": "Nemo: rise in false answers, by evidence in the question (points)", "rows": dose},
                   {"type": "bars", "title": "Nemo: false answers with the same false memory, by wording (%). Five identical runs ranged 55 to 61%.", "rows": wordings, "max": 100}],
    "3-fixes": [{"type": "pairs", "title": "Nemo: share of harm removed vs share of benefit kept (%)", "a": "Harm removed", "b": "Benefit kept", "rows": fixes, "min": -20, "max": 100}],
    "4-mmlu": [{"type": "forest", "title": "Pre-registered tests (points, 95% interval)", "rows": hyp},
               {"type": "pairs", "title": "Truth-sensitivity: following a true note minus a false one (points)", "a": "Items it knew", "b": "Items it was unsure of", "rows": truth, "min": -10, "max": 100}],
    "5-frontier": [{"type": "bars", "title": "F1: correct with no memory, out of replies that gave an answer (%)", "rows": f1acc, "max": 100},
                   {"type": "pairs", "title": "F3: replies that openly correct the myth, writing task (%)", "a": "No memory", "b": "Myth stored", "rows": f3bars, "max": 100}],
    "6-tutoring": [{"type": "pairs", "title": "Tutor told the student they were wrong (%)", "a": "False note", "b": "True note", "rows": tut, "max": 100}],
}, ensure_ascii=False, indent=1))

(OUT / "runs.json").write_text(json.dumps({exp: [{"id": r, "label": label, "kind": kind} for r, label, kind in runs] for exp, runs in RUNS.items()}, indent=1))
(OUT / "models.json").write_text(json.dumps({k: v["name"] for k, v in json.loads((ROOT / "data/models.json").read_text()).items()}, indent=1))
print("wrote", sorted(p.name for p in OUT.glob("*.json")), len(list((OUT / "runs").glob("*.json"))), "run files")
