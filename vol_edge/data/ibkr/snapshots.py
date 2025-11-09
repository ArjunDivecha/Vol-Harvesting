"""Build 15:45 ET signal snapshots from cached minute data."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from vol_edge.config import AppConfig

from .downloader import (
    load_or_fetch,
    load_vix3m_with_fallback,
    cache_path,
    _contract,
    _vix_contract,
)

NY_TZ = ZoneInfo("America/New_York")
SNAPSHOT_TIME = time(15, 45)


def _target_timestamp(trading_day: date, snapshot_time: time = SNAPSHOT_TIME) -> datetime:
    return datetime.combine(trading_day, snapshot_time, tzinfo=NY_TZ)


def _sample_at(df: pd.DataFrame, timestamp: datetime) -> pd.Series | None:
    if df.empty:
        return None
    if timestamp in df.index:
        row = df.loc[timestamp]
        return row if isinstance(row, pd.Series) else row.iloc[0]
    subset = df.loc[:timestamp]
    if subset.empty:
        return None
    if isinstance(subset, pd.Series):
        return subset.iloc[-1]
    return subset.iloc[-1]


def _close_value(row: pd.Series | float) -> float:
    if isinstance(row, pd.Series):
        value = row.get("close", row.iloc[-1])
        if isinstance(value, pd.Series):
            value = value.iloc[0]
        return float(value)
    return float(row)


def _prepare_minutes(symbol: str, contract_builder, config: AppConfig, start: datetime, end: datetime) -> pd.DataFrame:
    contract = contract_builder(symbol)
    df = load_or_fetch(symbol, contract, config, start, end)
    if "adj_close" in df.columns:
        df["close"] = df.get("close", df["adj_close"])
    if not df.index.tz:
        df.index = pd.to_datetime(df.index).tz_localize(NY_TZ)
    else:
        df.index = pd.to_datetime(df.index).tz_convert(NY_TZ)
    return df


def build_signal_snapshots(
    config: AppConfig,
    start: date,
    end: date,
    snapshot_time: time = SNAPSHOT_TIME,
) -> pd.DataFrame:
    padding_days = 30
    start_dt = datetime.combine(start - timedelta(days=padding_days), time(0), tzinfo=NY_TZ).astimezone(timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), time(0), tzinfo=NY_TZ).astimezone(timezone.utc)

    spy_minutes = _prepare_minutes("SPY", _contract, config, start_dt, end_dt)
    vix_minutes = _prepare_minutes("^VIX", _vix_contract, config, start_dt, end_dt)
    vix3m_df = load_vix3m_with_fallback(config, start_dt, end_dt)
    if not vix3m_df.index.tz:
        vix3m_df.index = pd.to_datetime(vix3m_df.index).tz_localize(NY_TZ)
    else:
        vix3m_df.index = pd.to_datetime(vix3m_df.index).tz_convert(NY_TZ)

    trading_days = sorted(set(spy_minutes.index.date))
    records: list[dict] = []

    for day in trading_days:
        if day < start or day > end:
            continue
        target_ts = _target_timestamp(day, snapshot_time)
        spy_row = _sample_at(spy_minutes, target_ts)
        if spy_row is None:
            continue
        vix_row = _sample_at(vix_minutes, target_ts)
        vix3m_row = _sample_at(vix3m_df, target_ts)
        if vix_row is None or vix3m_row is None:
            continue
        records.append(
            {
                "date": pd.Timestamp(day),
                "spy": _close_value(spy_row),
                "vix": _close_value(vix_row),
                "vix3m": _close_value(vix3m_row),
            }
        )

    if not records:
        return pd.DataFrame(columns=["spy", "vix", "vix3m"]).set_index(pd.Index([], name="date"))

    df = pd.DataFrame(records).set_index("date").sort_index()
    return df
