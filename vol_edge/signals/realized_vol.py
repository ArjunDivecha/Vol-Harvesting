"""Realized volatility calculations."""

from __future__ import annotations

import math
from typing import Iterable

import pandas as pd


def compute_erv30(adj_closes: Iterable[float], window: int = 10, trading_days: int = 252) -> float:
    """Compute the expected 30-day realized vol from the last `window` daily returns."""

    series = pd.Series(list(adj_closes)).astype(float)
    if len(series) < window + 1:
        raise ValueError("need at least window+1 closes to compute returns")
    returns = series.pct_change().dropna()
    recent = returns.tail(window)
    if len(recent) < window:
        raise ValueError("insufficient returns for window")
    stdev = recent.std(ddof=0)
    return float(stdev * math.sqrt(trading_days) * 100)
