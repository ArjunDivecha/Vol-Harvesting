from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from vol_edge.config import AppConfig, load_config
from vol_edge.data import CSVDataSource, MarketData, YahooDataSource, get_data_source


def _write_csv(path: Path, rows: list[dict]):
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def _build_csv_config(tmp_path: Path) -> AppConfig:
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
    rows = [
        {"date": d, "open": i + 1, "high": i + 2, "low": i, "close": i + 1.5, "adj_close": i + 1.4, "volume": 1000}
        for i, d in enumerate(dates)
    ]
    _write_csv(csv_dir / "spy.csv", rows)
    _write_csv(csv_dir / "vix.csv", rows)
    _write_csv(csv_dir / "vix3m.csv", rows)
    _write_csv(csv_dir / "uvxy.csv", rows)
    _write_csv(csv_dir / "svix.csv", rows)

    cfg = load_config(
        {
            "instruments": {
                "long_vol": {"symbol": "UVXY"},
                "short_vol": {"symbol": "SVIX"},
            },
            "data": {
                "provider": "csv",
                "csv": {
                    "spy": str(csv_dir / "spy.csv"),
                    "vix": str(csv_dir / "vix.csv"),
                    "vix3m": str(csv_dir / "vix3m.csv"),
                    "long_vol": str(csv_dir / "uvxy.csv"),
                    "short_vol": str(csv_dir / "svix.csv"),
                },
            },
            "backtest": {"start_date": "2020-01-01", "end_date": "2020-01-02"},
        }
    )
    return cfg


def test_csv_data_source_filters_by_date(tmp_path):
    cfg = _build_csv_config(tmp_path)
    source = get_data_source(cfg)
    assert isinstance(source, CSVDataSource)

    bundle = source.load(cfg.backtest.start_date, cfg.backtest.end_date)
    assert isinstance(bundle, MarketData)
    assert list(bundle.spy.index) == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02")]
    assert bundle.spy.loc["2020-01-01", "close"] == pytest.approx(1.5)
    assert bundle.long_vol.loc["2020-01-02", "adj_close"] == pytest.approx(2.4)


def test_yahoo_source_uses_adjusted_close(monkeypatch, tmp_path):
    cfg = load_config(
        {
            "instruments": {
                "long_vol": {"symbol": "UVXY"},
                "short_vol": {"symbol": "SVIX"},
            },
            "data": {"provider": "yfinance"},
            "backtest": {"start_date": "2020-01-01", "end_date": "2020-01-03"},
        }
    )

    called = {}

    def fake_download(tickers, start, end, auto_adjust, progress):
        called["start"] = start
        called["end"] = end
        called["tickers"] = tickers
        idx = pd.date_range("2020-01-01", periods=3, freq="D")
        data = {
            ("Close", "SPY"): [100, 101, 102],
            ("Adj Close", "SPY"): [99, 100, 101],
            ("Close", "^VIX"): [12, 13, 14],
            ("Adj Close", "^VIX"): [12, 13, 14],
            ("Close", "^VIX3M"): [15, 16, 17],
            ("Adj Close", "^VIX3M"): [15, 16, 17],
            ("Close", "UVXY"): [10, 11, 12],
            ("Adj Close", "UVXY"): [9, 10, 11],
            ("Close", "SVIX"): [7, 7.5, 8],
            ("Adj Close", "SVIX"): [7, 7.4, 7.9],
        }
        df = pd.DataFrame(data, index=idx)
        df.columns = pd.MultiIndex.from_tuples(df.columns)
        return df

    import yfinance as yf

    monkeypatch.setattr(yf, "download", fake_download)

    source = YahooDataSource(cfg)
    bundle = source.load(cfg.backtest.start_date, cfg.backtest.end_date)

    assert called["tickers"] == ["SPY", "^VIX", "^VIX3M", "UVXY", "SVIX"]
    assert bundle.spy.loc["2020-01-01", "adj_close"] == 99
    assert "adj_close" in bundle.long_vol.columns
