"""Historical minute downloader for IBKR."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
from ib_insync import BarData, Contract, IB
import yfinance as yf

from vol_edge.config import AppConfig
from .client import IBKRClient

_MAX_DURATION_DAYS = 7  # IBKR limits for 1-min bars when requesting 1-min data


def _contract(symbol: str, sec_type: str = "STK", exchange: str = "SMART", currency: str = "USD") -> Contract:
    contract = Contract()
    contract.symbol = symbol
    contract.secType = sec_type
    contract.exchange = exchange
    contract.currency = currency
    return contract


def _vix_contract(symbol: str) -> Contract:
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "IND"
    contract.exchange = "CBOE"
    contract.currency = "USD"
    return contract


def _historical_chunks(start: datetime, end: datetime, chunk_days: int = _MAX_DURATION_DAYS) -> Iterable[tuple[datetime, datetime]]:
    cursor = start
    while cursor < end:
        next_cursor = min(cursor + timedelta(days=chunk_days), end)
        yield cursor, next_cursor
        cursor = next_cursor


def _what_to_show(contract: Contract) -> str:
    if getattr(contract, "secType", "") == "IND":
        return "MIDPOINT"
    return "TRADES"


def fetch_minute_bars(ib: IB, contract: Contract, start: datetime, end: datetime) -> pd.DataFrame:
    frames = []
    data_type = _what_to_show(contract)
    use_rth = getattr(contract, "secType", "") != "IND"
    for chunk_start, chunk_end in _historical_chunks(start, end):
        duration = f"{(chunk_end - chunk_start).days} D"
        bars: list[BarData] = ib.reqHistoricalData(
            contract,
            endDateTime=chunk_end.astimezone(timezone.utc),
            durationStr=duration,
            barSizeSetting="1 min",
            whatToShow=data_type,
            useRTH=use_rth,
            keepUpToDate=False,
            formatDate=1,
        )
        if not bars:
            continue
        frame = pd.DataFrame(
            {
                "date": [bar.date for bar in bars],
                "open": [bar.open for bar in bars],
                "high": [bar.high for bar in bars],
                "low": [bar.low for bar in bars],
                "close": [bar.close for bar in bars],
                "volume": [getattr(bar, "volume", 0) for bar in bars],
            }
        )
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.concat(frames)
    df = df.drop_duplicates(subset="date")
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert("America/New_York")
    df = df.set_index("date").sort_index()
    return df


def cache_path(symbol: str, base_dir: Path = Path("data/ibkr_cache")) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{symbol}_1min.parquet"


def load_or_fetch(
    symbol: str,
    contract: Contract,
    app_config: AppConfig,
    start: datetime,
    end: datetime,
    allow_empty: bool = False,
) -> pd.DataFrame:
    path = cache_path(symbol)
    if path.exists():
        df = pd.read_parquet(path)
        df.index = pd.to_datetime(df.index)
        return df
    with IBKRClient(app_config.data.ibkr) as ib:
        df = fetch_minute_bars(ib, contract, start, end)
    if not df.empty:
        df.to_parquet(path)
    elif allow_empty and path.exists():
        path.unlink(missing_ok=True)
    if df.empty and not allow_empty:
        raise RuntimeError(f"No data returned for {symbol}")
    return df


def load_vix3m_with_fallback(app_config: AppConfig, start: datetime, end: datetime) -> pd.DataFrame:
    contract = _vix_contract("VIX3M")
    try:
        df = load_or_fetch("^VIX3M", contract, app_config, start, end, allow_empty=True)
    except Exception:
        df = pd.DataFrame()
    if not df.empty:
        return df

    daily = yf.download(
        "^VIX3M",
        start=start.date(),
        end=(end + timedelta(days=1)).date(),
        progress=False,
        auto_adjust=False,
    )
    if daily.empty:
        raise RuntimeError("Unable to obtain VIX3M data from either IBKR or Yahoo")
    daily = daily.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    if "adj_close" not in daily.columns:
        daily["adj_close"] = daily["close"]
    if "volume" not in daily.columns:
        daily["volume"] = 0
    idx = pd.to_datetime(daily.index).tz_localize("America/New_York") + pd.Timedelta(hours=16)
    daily.index = idx
    return daily
