import pandas as pd

from vol_edge.reports import compute_metrics


def test_compute_metrics_handles_monotonic_growth():
    dates = pd.date_range("2020-01-01", periods=30, freq="B")
    equity = pd.Series([100 + i for i in range(30)], index=dates)
    metrics = compute_metrics(equity)
    assert metrics.cagr > 0
    assert metrics.max_drawdown == 0.0
    assert metrics.adjusted_max_drawdown == 0.0


def test_metrics_detect_drawdown():
    dates = pd.date_range("2020-01-01", periods=5, freq="B")
    equity = pd.Series([100, 110, 90, 95, 80], index=dates)
    metrics = compute_metrics(equity)
    assert metrics.max_drawdown < 0
    assert metrics.adjusted_max_drawdown <= 0
