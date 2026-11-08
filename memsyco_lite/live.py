"""Rerun recorded trials on OpenRouter with your own key.

Every recorded trial keeps the exact messages we sent, so a live rerun sends the same request to the
same model on the same host, with the same settings. A spend cap stops the run before it costs more
than you allow.
"""

from __future__ import annotations

import getpass
import json
import os
import time

import pandas as pd

from .data import load_models, load_prompts
from .parse import score_mcq

OPENROUTER = "https://openrouter.ai/api/v1"


def get_key(name: str = "OPENROUTER_API_KEY") -> str:
    """Colab Secrets first, then the environment, then a prompt (the key is never printed)."""
    try:
        from google.colab import userdata  # type: ignore

        k = userdata.get(name)
        if k:
            return k
    except Exception:
        pass
    return os.environ.get(name) or getpass.getpass(f"{name}: ")


class SpendCapReached(RuntimeError):
    pass


class Client:
    """OpenAI-compatible client with retries, per-call cost from OpenRouter, and a hard cap in US$."""

    def __init__(self, api_key: str, cap_usd: float = 0.50, base_url: str = OPENROUTER):
        from openai import OpenAI

        self.client = OpenAI(base_url=base_url, api_key=api_key, max_retries=0, timeout=120)
        self.cap, self.spent, self.calls = cap_usd, 0.0, 0

    def chat(self, alias: str, messages: list[dict], temperature: float = 0.7, max_tokens: int = 2000) -> dict:
        if self.spent >= self.cap:
            raise SpendCapReached(f"spend cap of US${self.cap:.2f} reached")
        spec = load_models()[alias]
        if spec.get("local"):
            raise ValueError(f"{alias} ran on a local llama.cpp server, not OpenRouter")
        extra = dict(spec.get("extra_body") or {})
        max_tokens = extra.pop("max_tokens", max_tokens)
        extra.pop("logprobs", None)
        extra["usage"] = {"include": True}
        for attempt in range(5):
            try:
                r = self.client.chat.completions.create(model=spec["slug"], messages=messages, temperature=temperature,
                                                        max_tokens=max_tokens, extra_body=extra)
                break
            except Exception as e:  # rate limits, timeouts, a host that is briefly down
                if attempt == 4:
                    return {"text": "", "error": str(e)[:200], "cost": 0.0, "host": None}
                time.sleep(2 ** attempt)
        raw = r.model_dump()
        cost = float((raw.get("usage") or {}).get("cost") or 0.0)
        self.spent += cost
        self.calls += 1
        msg = raw["choices"][0].get("message") or {}
        return {"text": msg.get("content") or "", "error": None, "cost": cost, "host": raw.get("provider"),
                "finish": raw["choices"][0].get("finish_reason")}


def estimate_cost(recorded: pd.DataFrame) -> float:
    """What the same trials cost us, from the logged cost per trial (US$)."""
    return float(recorded["cost_usd"].fillna(0).sum()) if "cost_usd" in recorded else float("nan")


def rerun_mcq(client: Client, recorded: pd.DataFrame, experiment: str, run: str, items: dict) -> pd.DataFrame:
    """Send each recorded trial's exact prompt again and score the new reply the same way."""
    prompts = load_prompts(experiment, run)
    out = []
    for r in recorded.itertuples():
        try:
            res = client.chat(r.model, prompts[r.prompt_id])
        except SpendCapReached as e:
            print(e)
            break
        chosen, score = score_mcq(res["text"], r.option_order, items[r.item]) if not res["error"] else (None, "error")
        out.append({"trial_id": r.trial_id, "model": r.model, "item": r.item, "condition": r.condition, "rep": r.rep,
                    "evidence_mode": getattr(r, "evidence_mode", "as_written"), "recorded_score": r.score,
                    "score": score, "host": res["host"], "cost_usd": res["cost"], "response": res["text"]})
    df = pd.DataFrame(out)
    if len(df):
        usable = df["score"].isin(["correct", "false_option", "other_wrong"])
        df["false"] = (df["score"] == "false_option").where(usable).astype(float)
        df["correct"] = (df["score"] == "correct").where(usable).astype(float)
    print(f"{client.calls} calls, US${client.spent:.4f} spent")
    return df


def sample(df: pd.DataFrame, models: list[str], conditions: list[str], n_items: int = 10, reps=(1,), seed: int = 0) -> pd.DataFrame:
    """A small, paired sample: the same items for every model and condition."""
    items = sorted(df["item"].unique())
    rng = pd.Series(items).sample(n=min(n_items, len(items)), random_state=seed).tolist()
    keep = df["model"].isin(models) & df["condition"].isin(conditions) & df["item"].isin(rng)
    if "rep" in df:
        keep &= df["rep"].astype(int).isin(list(reps))
    return df[keep].copy()


def compare(recorded: pd.DataFrame, live: pd.DataFrame, value: str = "false") -> pd.DataFrame:
    """Our recorded rate beside your live rate, on the same trials, in percent."""
    rec = recorded[recorded["trial_id"].isin(live["trial_id"])]
    a = rec.groupby(["model", "condition"])[value].mean().mul(100).round(0).rename("ours")
    b = live.groupby(["model", "condition"])[value].mean().mul(100).round(0).rename("yours")
    n = live.groupby(["model", "condition"]).size().rename("trials")
    return pd.concat([a, b, n], axis=1)


def to_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)
