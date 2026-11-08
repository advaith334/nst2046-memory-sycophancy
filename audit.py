"""Print every experiment's setup, headline results and conclusion from the recorded trials.

    python audit.py            # all parts
    python audit.py --part 3   # one part

Nothing calls a model. Numbers are recomputed from data/results with the same item-level method as the report.
"""

from __future__ import annotations

import argparse

import pandas as pd

from memsyco_lite import load_items, load_run, load_table, model_name
from memsyco_lite.stats import effect, fmt

LINE = "-" * 78


def head(title: str, setup: list[str]) -> None:
    print(f"\n{LINE}\n{title}\n{LINE}")
    for s in setup:
        print(f"  * {s}")
    print()


def part1() -> None:
    head("PART 1. The effect (27 Oct 2026, 3,552 trials)", [
        "48 obscure-fact questions x 6 conditions x 2 repeats x 6 models, fresh requests.",
        "Measure: rise in choosing the false option over the model's own no-memory baseline (points)."])
    df = load_run("1-effect", "main")
    facts = df[df.item.isin(load_items("longtail"))]
    for m in ["mistral-nemo", "mistral-small", "llama-8b", "gemma-moe", "qwen-small", "claude-sonnet"]:
        print(f"  {model_name(m):22} stored false belief: {fmt(effect(facts[facts.model == m], 'stored_incorrect', 'no_belief'))}")
    nemo = facts[facts.model == "mistral-nemo"]
    print(f"\n  Nemo, true memory, accuracy: {fmt(effect(nemo, 'stored_correct', 'no_belief', 'correct'))}")
    print(f"  Nemo, unrelated memory:      {fmt(effect(nemo, 'stored_unrelated', 'no_belief'))}")
    for run, label in [("weak-passage", "weak passage"), ("strong-passage", "passage states the answer")]:
        d = load_run("2-evidence", run)
        print(f"  Nemo, {label + ':':28}{fmt(effect(d[d.model == 'mistral-nemo'], 'stored_incorrect', 'no_belief'))}")
    rates = []
    for w in ["notes", "may_be_wrong", "verified_profile", "base", "said_once", "bare_fact"]:
        d = load_run("2-evidence", f"wording-{w}")
        s = d[(d.condition == "stored_incorrect") & (d.model == "mistral-nemo")]
        rates.append(f"{w} {100 * s['false'].mean():.0f}%")
    print("  Nemo false answers by wording: " + ", ".join(rates))
    base, inst = load_run("2-evidence", "base-model"), load_run("2-evidence", "instruct-model")
    print(f"  Base vs instruct (local Nemo): {fmt(effect(base, 'stored_incorrect', 'no_belief'))} vs "
          f"{fmt(effect(inst[inst.model == 'nemo-instruct-local'], 'stored_incorrect', 'no_belief'))}"
          " (the report's +48 scores one reply differently)")
    print("\n  -> A stored false belief moved Nemo strongly. Evidence and wording controlled how much.")


def part2() -> None:
    head("PART 2. Fixes as a trade-off (5 Nov 2026, post hoc)", [
        "Harm = rise in false answers with a false memory. Benefit = rise in accuracy with a true memory.",
        "Shares of Nemo's main harm (+41) and benefit (+24) that each fix removed and kept."])
    t = load_table("3_fix_tradeoff")
    t = t[t.model == "mistral-nemo"]
    for r in t.itertuples():
        print(f"  {r.variant:14} harm removed {100 * r.harm_removed / r.main_effect:5.0f}%   benefit kept {100 * r.benefit_kept / r.main_benefit:5.0f}%")
    print("\n  -> No fix removed the harm while keeping the benefit. The label acts like a volume control.")


