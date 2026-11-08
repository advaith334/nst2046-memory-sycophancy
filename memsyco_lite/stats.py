"""Item-level statistics, as in the report.

Each item gives one number: the difference between two conditions within each repeat, averaged over
repeats. Intervals come from resampling items (20,000 resamples, BCa), so two repeats of one item are
never counted as independent evidence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sps

SEED = 2046
B = 20_000


def rate(df: pd.DataFrame, value: str = "false") -> pd.DataFrame:
    """Share of usable replies by model and condition, in percent."""
    return (df.groupby(["model", "condition"])[value].mean() * 100).round(1).unstack()


def item_diff(df: pd.DataFrame, cond: str, ref: str, value: str = "false") -> pd.Series:
    w = df[df["condition"].isin([cond, ref])].pivot_table(
        index=["item", "rep", "evidence_mode"] if "evidence_mode" in df else ["item", "rep"],
        columns="condition", values=value, aggfunc="first")
    if cond not in w or ref not in w:
        return pd.Series(dtype=float)
    return (w[cond] - w[ref]).dropna().groupby("item").mean()


def _bca(theta, boots, jack, alpha=0.05):
    boots = boots[np.isfinite(boots)]
    lo, hi = np.quantile(boots, [alpha / 2, 1 - alpha / 2])
    prop = (boots < theta).mean() + 0.5 * (boots == theta).mean()
    jack = jack[np.isfinite(jack)]
    if not 0 < prop < 1 or boots.std() == 0:
        return float(lo), float(hi)
    z0 = sps.norm.ppf(prop)
    diff = jack.mean() - jack
    denom = (diff**2).sum() ** 1.5
    a = (diff**3).sum() / (6 * denom) if denom > 0 else 0.0
    q = [sps.norm.cdf(z0 + (z0 + z) / (1 - a * (z0 + z))) for z in sps.norm.ppf([alpha / 2, 1 - alpha / 2])]
    return tuple(float(x) for x in np.quantile(boots, q))


def mean_ci(d, b: int = B, seed: int = SEED) -> dict:
    d = np.asarray(d, dtype=float)
    idx = np.random.default_rng(seed).integers(0, len(d), size=(b, len(d)))
    theta = float(np.nanmean(d))
    boots = np.nanmean(d[idx], axis=1)
    jack = np.array([np.nanmean(np.delete(d, i)) for i in np.where(np.isfinite(d))[0]])
    lo, hi = _bca(theta, boots, jack)
    return {"est": theta, "ci_low": lo, "ci_high": hi}


def signflip_p(d) -> float:
    """Exact two-sided sign-flip p-value over items (item effects lie on a 0.25 grid)."""
    d = np.asarray(d, float)
    d = d[np.isfinite(d) & (d != 0)]
    if len(d) == 0:
        return 1.0
    v = np.rint(np.abs(d) * 4).astype(int)
    total = int(v.sum())
    dist = np.zeros(2 * total + 1)
    dist[total] = 1.0
    for x in v:
        dist = 0.5 * (np.roll(dist, x) + np.roll(dist, -x))
    obs = abs(int(np.rint(d.sum() * 4)))
    return float(min(1.0, dist[np.abs(np.arange(-total, total + 1)) >= obs].sum()))


def holm(p) -> np.ndarray:
    p = np.asarray(p, float)
    order = np.argsort(p, kind="stable")
    adj, running = np.empty(len(p)), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(p) - rank) * p[i]))
        adj[i] = running
    return adj


def item_mean_diff(df: pd.DataFrame, cond: str, ref: str, value: str = "false") -> pd.Series:
    """Per item: mean over repeats in `cond` minus mean over repeats in `ref` (the pre-registered rule)."""
    g = df[df["condition"].isin([cond, ref])].groupby(["condition", "item"])[value].mean().unstack(0)
    if cond not in g or ref not in g:
        return pd.Series(dtype=float)
    return (g[cond] - g[ref]).dropna()


def effect(df: pd.DataFrame, cond: str, ref: str, value: str = "false", items=None, paired: bool = True) -> dict:
    """Item-level effect of `cond` against `ref` in points, with a 95% interval and sign-flip p.

    paired=True pairs repeats within item (Parts 1 and 2). paired=False compares item means, the rule
    the pre-registration fixed for Part 3.
    """
    d = item_diff(df, cond, ref, value) if paired else item_mean_diff(df, cond, ref, value)
    if items is not None:
        d = d.reindex(items)
    ci = mean_ci(d.to_numpy())
    return {"effect": 100 * ci["est"], "low": 100 * ci["ci_low"], "high": 100 * ci["ci_high"],
            "items": int(d.notna().sum()), "p": signflip_p(d.to_numpy())}


def fmt(e: dict, halves: str = "even") -> str:
    """'+41 [+28, +54]' in the report's style.

    Parts 1, 2, 4 and 5 rounded halves to the nearest even number (Python's default). The pre-registered
    Part 3 analysis rounded halves away from zero, so pass halves="up" there to match its tables.
    """
    def s(v: float) -> str:
        r = int(np.floor(abs(v) + 0.5)) * (1 if v >= 0 else -1) if halves == "up" else int(round(v))
        return "0" if r == 0 else f"{r:+d}".replace("-", "\u2212")
    return f"{s(e['effect'])} [{s(e['low'])}, {s(e['high'])}]"
