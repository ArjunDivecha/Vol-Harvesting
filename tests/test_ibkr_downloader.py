from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from vol_edge.config import load_config
from vol_edge.data.ibkr import downloader as dl
from vol_edge.data.ibkr.downloader import (
    _historical_chunks,
    cache_path,
    fetch_minute_bars,
    load_or_fetch,
    load_vix3m_with_fallback,
)


def test_historical_chunks_cover_range():
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end = datetime(2020, 2, 15, tzinfo=timezone.utc)
    chunks = list(_historical_chunks(start, end, chunk_days=30))
    assert len(chunks) == 2
    assert chunks[0][0] == start
    assert chunks[-1][1] == end


def test_cache_path_creates_directory(tmp_path, monkeypatch):
    monkeypatch.setattr("vol_edge.data.ibkr.downloader.Path", lambda p="data/ibkr_cache": tmp_path / "cache")
    path = cache_path("SPY")
    assert path.parent.exists()
    assert path.name == "SPY_1min.parquet"


def test_fetch_minute_bars_converts_timezone(monkeypatch):
    def fake_reqHistoricalData(contract, **kwargs):
        dates = pd.date_range("2020-01-01", periods=2, freq="min", tz="UTC")
        frames = []
        for dt in dates:
            frames.append({"date": dt.isoformat(), "open": 1, "high": 1, "low": 1, "close": 1, "volume": 100})
        return [SimpleNamespace(**row) for row in frames]

    fake_ib = SimpleNamespace(reqHistoricalData=fake_reqHistoricalData)
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    df = fetch_minute_bars(fake_ib, SimpleNamespace(), start, end)
    assert not df.empty
    assert df.index.tz.zone == "America/New_York"


def test_load_or_fetch_reads_cache(tmp_path, monkeypatch):
    cache_file = tmp_path / "SPY_1min.parquet"
    df = pd.DataFrame({"close": [1, 2]}, index=pd.date_range("2020-01-01", periods=2, tz="America/New_York"))
    df.to_parquet(cache_file)
    monkeypatch.setattr("vol_edge.data.ibkr.downloader.cache_path", lambda symbol, base_dir=Path("data/ibkr_cache"): cache_file)

    config = load_config(
        {
            "instruments": {"long_vol": {"symbol": "UVXY"}, "short_vol": {"symbol": "SVXY"}},
            "data": {"provider": "ibkr"},
            "backtest": {"start_date": "2020-01-01"},
        }
    )
    data = load_or_fetch(
        "SPY",
        SimpleNamespace(),
        config,
        datetime(2020, 1, 1, tzinfo=timezone.utc),
        datetime(2020, 1, 2, tzinfo=timezone.utc),
    )
    assert len(data) == 2


def test_load_vix3m_with_fallback(monkeypatch):
    monkeypatch.setattr(dl, "load_or_fetch", lambda *args, **kwargs: pd.DataFrame())

    def fake_download(symbol, start, end, progress, auto_adjust=False):
        idx = pd.date_range("2020-01-01", periods=2, freq="D")
        return pd.DataFrame(
            {
                "Open": [1, 2],
                "High": [1, 2],
                "Low": [1, 2],
                "Close": [1, 2],
                "Adj Close": [1, 2],
                "Volume": [0, 0],
            },
            index=idx,
        )

    monkeypatch.setattr(dl.yf, "download", fake_download)

    config = load_config(
        {
            "instruments": {"long_vol": {"symbol": "UVXY"}, "short_vol": {"symbol": "SVXY"}},
            "data": {"provider": "ibkr"},
            "backtest": {"start_date": "2020-01-01"},
        }
    )

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end = datetime(2020, 1, 3, tzinfo=timezone.utc)
    df = load_vix3m_with_fallback(config, start, end)
    assert not df.empty
    assert "close" in df.columns