def part3() -> None:
    head("PART 3. Pre-registered test on 120 MMLU questions (5 Nov 2026, 9,287 trials)", [
        "Hypotheses committed before the first trial. Item means per condition, harness scores."])
    df = load_run("4-mmlu", "default", scoring="harness_score")
    nemo = df[df.model == "mistral-nemo"]
    E = lambda d, c, r, v="false": fmt(effect(d, c, r, v, paired=False), halves="up")  # noqa: E731
    print(f"  H1 harm, Nemo:                  {E(nemo, 'stored_incorrect', 'no_belief')}")
    print(f"  H2 harm, Mistral Small:         {E(df[df.model == 'mistral-small'], 'stored_incorrect', 'no_belief')}")
    print(f"  H3 label cuts Nemo's harm:      {E(nemo, 'stored_incorrect', 'stored_incorrect_labelled')}")
    print(f"  H4 labelled still harms, Nemo:  {E(nemo, 'stored_incorrect_labelled', 'no_belief')}")
    print(f"  H5 benefit, Nemo:               {E(nemo, 'stored_correct', 'no_belief', 'correct')}")
    for m in ["llama-8b-deepinfra", "qwen-small", "gemma-moe"]:
        print(f"  H6 harm, {model_name(m).split(' (')[0]:22}{E(df[df.model == m], 'stored_incorrect', 'no_belief')}")
    ts = load_table("4_truth_sensitivity").set_index("model")
    print(f"\n  Truth-sensitivity, Nemo: knew +{100 * ts.loc['mistral-nemo', 'knew']:.0f}, unsure +{100 * ts.loc['mistral-nemo', 'unsure']:.0f}")
    print("\n  -> All five primary hypotheses passed, and every open model moved.")


def part4() -> None:
    head("PART 4. Frontier models (6 Nov 2026, 5,536 trials, exploratory)", [
        "F1 headroom on 64 computed questions, F2 test cues, F3 free-text myths, F4 pressure."])
    f1 = pd.concat([load_run("5-frontier", "f1-frontier"), load_run("5-frontier", "f1-main-models")])
    for m in ["claude-sonnet", "gpt-terra-openai", "claude-haiku"]:
        sc = f1[f1.model == m].score
        print(f"  {model_name(m):22} correct with no memory: {(sc == 'correct').sum()} of {sc.isin(['correct', 'false_option', 'other_wrong']).sum()}")
    f3 = pd.concat([load_run("5-frontier", "f3-frontier"), load_run("5-frontier", "f3-main-models")])
    w = f3[f3.task == "generate"]
    for m in ["claude-sonnet", "claude-haiku"]:
        a = 100 * w[(w.model == m) & (w.memory == "none")].outcome.eq("corrects_openly").mean()
        b = 100 * w[(w.model == m) & (w.memory == "stored")].outcome.eq("corrects_openly").mean()
        print(f"  {model_name(m):22} corrects the myth openly: {a:.0f}% -> {b:.0f}% with the myth stored")
    print("\n  -> Frontier models were almost never unsure, so we cannot tell resistance from knowledge.")


def part5() -> None:
    head("PART 5. Three-role tutoring simulation (7 Nov 2026, 5,380 trials)", [
        "Student asks, model tutors in free text, two AI judges read each reply with the key.",
        "Open models use the rerun at 1,500 tokens; Claude models the planned run."])
    rr = load_table("6_by_model_rerun").set_index("model")
    for m in ["mistral-nemo", "llama-8b-deepinfra", "mistral-small", "claude-haiku", "claude-sonnet"]:
        r = rr.loc[m]
        print(f"  {model_name(m).split(' (')[0]:20} told the student they were wrong: false note {100 * r.told_note_false:3.0f}%, "
              f"true note {100 * r.told_note_true:3.0f}%; false after pushback (no note) {100 * r.false2_none:3.0f}%")
    t = load_table("6_planned_tests")
    print(f"\n  Planned predictions passed: {int(t['pass'].sum())} of {len(t)}")
    print("\n  -> Knowledge, not role, decided whether a tutor used the note to correct the student.")


CONCLUSION = """
CONCLUSION
  These models do not check a stored statement against the truth. They weigh it against what they
  already know and what else is in the prompt. Where their knowledge is thin, how much weight it gets
  depends on surface cues such as wording and format, and whether it is true makes little difference.

  Frontier models showed no detectable effect but were almost never unsure on our questions. The people
  who deploy memory should test it with both true and false records, especially for cheaper models and
  niche subjects.

LIMITS
  Synthetic tests in English, no real users. AI-drafted questions in Parts 1 and 2 not yet checked by
  people. Free-text outcomes come from AI judges.
"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--part", type=int, choices=[1, 2, 3, 4, 5])
    args = ap.parse_args()
    parts = {1: part1, 2: part2, 3: part3, 4: part4, 5: part5}
    for k, f in parts.items():
        if args.part in (None, k):
            f()
    if args.part is None:
        print(CONCLUSION)
