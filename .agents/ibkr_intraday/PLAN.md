# ExecPlan — IBKR Intraday Data Integration

## 1. Context & Goal
We need to add a 15:45 ET signal path backed by IBKR minute data (SPY, ^VIX, ^VIX3M) so backtests and, eventually, live trading match the paper’s timing. User will provide an IBKR TWS/Gateway session; we must build an `ib-insync` client, download historical 1-minute bars, cache them locally (parquet), and teach the backtest to consume these snapshots instead of daily closes when available.

## 2. Scope
- Add `ibkr` provider to `vol_edge.data` alongside existing yfinance/csv adapters.
- Implement minute-bar downloader using `ib_insync` (`IB.reqHistoricalData`), handling pagination/ratelimits.
- Normalize data to include a 15:45 ET sample per session (fall back to latest pre-15:45 print when missing).
- Extend backtest engine to accept intraday-derived snapshots (SPY close, VIX, VIX3M) while still supporting daily mode as fallback.
- Optionally persist pulls into `.data/ibkr_cache/*.parquet` for repeatability.

## 3. Out of Scope (for this plan)
- Replacing Yahoo daily mode entirely; it remains a fallback.
- Live order execution (MOC placement) — still future work.
- Non-minute resolutions or other assets.

## 4. Milestones
1. **IBKR Connectivity Layer**
   - Config updates for host/port/client ID, symbol mapping.
   - Thin wrapper around `ib_insync.IB` for context-managed connections.
   - TDD: mock `IB` to ensure we handle retries/timeouts.
2. **Historical Minute Downloader**
   - Function to fetch SPY/VIX/VIX3M minute bars between start/end, chunking per IBKR limits, returning DataFrames.
   - Cache to parquet with metadata (last update). CLI helper to refresh.
   - Tests: monkeypatch IB client to emit synthetic bars; ensure stitching/ordering correct.
3. **Signal Extraction @15:45**
   - Utility that takes minute bars + calendar and returns per-day snapshots (SPY price, VIX, VIX3M) at 15:45 ET (or latest prior, or 12:45 on early closes).
   - Tests: synthetic minute series covering full/half days, missing bars.
4. **Backtest Integration**
   - Option in config to select `ibkr_intraday` provider; data loader supplies both minute snapshots and daily OHLC for ETNs (Yahoo/CSV still used for UVXY/SVXY unless IB data provided).
   - Backtest picks intraday signals when available; falls back to daily logic otherwise.
   - Tests: small fixture verifying the 15:45 snapshots change target weights vs. daily fallback.
5. **Docs & CLI Hook**
   - README updates on IBKR requirements, caching, and new CLI flags for refreshing cache.
   - Possibly `vol-edge data --provider ibkr --refresh` command.

## 5. Risks & Mitigation
- **IBKR rate limits / disconnects**: implement exponential backoff, chunk requests by 1 week for minute bars.
- **Timezones/Holidays**: use `pandas_market_calendars` or manual schedule to know when 15:45 exists; handle early-closes (12:45/13:00) per PRD.
- **Data gaps**: log warnings and fall back to daily snapshot if IBKR missing; surface in audit trail.

## 6. Next Steps
- Confirm `ib_insync` availability and IBKR credentials (host/port/client_id) from config.
- Begin with Milestone 1 tests for the connectivity wrapper.
