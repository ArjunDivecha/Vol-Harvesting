# Volatility Edge (VIX ETN) Strategy – Implementation Guide

This README distills the requirements from `PRD.txt` and the white paper *“The Volatility Edge — A Dual Approach For VIX ETNs Trading”* (esp. Table&nbsp;2, p.22; Sections&nbsp;3–6, pp.15–31) into a build/run guide for the production Python stack (3.11+) that backtests, evaluates, and trades the four rule sets (`Passive`, `eVRP`, `eVRP + BoC`, `eVRP + BoC + Sizing`). It is the canonical hand‑off for building the codebase before we begin TDD work.

---

## 1. Scope & Objectives

- **Parity with paper signals** – replicate the decision tables in Table&nbsp;2 (p.22) including ±2 % rebalance bands with a base-case assumption of zero explicit trading costs (5 bps remains a configurable override to match the paper when needed).
- **Signal timing (spec deviation)** – compute eRV30 from the latest 10 daily close-to-close SPY returns and form the entire signal snapshot (SPY, VIX, VIX3M) using the prior day’s close. Target weights derived at *t‑1* are implemented via Market‑On‑Close at *t*, creating a documented one-session lag relative to the paper’s 15:45 ET signal.
- **Execution realism** – under the daily-data regime, assume fills occur at the official close (or adjusted close) and treat limit-on-close fallbacks as no-ops because only closing prices are modeled. Early-close nuances are noted but not simulated until intraday data returns.
- **Transparency** – produce Table‑3‑style metrics, Figure‑4/5 plots, blending analysis, daily audit logs, and reproducible configs, with clear callouts where the daily-only approximation diverges from the original spec.
- **Primary data** – start with Yahoo Finance (`yfinance`) daily OHLCV for SPY, VIX (`^VIX`), VIX3M (`^VIX3M`), UVXY, and SVIX; keep the data layer pluggable so the eventual live-trading stack (with intraday inputs) can be implemented separately without refactoring the backtest.
- **Default instruments** – adopt the most active VIX ETNs (UVXY for long exposure, SVIX for short exposure) per Yahoo Finance volumes observed on 2025‑11‑08 09:56 PT.
- **Backtest vs. live split** – the historical backtest will always operate on daily closes; intraday data is reserved for future live/paper trading modules and treated as a separate concern.

Out of scope per PRD: VIX futures, swaps, or replicating proprietary ETN proxies—only ETF/ETN wrappers with configurable multipliers (e.g., SVIX, UVXY, VIXY).

---

## 2. Phased Implementation Plan

1. **Environment & Tooling**
   - Python 3.11+, `uv`/`poetry` (lockfile), `pytest` + `hypothesis`, `pandas`, `pyarrow`, `numpy`, `matplotlib`, `ib-insync`, `pydantic`.
   - Bootstrap repo with linting (`ruff`/`black` optional) and pre-commit if desired.
   - Target runtime is a single Apple Silicon (M4 Max) macOS host; document any architecture-specific steps (e.g., IBKR gateway install paths).
2. **Data Layer (`vol_edge/data/`)**
   - Contracts in `base.py` for schema/units (dates in ET, adjusted vs raw closes).
   - `yfinance_source.py` (daily OHLCV pulls for SPY, VIX, VIX3M, UVXY, SVIX) as the initial implementation; keep CSV/Parquet ingestion for offline fixtures and leave hooks for future IBKR/intraday adapters.
   - Rolling-window helpers to ensure the prior-close snapshot is available before emitting signals (enforce 10-day warm-up).
3. **Signal Engines (`vol_edge/signals/`)**
   - `realized_vol.py`: eRV30 per eq.(5), annualized, with calendar adjustments and early‑close shifts.
   - `term_structure.py`: VIX vs. VIX3M comparison with optional epsilon deadband (default 0, per PRD §15).
4. **Strategy Layer (`vol_edge/strategies/`)**
   - Base interface + four concrete implementations mirroring Table 2.
   - Configurable safety caps (`max_vol_exposure_pct`) and instrument multipliers for inverse/leveraged ETNs.
