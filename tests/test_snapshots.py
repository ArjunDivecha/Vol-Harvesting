from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from vol_edge.config import load_config
from vol_edge.data.ibkr import snapshots as snap


def _make_minutes(day: str, base: float) -> pd.DataFrame:
    idx = pd.date_range(f"{day} 15:40", periods=10, freq="min", tz="America/New_York")
    closes = [base + i * 0.1 for i in range(10)]
    return pd.DataFrame({"close": closes}, index=idx)


def test_build_signal_snapshots(monkeypatch):
    spy = pd.concat([
        _make_minutes("2020-01-01", 100.0),
        _make_minutes("2020-01-02", 101.0),
    ])
    vix = spy * 0 + 20
    vix3m = spy * 0 + 25

    def fake_prepare(symbol, builder, config, start, end):
        if symbol == "SPY":
            return spy
        if symbol == "^VIX":
            return vix
        raise AssertionError("unexpected symbol")

    monkeypatch.setattr(snap, "_prepare_minutes", fake_prepare)
    monkeypatch.setattr(snap, "load_vix3m_with_fallback", lambda *args, **kwargs: vix3m)

    config = load_config(
        {
            "instruments": {"long_vol": {"symbol": "UVXY"}, "short_vol": {"symbol": "SVXY"}},
            "data": {"provider": "ibkr"},
            "backtest": {"start_date": "2020-01-01", "end_date": "2020-01-02"},
        }
    )

    df = snap.build_signal_snapshots(config, date(2020, 1, 1), date(2020, 1, 2))
    assert len(df) == 2
    assert df.iloc[0]["spy"] == pytest.approx(100.5)
    assert df.iloc[1]["spy"] == pytest.approx(101.5)
