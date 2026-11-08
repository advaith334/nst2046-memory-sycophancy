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


WORDING = {"base": "Wording: our usual", "notes": "Wording: plain \"Notes:\"", "may_be_wrong": "Wording: \"may be wrong\"",
           "bare_fact": "Wording: just the claim", "said_once": "Wording: \"once said\"", "verified_profile": "Wording: \"verified facts\""}
RUNS = {
    "1-effect": [("main", "Main test: 48 questions, 6 models", "mcq")],
    "2-evidence": [("weak-passage", "A hint in the question", "mcq"), ("strong-passage", "The answer stated in the question", "mcq"),
                   ("false-passage", "A false passage in the question", "mcq")]
    + [(f"wording-{w}", WORDING[w], "mcq") for w in
       ["base", "notes", "may_be_wrong", "bare_fact", "said_once", "verified_profile"]]
    + [("base-model", "Base model (no chat training)", "mcq"), ("instruct-model", "Same model with chat training", "mcq")],
    "3-fixes": [("fix-tutor", "Fix: \"You are a tutor\"", "mcq"), ("fix-patient", "Fix: \"Patient record\"", "mcq"), ("fix-rule", "Fix: checking rule", "mcq"),
                ("fix-answer_first", "Fix: answer before reading the memory", "mcq"), ("fix-memory_gate", "Fix: memory filter", "mcq")],
    "4-mmlu": [("default", "Main test: 120 exam questions", "mcq"), ("tutor-frame", "With \"You are a tutor\"", "mcq"), ("patient-frame", "With \"Patient record\"", "mcq"),
               ("wording-may_be_wrong", "With \"may be out of date or wrong\"", "mcq"), ("claude", "Claude Sonnet check", "mcq")],
    "5-frontier": [("f3-frontier", "Writing about myths: strongest models", "f3"), ("f3-main-models", "Writing about myths: other models", "f3"),
                   ("f2f4-frontier-base", "Hard questions: strongest models", "frontier"), ("f2f4-main-models-base", "Hard questions: other models", "frontier"),
                   ("f2f4-frontier-pushback", "User pushes back: strongest models", "frontier"), ("f2f4-main-models-authority", "\"Expert\" memory: other models", "frontier")],
    "6-tutoring": [("rerun-1500-tokens", "Second run (longer replies)", "tutor"), ("planned", "First run (replies cut off at 500 tokens)", "tutor"),
                   ("frame-tutor_b", "Wording test: \"You are a tutor\"", "tutor"), ("frame-assistant_b", "Wording test: \"You are an AI assistant\"", "tutor")],
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
dose = [{"label": "No evidence", **ci(effect(nemo, "stored_incorrect", "no_belief"))},
        {"label": "A hint", **ci(effect(weak[weak.model == "mistral-nemo"], "stored_incorrect", "no_belief"))},
        {"label": "States the answer", **ci(effect(strong[strong.model == "mistral-nemo"], "stored_incorrect", "no_belief"))}]
wordings = []
for w, label in [("notes", "Plain \"Notes:\" heading"), ("may_be_wrong", "Adds \"may be out of date or wrong\""), ("verified_profile", "Heading \"Verified profile facts\""),
                 ("base", "Our usual: \"User believes that ...\""), ("said_once", "\"User once said that ...\""), ("bare_fact", "Just the claim, no \"User believes\"")]:
    d = load_run("2-evidence", f"wording-{w}")
    s = d[(d.condition == "stored_incorrect") & (d.model == "mistral-nemo")]
    wordings.append({"label": label, "value": pct(s["false"].mean())})

trade = load_table("3_fix_tradeoff")
trade = trade[trade.model == "mistral-nemo"]
fixnames = {"label": "\"Unverified\" label", "rule": "Checking rule", "answer_first": "Answer before memory", "memory_gate": "Memory filter",
            "tutor": "\"You are a tutor\"", "patient": "\"Patient record\""}
fixes = [{"label": fixnames[r.variant], "a": pct(r.harm_removed / r.main_effect), "b": pct(r.benefit_kept / r.main_benefit)}
         for r in trade.itertuples() if r.variant in fixnames]

mm = load_run("4-mmlu", "default", scoring="harness_score")
E = lambda d, c, r, v="false": ci(effect(d, c, r, v, paired=False), "up")  # noqa: E731
mn = mm[mm.model == "mistral-nemo"]
hyp = [{"label": "1. Nemo is pulled", **E(mn, "stored_incorrect", "no_belief")},
       {"label": "2. Small is pulled", **E(mm[mm.model == "mistral-small"], "stored_incorrect", "no_belief")},
       {"label": "3. \"Unverified\" helps Nemo", **E(mn, "stored_incorrect", "stored_incorrect_labelled")},
       {"label": "4. ...but not fully", **E(mn, "stored_incorrect_labelled", "no_belief")},
       {"label": "5. True memory helps Nemo", **E(mn, "stored_correct", "no_belief", "correct")}] + [
       {"label": f"Also pulled: {n}", **E(mm[mm.model == m], "stored_incorrect", "no_belief")}
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
    "1-effect": [{"type": "forest", "title": "How much a false memory raised wrong answers, by model", "read": "Each dot is the rise in wrong answers, in percentage points, when the memory held a false belief. The line shows the range we are 95% confident about. A dot on 0 means no change.", "rows": e1}],
    "2-evidence": [{"type": "forest", "title": "Mistral Nemo: the rise in wrong answers shrinks as the question gives more evidence", "read": "Each dot is the rise in wrong answers caused by the false memory, in percentage points, with its 95% range.", "rows": dose},
                   {"type": "bars", "title": "Mistral Nemo: wrong answers with the same false memory, worded six ways", "read": "Each bar is the share of answers that picked the false option. Running one wording five times only varied between 55% and 61%.", "rows": wordings, "max": 100}],
    "3-fixes": [{"type": "pairs", "title": "Mistral Nemo: what each fix took away and what it kept", "read": "Blue is how much of the harm from false memories the fix removed. Orange is how much of the help from true memories it kept. A good fix would have both bars near 100%.", "a": "Harm removed (%)", "b": "Benefit kept (%)", "rows": fixes, "min": -20, "max": 100}],
    "4-mmlu": [{"type": "forest", "title": "Our five main predictions, plus three more models", "read": "Each dot is the size of an effect in percentage points, with its 95% range. Every range sits clearly above 0, so every prediction held.", "rows": hyp},
               {"type": "pairs", "title": "Does the model tell a true memory from a false one?", "read": "Each bar is how much more often the model followed a true memory than a false one, in percentage points. Big bars mean it could tell them apart. Blue is questions it already knew, orange is questions it got wrong without a memory.", "a": "Questions it knew", "b": "Questions it didn't know", "rows": truth, "min": -10, "max": 100}],
    "5-frontier": [{"type": "bars", "title": "Correct answers on 64 hard questions, with no memory", "read": "The strongest models got almost everything right, so a false memory had little room to change their answers. Brackets show correct answers out of answers given.", "rows": f1acc, "max": 100},
                   {"type": "pairs", "title": "How often a model corrected a myth while writing", "read": "Share of replies that openly said the myth is wrong. Orange is with the myth stored in memory. Every model corrected it more often when it was in memory.", "a": "No memory (%)", "b": "Myth in memory (%)", "rows": f3bars, "max": 100}],
    "6-tutoring": [{"type": "pairs", "title": "How often the tutor told the student their belief was wrong", "read": "Blue is when the note held a wrong belief, so speaking up was right. Orange is when the note held a right belief, so speaking up was a mistake. A good tutor has a long blue bar and a short orange one.", "a": "Note held a wrong belief (%)", "b": "Note held a right belief (%)", "rows": tut, "max": 100}],
}, ensure_ascii=False, indent=1))

(OUT / "runs.json").write_text(json.dumps({exp: [{"id": r, "label": label, "kind": kind} for r, label, kind in runs] for exp, runs in RUNS.items()}, indent=1))
(OUT / "models.json").write_text(json.dumps({k: v["name"] for k, v in json.loads((ROOT / "data/models.json").read_text()).items()}, indent=1))
print("wrote", sorted(p.name for p in OUT.glob("*.json")), len(list((OUT / "runs").glob("*.json"))), "run files")
