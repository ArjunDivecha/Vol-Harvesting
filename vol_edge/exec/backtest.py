"""Daily close-based backtest engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from vol_edge.config import AppConfig, DataProvider
from vol_edge.data import MarketData, get_data_source
from vol_edge.data.ibkr.snapshots import build_signal_snapshots
from vol_edge.portfolio import PortfolioState, RebalanceEngine
from vol_edge.signals import (
    TermStructureState,
    compute_erv30,
    compute_evrp,
    compute_term_structure_state,
)
from vol_edge.strategies import StrategyContext, build_strategy


@dataclass
class DailyRecord:
    date: pd.Timestamp
    equity: float
    target_weights: Dict[str, float]
    actual_weights: Dict[str, float]
    vix: float
    vix3m: float
    erv30: float
    evrp: float
    term_structure: TermStructureState


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    benchmark_curve: pd.Series
    records: List[DailyRecord]


def _price(df: pd.DataFrame, ts: pd.Timestamp) -> float:
    row = df.loc[ts]
    if "adj_close" in row:
        return float(row["adj_close"])
    return float(row["close"])


def _ensure_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column]
    raise ValueError(f"Missing column {column}")


def run_backtest(config: AppConfig, data: Optional[MarketData] = None) -> BacktestResult:
    if data is None:
        source = get_data_source(config)
        data = source.load(config.backtest.start_date, config.backtest.end_date)

    spy_adj = _ensure_series(data.spy, "adj_close")
    dates = spy_adj.index
    if len(dates) < 15:
        raise ValueError("Not enough data for backtest")

    use_intraday_signals = config.data.provider == DataProvider.IBKR
    intraday_snapshots = None
    signal_series = spy_adj
    if use_intraday_signals:
        end_date = config.backtest.end_date or dates[-1].date()
        intraday_snapshots = build_signal_snapshots(config, config.backtest.start_date, end_date)
        if intraday_snapshots.empty:
            raise ValueError("No intraday snapshots available")
        signal_series = intraday_snapshots["spy"]

    strategy = build_strategy(config.strategy)
    rebalance = RebalanceEngine(config.strategy.rebalance_threshold_pct)
    portfolio = PortfolioState(cash=config.backtest.initial_equity)
    records: List[DailyRecord] = []

    long_symbol = config.instruments.long_vol.symbol
    short_symbol = config.instruments.short_vol.symbol
    role_to_symbol = {"long_vol": long_symbol, "short_vol": short_symbol}

    equity_series = []
    spy_equity = []
    spy_base = spy_adj.iloc[0]

    window = 10

    for idx in range(window, len(dates)):
        current_date = dates[idx]
        history = signal_series.loc[:current_date].tail(window + 1)
        if len(history) < window + 1:
            continue
        erv30 = compute_erv30(history.tolist())
        if use_intraday_signals:
            if current_date not in intraday_snapshots.index:
                continue
            snap = intraday_snapshots.loc[current_date]
            vix = float(snap["vix"])
            vix3m = float(snap["vix3m"])
        else:
            vix = _price(data.vix, current_date)
            vix3m = _price(data.vix3m, current_date)
        evrp = compute_evrp(vix, erv30)
        term_structure = compute_term_structure_state(vix, vix3m, config.strategy.term_structure_epsilon)

        ctx = StrategyContext(vix=vix, vix3m=vix3m, erv30=erv30, evrp=evrp, term_structure=term_structure)
        decision = strategy.target_weights(ctx)
        target_weights = {role_to_symbol.get(role, role): weight for role, weight in decision.weights.items()}

        prices = {
            short_symbol: _price(data.short_vol, current_date),
            long_symbol: _price(data.long_vol, current_date),
        }
        current_weights = portfolio.weights(prices)
        orders = rebalance.generate_orders(portfolio, target_weights, prices)
        if orders:
            portfolio.apply_orders(orders, prices, cost_bps=config.strategy.trade_cost_bps)
        equity = portfolio.equity(prices)
        equity_series.append((current_date, equity))
        spy_value = spy_adj.loc[current_date] / spy_base * config.backtest.initial_equity
        spy_equity.append((current_date, spy_value))
        records.append(
            DailyRecord(
                date=current_date,
                equity=equity,
                target_weights=target_weights,
                actual_weights=portfolio.weights(prices),
                vix=vix,
                vix3m=vix3m,
                erv30=erv30,
                evrp=evrp,
                term_structure=term_structure,
            )
        )

    equity_curve = pd.Series({dt: val for dt, val in equity_series})
    benchmark_curve = pd.Series({dt: val for dt, val in spy_equity})
    return BacktestResult(equity_curve=equity_curve, benchmark_curve=benchmark_curve, records=records)
