"""Command line entry points."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vol_edge.config import load_config
from vol_edge.exec.backtest import run_backtest
from vol_edge.reports import compute_metrics


def _run_backtest(config_path: Path) -> None:
    config = load_config(config_path)
    result = run_backtest(config)
    metrics = compute_metrics(result.equity_curve)
    payload = {
        "final_equity": result.equity_curve.iloc[-1],
        "records": len(result.records),
        "cagr": metrics.cagr,
        "sharpe": metrics.sharpe,
        "max_drawdown": metrics.max_drawdown,
    }
    print(json.dumps(payload, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Volatility Edge CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest_parser = subparsers.add_parser("backtest", help="Run a backtest")
    backtest_parser.add_argument("--config", required=True, type=Path)

    args = parser.parse_args()
    if args.command == "backtest":
        _run_backtest(args.config)


if __name__ == "__main__":  # pragma: no cover
    main()
