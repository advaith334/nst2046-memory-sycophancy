"""Load the question sets, the recorded trials and the result tables that ship with this repo."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


@lru_cache(maxsize=None)
def load_models() -> dict:
    """Model alias -> name, OpenRouter slug and the host settings we used."""
    return json.loads((DATA / "models.json").read_text())


def model_name(alias: str) -> str:
    return load_models().get(alias, {}).get("name", alias)


@lru_cache(maxsize=None)
def load_items(name: str) -> dict:
    """Question set by name (longtail, useful_memory, mmlu, frontier_headroom, frontier_myths), keyed by id."""
    items = json.loads((DATA / "items" / f"{name}.json").read_text())
    return {i["id"]: i for i in items}


def load_run(experiment: str, run: str, scoring: str = "score") -> pd.DataFrame:
    """Recorded trials for one run, one row per trial.

    Multiple-choice runs get three 0/1 columns: `false` (picked the false option), `correct` and
    `other`. They are NaN when the reply could not be scored, so rates use usable replies only,
    as in the report.

    scoring="score" re-reads every reply with the analysis rule (Parts 1 and 2). scoring="harness_score"
    uses the score the harness logged at run time, which the pre-registered Part 3 analysis used. The two
    differ on a handful of replies.
    """
    df = pd.read_csv(DATA / "results" / experiment / f"{run}.csv", keep_default_na=False, na_values=[""])
    if scoring in df:
        s = df[scoring]
        usable = s.isin(["correct", "false_option", "other_wrong"])
        df["false"] = np.where(usable, (s == "false_option").astype(float), np.nan)
        df["correct"] = np.where(usable, (s == "correct").astype(float), np.nan)
        df["other"] = np.where(usable, (s == "other_wrong").astype(float), np.nan)
    return df


def load_prompts(experiment: str, run: str) -> dict:
    """prompt_id -> the exact messages sent (identical for every model given the same item, condition and repeat)."""
    path = DATA / "results" / experiment / f"{run}.prompts.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_table(name: str) -> pd.DataFrame:
    """A result table as quoted in the report, e.g. load_table('4_preregistered_tests')."""
    return pd.read_csv(DATA / "tables" / f"{name}.csv")


def show_prompt(messages: list[dict]) -> str:
    """Messages as plain text, for printing in a notebook."""
    return "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in messages)
