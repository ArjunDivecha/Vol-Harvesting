# Volatility Edge (VIX ETN) Strategy – Implementation Guide

This README distills the requirements from `PRD.txt` and the white paper *“The Volatility Edge — A Dual Approach For VIX ETNs Trading”* (esp. Table&nbsp;2, p.22; Sections&nbsp;3–6, pp.15–31) into a build/run guide for the production Python stack (3.11+) that backtests, evaluates, and trades the four rule sets (`Passive`, `eVRP`, `eVRP + BoC`, `eVRP + BoC + Sizing`). It is the canonical hand‑off for building the codebase before we begin TDD work.

---

## 1. Scope & Objectives

- **Parity with paper signals** – replicate the decision tables in Table&nbsp;2 (p.22) including ±2 % rebalance bands and 5 bps per trade.
- **Signal timing** – compute eRV30 using 10 daily SPY returns with the latest price sampled at 15:45 ET (shift to 15:44–15:45 minute bar when only 1‑min data exist; Sec. 4.2 & Sec. 6, pp.18 & 27–28).
- **Execution realism** – ingest daily/minute data, simulate Market‑On‑Close (MOC) fills, handle early closes (13:00 ET execution; p.31), and expose the same flow to IBKR paper/live trading.
- **Transparency** – produce Table‑3‑style metrics, Figure‑4/5 plots, blending analysis, daily audit logs, and reproducible configs.

Out of scope per PRD: VIX futures, swaps, or replicating proprietary ETN proxies—only ETF/ETN wrappers with configurable multipliers (e.g., SVIX, UVXY, VIXY).

---

## 2. Phased Implementation Plan

1. **Environment & Tooling**
   - Python 3.11+, `uv`/`poetry` (lockfile), `pytest` + `hypothesis`, `pandas`, `pyarrow`, `numpy`, `matplotlib`, `ib-insync`, `pydantic`.
   - Bootstrap repo with linting (`ruff`/`black` optional) and pre-commit if desired.
2. **Data Layer (`vol_edge/data/`)**
   - Contracts in `base.py` for time‑zone‑aware frames.
   - CSV/Parquet loader (`csv_source.py`) plus IBKR adapter (`ibkr_source.py`) for historical + intraday pulls.
   - Ensure SPY minute data resolution supports 15:45 ET sampling; provide fallback logic for missing bars.
3. **Signal Engines (`vol_edge/signals/`)**
   - `realized_vol.py`: eRV30 per eq.(5), annualized, with calendar adjustments and early‑close shifts.
   - `term_structure.py`: VIX vs. VIX3M comparison with optional epsilon deadband (default 0, per PRD §15).
4. **Strategy Layer (`vol_edge/strategies/`)**
   - Base interface + four concrete implementations mirroring Table 2.
   - Configurable safety caps (`max_vol_exposure_pct`) and instrument multipliers for inverse/leveraged ETNs.
5. **Portfolio & Execution (`vol_edge/portfolio/`, `vol_edge/exec/`)**
   - Position tracking, notional→shares sizing, ±2 % rebalance logic, cost model (5 bps), and MOC simulator.
   - IBKR wrapper (`ib_broker.py`) that submits MOC, handles rejects, and escalates to fallback (limit-on-close or VWAP slice) when needed (Sec. 6, p.29).
   - Scheduling utilities for regular/early closes and holiday awareness.
6. **Reporting & CLI (`vol_edge/reports/`, `cli.py`)**
   - Metrics per Table 3 (CAGR, vol, Sharpe, Sortino, MDD, adj. MDD per rolling 20-day median definition on p.24).
   - Blending sweep (Figure 5), equity/drawdown plots (Figure 4), CSV exports of monthly/annual returns (Appendix B).
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

Signal order: compute eRV30 first (needs SPY data), fetch VIX/VIX3M snapshots at the signal timestamp, derive term-structure state, then evaluate the rule tree. All strategies honor ±2 % rebalance bands and 5 bps execution cost.

---

## 4. Data, Calendars, & Signal Timing

- **SPY daily closes** (for last 10 returns) and intraday prices to capture the 15:45 ET snapshot. If 15:45 is absent, use the last print prior to that time (Sec. 4.2, p.18). Early closes shift to 12:45 ET signal / 13:00 ET MOC (p.31).
- **VIX & VIX3M snapshots** from the same timestamp; allow adapters for CSV, Polygon, IBKR, etc., but normalize to a shared schema.
- **Trading calendars** for NYSE + CBOE to align holidays/half days and to prevent signals on closed sessions.
- **Instrument metadata** – YAML config with tickers, multipliers (e.g., `-1` for SVIX, `+1` for VIXY), borrow availability flags, and fallback tickers.

---

## 5. Configuration & CLI Contracts

`vol_edge.config` (Pydantic) should deserialize YAML structures similar to the snippet in §8 of `PRD.txt`, including:

- `data.csv_paths` & `data.ibkr` credentials.
- `instruments.vix_short` / `vix_long` definitions with multipliers and fee assumptions.
- `signals.signal_time_et`, `term_structure_epsilon`, `max_vol_exposure_pct`, `rebalance_threshold_pct`, `trade_cost_bps`.
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

## 9. Open Questions for You

To avoid assumptions, please clarify:

1. **Data sourcing** – Which concrete providers (Polygon, Tiingo, IBKR historical, CSV dumps) will we use for SPY minute data and VIX/VIX3M snapshots? Any licensing constraints?
2. **Historical window** – Should backtests start Jan‑2008 as in the paper, or do you want a different start/stop range?
3. **Instrument mapping** – Which ETNs/ETFs should we treat as `VIXSHORT` and `VIXLONG` in both backtests and live trading (e.g., `SVIX`/`UVIX`, `SVXY`/`VIXY`)? Are there brokerage availability constraints?
4. **Position caps** – Is the default `max_vol_exposure_pct = 40%` acceptable, or do you prefer a different ceiling per strategy?
5. **Execution venue** – Are we strictly using IBKR MOC orders, or do you need support for smart-routing/ISLAND close orders or alternative brokers?
6. **Fallback behavior** – When MOC is rejected or the instrument is halted, should we auto-switch to limit-on-close, next-day MOO, or simply flatten to cash?
7. **Cost model** – Do we always apply 5 bps round-trip per Table 2, or should costs be parameterized by instrument/liquidity tiers?
8. **Blending analysis** – Which SPY blend weights (beyond the 0→100 % in 5 % steps from Figure 5) matter most for your reporting?
9. **Deployment** – Will live trading run on a single machine (cron/systemd) or do we need container/orchestrator hooks (Docker, ECS, etc.)?
10. **Compliance logging** – Do you require additional artifacts (e.g., signed order blotters, broker confirms) for audit/regulatory workflows?
11. **Extensibility** – Should we reserve hooks for alternative realized-vol estimators (HAR, GARCH) now, or defer until baseline parity is achieved?
12. **User interface** – Beyond CLI/notebook, do you envision a lightweight dashboard or alerts channel (Slack/Email) for fills and risk events?

Once these points are resolved, we can draft the first ExecPlan and start the TDD implementation safely.

---

*Last updated:* Generated by Codex after reviewing `PRD.txt` and the referenced white paper. Please answer the open questions so we can proceed without guesswork.
