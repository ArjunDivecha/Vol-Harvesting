"""Daily backtest report builder."""

from __future__ import annotations

from typing import List

import pandas as pd

from vol_edge.config import AppConfig
from vol_edge.exec.backtest import BacktestResult, DailyRecord


def _regime_from_weights(record: DailyRecord, config: AppConfig) -> str:
    weights = record.actual_weights or {}
    long_w = weights.get(config.instruments.long_vol.symbol, 0.0)
    short_w = weights.get(config.instruments.short_vol.symbol, 0.0)
    if abs(long_w) < 1e-6 and abs(short_w) < 1e-6:
        return "cash"
    if abs(long_w) >= abs(short_w):
        return f"long_vol {long_w:.2%}"
    return f"short_vol {short_w:.2%}"


def build_daily_report(result: BacktestResult, config: AppConfig) -> pd.DataFrame:
    """Return a DataFrame with Date, Regime, Position, PnL, Cumulative PnL."""

    equity = result.equity_curve.sort_index()
    daily_pnl = equity.diff().fillna(0.0)
    cumulative_pnl = equity - equity.iloc[0]

    rows: List[dict] = []
    for rec in result.records:
        dt = pd.Timestamp(rec.date)
        regime = _regime_from_weights(rec, config)
        position_desc = ", ".join(
            f"{symbol} {weight:.2%}" for symbol, weight in rec.actual_weights.items()
        )
        rows.append(
            {
                "date": dt.date().isoformat(),
                "strategy": config.strategy.name,
                "regime": regime,
                "position": position_desc or "n/a",
                "pnl": float(daily_pnl.get(dt, 0.0)),
                "cumulative_pnl": float(cumulative_pnl.get(dt, 0.0)),
            }
        )

    return pd.DataFrame(rows)