5. **Portfolio & Execution (`vol_edge/portfolio/`, `vol_edge/exec/`)**
   - Position tracking, notional→shares sizing, ±2 % rebalance logic, zero-cost default (configurable), and a close-to-close fill model (MOC assumed to fill at that day’s close).
   - Execution module focuses on backtests only for now; IBKR live/paper wrappers remain TODO until we reinstate intraday feeds.
   - Basic calendar utilities for trading-day iteration; early-close shifts are noted but not simulated until we have intraday data.
6. **Reporting & CLI (`vol_edge/reports/`, `cli.py`)**
   - Metrics per Table 3 (CAGR, vol, Sharpe, Sortino, MDD, adj. MDD per rolling 20-day median definition on p.24).
   - Blending sweep (Figure 5) using the 0 → 100 % SPY weights in 5 % increments, equity/drawdown plots (Figure 4), CSV exports of monthly/annual returns (Appendix B).
   - CLI: `vol-edge backtest|blend|paper|live|report`.
7. **Examples & Docs**
   - `examples/backtest_evrp_boc_sizing.yml` config template.
   - `examples/Walkthrough.ipynb` to load data, run one strategy, plot, and export reports.

Each phase should follow TDD: author failing unit/property tests before implementation, request approval, and iterate until green. Larger milestones (e.g., completing phases 2–5) should start with an ExecPlan stored under `.agents/<feature>/PLAN.md` per team workflow.

---

## 3. Strategy Rules (Table 2 Reference)

| Strategy | When to Hold | Instrument | Size | Notes |
| --- | --- | --- | --- | --- |
| Passive | Always | `VIXSHORT` | +20 % | Rebalance if drift > ±2 %. |
| eVRP | `eVRP = VIX − eRV30 > 0` | `VIXSHORT` | +20 % | Else go cash. |
| eVRP + BoC | `eVRP > 0 ∧ VIX < VIX3M` | `VIXSHORT` | +20 % | Contango bias short. |
|  | `eVRP ≤ 0 ∧ VIX < VIX3M` | `VIXSHORT` | +10 % | Mild short when premium negative but structure favorable. |
|  | `eVRP ≤ 0 ∧ VIX > VIX3M` | `VIXLONG` | +20 % | Go long when backwardation + negative VRP. |
| eVRP + BoC + Sizing | `eVRP > 0 ∧ VIX < VIX3M` | `VIXSHORT` | `VIX%` | Dynamic sizing (VIX/100 of NAV; cap configurable). |
|  | `eVRP < 0 ∧ VIX < VIX3M` | `VIXSHORT` | `0.5 × VIX%` | Reduce risk in low-VIX fragility regimes. |
|  | `eVRP < 0 ∧ VIX > VIX3M` | `VIXLONG` | `VIX%` | Offense in backwardation. |

Signal order: compute eRV30 first (needs SPY data), fetch VIX/VIX3M snapshots at the signal timestamp, derive term-structure state, then evaluate the rule tree. All strategies honor ±2 % rebalance bands and assume zero explicit execution cost unless a config override is supplied.

---

## 4. Instrument Defaults & Market Data

*Spec deviation notice:* Until we have intraday feeds, every signal uses the **prior trading day’s close**, so decisions react one full session later than Table 2 assumes. All reports must highlight this lag so stakeholders don’t overfit to Table 3.

- **Default ETFs/ETNs** – A quick Yahoo Finance (`yfinance`) pull on 2025‑11‑08 09:56 PT showed `UVXY` trading ~53 M shares that day (10‑day avg ~37.5 M) vs. `UVIX` at ~47 M (avg ~31 M), while inverse products `SVIX` and `SVXY` printed ~9 M (avg ~3.9 M) and ~3.3 M (avg ~2.0 M) respectively. We therefore fix `UVXY` as `VIXLONG` and `SVIX` as `VIXSHORT` in configs, with multipliers reflecting their leverage ( +1.5× for UVXY, −1× for SVIX) and leave the others as alternates/fallbacks.
- **Backtest horizon** – Run historical tests across the full Jan‑2008 → latest‑available window to remain consistent with the paper while capturing post‑2025 behavior once data is available.
- **SPY daily closes** provide both the last 10 returns for eRV30 and the prior-close snapshot for signal formation; no intraday sampling is attempted in this first phase, and we rely on Yahoo’s adjusted close to incorporate splits/distributions.
- **VIX & VIX3M closes** (from `^VIX` / `^VIX3M`) are aligned to the same prior-close timestamp. Document that this introduces a ~15-minute timing difference vs. the paper’s 15:45 ET observation.
- **Trading calendars** for NYSE + CBOE to align holidays/half days and to prevent signals on closed sessions.
- **Instrument metadata** – YAML config with tickers, multipliers (e.g., `-1` for SVIX, `+1` for UVXY’s effective leverage), borrow availability flags, and fallback tickers.
- **Test fixtures** – Prefer sanitized IBKR exports for deterministic unit/integration tests once you share them; until then we will fabricate synthetic datasets clearly labeled as such.
- **Calendars** – Yahoo Finance trading days are sufficient; no separate NYSE/CBOE calendar will be wired in for the backtest unless data anomalies appear.

