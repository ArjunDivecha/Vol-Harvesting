"""Compute today's signal and (optionally) send IBKR MOC orders."""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vol_edge.config import AppConfig, load_config
from vol_edge.data.ibkr.snapshots import build_signal_snapshots
from vol_edge.exec.ib_trader import TradeExecutor, get_last_price, get_positions, get_index_price
from vol_edge.signals import (
    compute_erv30,
    compute_evrp,
    compute_term_structure_state,
)
from vol_edge.strategies import StrategyContext, build_strategy


def choose_target_role(decision_weights: dict[str, float]) -> str | None:
    if not decision_weights:
        return None
    role, weight = max(decision_weights.items(), key=lambda kv: abs(kv[1]))
    return role if abs(weight) > 1e-9 else None


def compute_target_shares(
    config: AppConfig,
    role: str | None,
    prices: dict[str, float],
) -> dict[str, int]:
    targets = {config.instruments.long_vol.symbol: 0, config.instruments.short_vol.symbol: 0}
    notional = config.execution.notional_per_trade
    if role is None:
        return targets
    if role == "long_vol":
        price = prices[config.instruments.long_vol.symbol]
        targets[config.instruments.long_vol.symbol] = int(round(notional / price))
    elif role == "short_vol":
        price = prices[config.instruments.short_vol.symbol]
        targets[config.instruments.short_vol.symbol] = int(round(notional / price))
    return targets


def run(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    if config.data.provider != "ibkr":
        raise SystemExit("Config must use data.provider=ibkr for live trading")
    if not config.execution.account_id:
        raise SystemExit("execution.account_id must be set to your IBKR account (e.g., U14983106)")

    target_date = args.date or date.today()
    lookback_days = 20
    snapshots = build_signal_snapshots(config, target_date - timedelta(days=lookback_days), target_date)
    if snapshots.empty or target_date not in snapshots.index.date:
        raise SystemExit(f"No snapshot for {target_date}")
    snap_row = snapshots.loc[str(target_date)]

    spy_history = snapshots["spy"].loc[:str(target_date)].tail(11)
    if len(spy_history) < 11:
        raise SystemExit("Insufficient history for eRV30")

    erv30 = compute_erv30(spy_history.tolist())
    executor = TradeExecutor(config)

    with executor.client as ib:
        vix = get_index_price(ib, config.data.ibkr.vix_symbol)
        vix3m = get_index_price(ib, config.data.ibkr.vix3m_symbol)

        evrp = compute_evrp(vix, erv30)
        term_structure = compute_term_structure_state(vix, vix3m, config.strategy.term_structure_epsilon)

        strategy = build_strategy(config.strategy)
        ctx = StrategyContext(vix=vix, vix3m=vix3m, erv30=erv30, evrp=evrp, term_structure=term_structure)
        decision = strategy.target_weights(ctx)
        role = choose_target_role(decision.weights)

        holdings = get_positions(ib, config.execution.account_id)
        prices = {
            config.instruments.long_vol.symbol: get_last_price(ib, config.instruments.long_vol),
            config.instruments.short_vol.symbol: get_last_price(ib, config.instruments.short_vol),
        }
        targets = compute_target_shares(config, role, prices)
        orders = {}
        for symbol, target_shares in targets.items():
            current = int(round(holdings.get(symbol, 0.0)))
            delta = target_shares - current
            if delta != 0:
                orders[symbol] = delta

        summary = {
            "date": str(target_date),
            "role": role,
            "decision_weights": decision.weights,
            "vix": vix,
            "vix3m": vix3m,
            "prices": prices,
            "current_holdings": holdings,
            "target_shares": targets,
            "order_deltas": orders,
        }
        print(json.dumps(summary, indent=2))

        if args.execute and orders:
            for symbol, delta in orders.items():
                instrument = (
                    config.instruments.long_vol if symbol == config.instruments.long_vol.symbol else config.instruments.short_vol
                )
                order_id = executor.place_moc_order(instrument, delta, ib=ib)
                print(f"Submitted MOC order {order_id} for {symbol} delta {delta}")
        elif not orders:
            print("Already at target; no orders needed.")
        else:
            print("Dry run complete (no orders sent). Use --execute to submit.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate signal and place IBKR MOC orders")
    parser.add_argument("--config", required=True)
    parser.add_argument("--date", type=lambda s: date.fromisoformat(s), help="Target trading date (YYYY-MM-DD)")
    parser.add_argument("--execute", action="store_true", help="Actually submit orders")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
