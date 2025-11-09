"""Daily data sources for the Volatility Edge backtest."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import pandas as pd
import yfinance as yf

from vol_edge.config import AppConfig, DataProvider


@dataclass
class MarketData:
    spy: pd.DataFrame
    vix: pd.DataFrame
    vix3m: pd.DataFrame
    long_vol: pd.DataFrame
    short_vol: pd.DataFrame


class DataSource(Protocol):
    def load(self, start: date, end: date | None = None) -> MarketData: ...


_REQUIRED_COLS = ["open", "high", "low", "close", "adj_close", "volume"]


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in _REQUIRED_COLS:
        if col not in out.columns:
            out[col] = pd.NA
    return out[_REQUIRED_COLS]


def _load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.set_index("date").sort_index()
    df.columns = [c.lower() for c in df.columns]
    return _ensure_columns(df)


class CSVDataSource:
    def __init__(self, config: AppConfig):
        if not config.data.csv:
            raise ValueError("CSV paths missing in config")
        self.paths = config.data.csv

    def load(self, start: date, end: date | None = None) -> MarketData:
        spy = _load_csv(self.paths.spy)
        vix = _load_csv(self.paths.vix)
        vix3m = _load_csv(self.paths.vix3m)
        long_vol = _load_csv(self.paths.long_vol)
        short_vol = _load_csv(self.paths.short_vol)
        slice_ = slice(pd.Timestamp(start), pd.Timestamp(end) if end else None)
        return MarketData(
            spy=spy.loc[slice_],
            vix=vix.loc[slice_],
            vix3m=vix3m.loc[slice_],
            long_vol=long_vol.loc[slice_],
            short_vol=short_vol.loc[slice_],
        )


class YahooDataSource:
    def __init__(self, config: AppConfig):
        self.config = config

    def load(self, start: date, end: date | None = None) -> MarketData:
        symbols = [
            "SPY",
            "^VIX",
            "^VIX3M",
            self.config.instruments.long_vol.symbol,
            self.config.instruments.short_vol.symbol,
        ]
        data = yf.download(symbols, start=start, end=end, auto_adjust=False, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            frames = {sym: _normalize_from_multiindex(data, sym) for sym in symbols}
        else:
            frames = {"SPY": _ensure_columns(data)}  # fallback for single symbol fetch
        return MarketData(
            spy=frames["SPY"],
            vix=frames["^VIX"],
            vix3m=frames["^VIX3M"],
            long_vol=frames[self.config.instruments.long_vol.symbol],
            short_vol=frames[self.config.instruments.short_vol.symbol],
        )


def _normalize_from_multiindex(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    cols = df.xs(symbol, axis=1, level=1)
    cols = cols.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    })
    cols.index = cols.index.tz_localize(None)
    return _ensure_columns(cols)


def get_data_source(config: AppConfig) -> DataSource:
    if config.data.provider == DataProvider.CSV:
        return CSVDataSource(config)
    # Even when using IBKR for intraday signals we rely on daily Yahoo data for ETNs
    return YahooDataSource(config)