---

## 5. Configuration & CLI Contracts

`vol_edge.config` (Pydantic) should deserialize YAML structures similar to the snippet in §8 of `PRD.txt`, including:

- `data.csv_paths` & `data.ibkr` credentials.
- `instruments.vix_short` / `vix_long` definitions with multipliers and fee assumptions.
- `signals.signal_time_et`, `term_structure_epsilon`, `max_vol_exposure_pct`, `rebalance_threshold_pct`, `trade_cost_bps` (default 0; set to 5 to match the paper).
- `risk` toggles (NAV dislocation checks, min trade value, etc.).
- `logging` level and audit sink.

CLI usage (per PRD §14):

```bash
vol-edge backtest --config configs/base.yml
vol-edge blend --config configs/base.yml --weights 0:100:5
vol-edge paper --config configs/ibkr-paper.yml
vol-edge live --config configs/ibkr-live.yml
vol-edge report --run-id 2024-09-15_evpr
```

Each command should emit a run identifier to tie together logs, metrics, and audit files.

---

## 6. Testing & Validation

- **Unit tests** for eRV30 math, signal decision tables (mirror Table 2 cases), rebalance thresholding, fee application, adjusted MDD calculation.
- **Property tests** (Hypothesis) confirming no look-ahead: signals must only use data ≤ signal timestamp; randomized calendars/early closes.
- **Backtest determinism** – identical seeds/data ⇒ identical outcomes.
- **Acceptance checks** – on sample datasets, ensure Sharpe/CAGR ordering matches Table 3 ranges (p.25) and document tolerated deviations.

Follow the prescribed workflow: write tests first, get approval, then implement.

---

## 7. Observability & Risk Controls

- **Daily audit trail** (parquet/jsonl) containing timestamp, all signal inputs, regime, target vs. actual weights, submitted orders, fills, PnL, and risk flags.
- **Logging** – INFO default, DEBUG via CLI flag; highlight warnings when instruments halt or when NAV dislocation checks trip (Appendix B).
- **Risk knobs** – `max_vol_exposure_pct` default 0.40, `min_trade_value_usd` 1 000, optional NAV dislocation guard, configurable epsilon for VIX/VIX3M ties, manual override to force cash.
- **Disclaimers** – README and CLI banner must state that VIX ETPs carry termination risk (Sec. 2 & §13) and reference events like Feb‑5‑2018 (XIV) and Mar‑2022 VXX creations halt.

---

## 8. Deliverables Checklist

- [ ] Python package `vol_edge/` with modules outlined in §9 of `PRD.txt`.
- [ ] Config schemas, example configs, and CLI entrypoints.
- [ ] Tests (unit + property) with ≥85 % coverage.
- [ ] Reports & plots (Table 3 / Figure 4–5 analogs).
- [ ] Dockerfile or `uv.lock`/`poetry.lock`.
- [ ] Notebook walkthrough and sample data fixtures.

---

## 9. Decisions Locked In

- Use Yahoo Finance adjusted closes for SPY, UVXY, SVIX (raw closes optional but not required now).
- Daily backtest is permanent; intraday data will come later solely for live/paper trading flows.
- Yahoo’s trading calendar is sufficient for determining valid sessions.

---

*Last updated:* Generated by Codex after reviewing `PRD.txt` and the referenced white paper. Please answer the open questions so we can proceed without guesswork.
