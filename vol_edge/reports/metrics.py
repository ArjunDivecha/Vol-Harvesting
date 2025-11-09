"""Performance metric calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class PerformanceMetrics:
    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    adjusted_max_drawdown: float


def _annualized_return(equity: pd.Series) -> float:
    start, end = equity.iloc[0], equity.iloc[-1]
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0 or start <= 0:
        return 0.0
    years = days / 365.25
    return (end / start) ** (1 / years) - 1 if years > 0 else 0.0


def _daily_returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change().dropna()


def _volatility(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    return float(returns.std(ddof=0) * np.sqrt(252))


def _sortino(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    downside = returns[returns < 0]
    if downside.empty:
        return float(np.inf)
    downside_dev = downside.std(ddof=0) * np.sqrt(252)
    avg = returns.mean() * 252
    return float(avg / downside_dev) if downside_dev != 0 else float(np.inf)


def _max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdowns = equity / running_max - 1
    return float(drawdowns.min())


def _adjusted_mdd(equity: pd.Series, window: int = 20) -> float:
    median_nav = equity.rolling(window).median()
    ratio = equity / median_nav
    drawdowns = ratio - 1
    drawdowns = drawdowns.where(drawdowns < 0, 0.0)
    drawdowns = drawdowns.dropna()
    return float(drawdowns.min()) if not drawdowns.empty else 0.0


def compute_metrics(equity: pd.Series) -> PerformanceMetrics:
    equity = equity.dropna()
    returns = _daily_returns(equity)
    vol = _volatility(returns)
    cagr = _annualized_return(equity)
    sharpe = float((returns.mean() * 252) / vol) if vol else 0.0
    sortino = _sortino(returns)
    return PerformanceMetrics(
        cagr=cagr,
        volatility=vol,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=_max_drawdown(equity),
        adjusted_max_drawdown=_adjusted_mdd(equity),
    )
