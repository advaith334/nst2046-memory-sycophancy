"""Small helpers for the NST2046 memory-sycophancy notebooks: load recorded trials, rebuild prompts,
rerun them on OpenRouter, and compute item-level statistics the way the report does."""

from .data import ROOT, load_items, load_models, load_prompts, load_run, load_table, model_name
from .parse import final_letter, score_mcq
from .stats import effect, holm, rate

__all__ = ["ROOT", "load_items", "load_models", "load_prompts", "load_run", "load_table", "model_name",
           "final_letter", "score_mcq", "effect", "holm", "rate"]
