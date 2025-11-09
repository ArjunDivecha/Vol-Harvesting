from datetime import date

import pandas as pd

from vol_edge.config import StrategyConfig, StrategyName, load_config
from vol_edge.data import MarketData
from vol_edge.exec.backtest import BacktestResult, run_backtest


def make_frame(values):
    dates = pd.date_range("2020-01-01", periods=len(values), freq="B")
    return pd.DataFrame(
        {
            "open": values,
            "high": [v * 1.01 for v in values],
            "low": [v * 0.99 for v in values],
            "close": values,
            "adj_close": values,
            "volume": 1_000,
        },
        index=dates,
    )


def build_bundle(length: int = 40) -> tuple[MarketData, pd.DatetimeIndex]:
    dates = pd.date_range("2020-01-01", periods=length, freq="B")
    spy_vals = [100 + i * 0.2 for i in range(length)]
    spy = make_frame(spy_vals)
    vix = make_frame([18 + (i % 3) for i in range(length)])
    vix3m = make_frame([20 + (i % 2) for i in range(length)])
    long_vol = make_frame([15 - 0.1 * i for i in range(length)])
    short_vol = make_frame([40 + 0.3 * i for i in range(length)])
    return MarketData(spy=spy, vix=vix, vix3m=vix3m, long_vol=long_vol, short_vol=short_vol), dates


def test_backtest_generates_records():
    bundle, dates = build_bundle()
    config = load_config(
        {
            "instruments": {
                "long_vol": {"symbol": "UVXY"},
                "short_vol": {"symbol": "SVIX"},
            },
            "strategy": {"name": "evrp"},
            "backtest": {"start_date": str(dates[0].date()), "end_date": str(dates[-1].date())},
        }
    )

    result = run_backtest(config, data=bundle)
    assert isinstance(result, BacktestResult)
    assert len(result.records) > 0
    last_record = result.records[-1]
    assert "SVIX" in last_record.actual_weights or "UVXY" in last_record.actual_weights
    assert result.equity_curve.iloc[-1] > 0
