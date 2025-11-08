# Backtest ExecPlan (Daily-Data Approximation)

## 1. Context & Intent
- Build the backtesting portion of the Volatility Edge project using **daily close-only data** as an interim solution.
- Ensure parity with Table 2 decision logic while acknowledging the intentional one-session lag vs. the paper’s 15:45 ET signals.
- Follow TDD throughout; each module should land with failing tests first, then implementation.

## 2. Scope
- Data ingestion via `yfinance` (daily OHLCV for SPY, VIX, VIX3M, UVXY, SVIX) plus CSV fixture loader for tests.
- Signal computation: eRV30 from 10 prior close-to-close SPY returns, VIX term-structure state from prior-day closes.
- Strategy engines: Passive, eVRP, eVRP+BoC, eVRP+BoC+Sizing with configurable caps/thresholds.
- Portfolio + execution: holdings, rebalance logic, close-to-close fill model, zero explicit costs (configurable).
- Backtest runner + CLI entry point for `vol-edge backtest` operating on YAML config.
- Reporting: metrics akin to Table 3 (CAGR, vol, Sharpe, Sortino, MDD, adj MDD) and CSV/JSON summary output. Plotting deferred until data validation unless trivial.

## 3. Out of Scope (for this plan)
- Intraday/15:45 ET sampling and IBKR adapters.
- Live or paper trading flows, broker order management, limit-on-close lifecycle beyond documentation.
- Advanced execution models (VWAP, partial fills), NAV dislocation checks, alerting.
- Jupyter notebook/demo polish.

## 4. Milestones & TDD Tasks
1. **Config & Data Contracts**
   - Define Pydantic config models for data paths, instruments, strategy selection, and backtest params.
   - Tests: schema validation, default overrides, error handling for missing tickers.
2. **Data Access Layer**
   - Implement `yfinance_source.py` (and stub CSV loader) returning pandas DataFrames indexed by date.
   - Tests: mock yfinance responses, ensure adjusted vs. raw close handling, enforce 10-day warm-up availability.
3. **Signal Modules**
   - `realized_vol.py`: compute eRV30 (Eq. 5) using prior closes.
   - `term_structure.py`: compute eVRP, state (contango/backwardation), ensure tie handling.
   - Tests: parametrized cases verifying no look-ahead (signals use t-1 data), correctness vs. manual calculations.
4. **Strategy Layer**
   - Implement base interface + four strategies per Table 2, referencing signals only.
   - Tests: table-driven inputs/outputs covering every branch, rebalance threshold edges, caps.
5. **Portfolio & Execution**
   - Portfolio state (cash, positions, equity), sizing helpers (weights→shares) respecting multipliers.
   - Rebalance engine applying ±2% drift check, tracking fills at close_t (zero cost by default).
   - Tests: rebalance threshold scenarios, share rounding, exposure caps, PnL math across multiple days.
6. **Backtest Engine & CLI**
   - Event loop over trading days: load data, build signal snapshot from t-1, execute orders at t close, log audit trail.
   - CLI command `vol-edge backtest --config path.yml` hooking config → engine.
   - Tests: deterministic sample dataset verifying strategy rankings, CLI smoke test via `subprocess` or Click runner.
7. **Reporting**
   - Metrics module reproducing Table-3 stats, adjusted MDD, optional CSV export of equity curve.
   - Tests: feed synthetic equity series to validate metrics & adjusted MDD definition.

## 5. Risks & Mitigations
- **Spec divergence** (daily vs. 15:45): highlight in README + CLI banner; design data layer to swap in intraday sources later.
- **Yahoo data gaps**: add retry/backoff, allow cached CSV fixtures for deterministic tests; surface warnings when data missing.
- **Adjusted-price drift**: store both adjusted and unadjusted closes so we can reconcile distributions if needed.

## 6. Deliverables
- `vol_edge/` package with modules above, unit/property tests, CLI entry point, sample config, README updates noting daily-only mode.
- `.agents/backtest` artifacts (this plan, notes, eventual research snippets if needed).
- CI-ready `pytest` suite (even if run locally) with clear instructions.

## 7. Open Questions (tracking)
1. Adjusted vs. unadjusted close preference for SPY/UVXY/SVIX (affects data schema).
2. Should the daily backtest remain permanently once intraday parity is available, or is it purely a stopgap?
3. Do we trust Yahoo’s implicit holiday calendar, or should we integrate an explicit NYSE/CBOE calendar now?

*Next action after plan approval:* begin Milestone 1 by writing config-schema tests.
