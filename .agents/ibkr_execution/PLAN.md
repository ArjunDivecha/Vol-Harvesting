# ExecPlan — IBKR Trade Execution

## 1. Goal
Extend the Vol Edge stack with a paper/live trading mode that places Market-On-Close (MOC) orders via IBKR, aligned with the 15:45 signal pipeline. Provide a reusable execution module, richer logging/audit trail, and CLI entry points (`vol-edge paper`, `vol-edge live`).

## 2. Scope
- IBKR order manager built atop `ib-insync` handling:
  - Connection lifecycle (reuse existing `IBKRClient`).
  - Contract mapping for UVXY, SVXY, and any configured instruments.
  - Position/portfolio sync and PnL polling.
  - Submission of MOC orders with fallback to limit-on-close (per spec).
- Scheduler that triggers signal evaluation and order placement at the proper cutoff (e.g., 15:45 ET signal, MOC deadline 15:50/16:00, early-closes 12:45/13:00).
- Risk controls: max exposure cap enforcement, ability to flatten all positions, pause trading on errors.
- CLI commands `vol-edge paper --config ...` and `vol-edge live --config ...` that run a single trading day loop (initial version) with clear stdout + audit logs.

## 3. Out of Scope
- Continuous daemonization or cloud deployment (document manual cron/systemd guidance instead).
- Broker account management (margin settings, borrow availability). We assume the user configures IBKR manually.
- Advanced execution algos (VWAP slices, multi-venue). We'll stick to MOC + limit-on-close fallback.

## 4. Work Plan
1. **Config Expansion**
   - Add `execution` section (order deadline offsets, fallback limit buffer, paper vs. live account identifiers).
   - Tests confirming parsing and defaults.
2. **Contract + Portfolio Sync**
   - Utilities to map configured instruments to IBKR contracts (ticker, exchange, multiplier) and fetch current positions.
   - Tests with mocked `ib_insync` responses ensuring we translate holdings into our `PortfolioState` format.
3. **Order Builder**
   - Translate desired weight deltas into share orders, choose order type (MOC vs. LOC fallback), and submit via IBKR with error handling/retries.
   - Tests mocking IBKR order placement and verifying fallback logic.
4. **Execution Loop**
   - Combine signal snapshots (already implemented) with live quotes if needed, compare to current holdings, and place orders before the cutoff time. Include logging and persisted audit file.
   - Tests using dependency injection/mocks to confirm the loop submits expected orders given synthetic signals/positions.
5. **CLI Integration & Docs**
   - Implement `vol-edge paper/live` commands.
   - Update README with instructions for running paper/live modes, required IBKR settings, and known limitations.

## 5. Risks & Mitigation
- **Timing windows**: ensure we enforce a buffer (e.g., submit orders no later than 15:50 ET). Provide config knobs and validate local clock vs. IBKR server time.
- **Order rejections**: implement fallback limit-on-close with last-trade-based price; if both fail, log and optionally flatten next session.
- **State drift**: reconcile positions at start of day and after fills; log differences vs. expected weights.

## 6. Next Step
Begin Milestone 1 by adding the execution config schema + tests.
