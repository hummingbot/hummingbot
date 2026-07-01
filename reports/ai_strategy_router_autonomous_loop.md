# AI Strategy Router Autonomous Loop

## Goal

Build a closed iteration loop for the AI strategy router:

```text
observe -> test -> evaluate -> repair plan -> deploy paper -> verify -> repeat
```

The loop is intentionally paper-first. Live trading promotion must remain gated by tests, risk limits, and an explicit release process.

## Current Implementation

Implemented:

```text
scripts/ai_router_monitor.py
scripts/ai_router_iteration_loop.py
reports/ai_strategy_router_iteration_latest.md
reports/ai_strategy_router_iteration_latest.json
reports/ai_strategy_router_live_status.md
```

Current loop command:

```bash
python3 scripts/ai_router_iteration_loop.py
```

Run continuously:

```bash
python3 scripts/ai_router_iteration_loop.py --watch 300 --max-iterations 999
```

Run tests, then restart the paper bot if tests pass:

```bash
python3 scripts/ai_router_iteration_loop.py --deploy-paper
```

## What The Loop Does Now

1. Observes the current paper bot:
   - Docker container status.
   - Latest router decision.
   - Latest protect event.
   - Order and fill counts.
   - Open/completed/cancelled order status distribution.
   - Estimated inventory, fees, and mark-to-market equity.

2. Tests code:
   - Python compile checks for router/controller/executor/loop files.
   - Synthetic router regime tests.
   - Strategy registry integrity checks.

3. Evaluates gaps:
   - Paper bot not running.
   - No orders/fills.
   - Paper loss below threshold.
   - Elevated open order count.
   - Router currently in protect mode.
   - Route/config mismatch, such as `trend_short` while `allow_short=false`.
   - Shadow strategy adapter backlog.
   - Uncommitted/unpinned release changes.

4. Optionally deploys:
   - Restarts `hummingbot-ai-router-paper`.
   - Mounts local controller/router/executor files into the Hummingbot Docker image.
   - Keeps deployment paper-only.

5. Writes reports:
   - Markdown report for humans.
   - JSON report for future automation.

## What Is Still Missing

### 1. Code Auto-Iteration

Current status: partial.

The loop can detect failures and write repair tasks, but it does not yet rewrite code by itself.

Needed:

- A patch-generation agent that reads the JSON report and proposes a minimal code patch.
- A mutation budget: one small change per loop.
- Mandatory tests after every patch.
- Automatic rollback if deploy verification fails.
- A release ledger recording patch, test result, deploy ID, and paper outcome.

Suggested rule:

```text
The loop may auto-change code only inside an allowlist:
routers/, controllers/generic/ai_strategy_router.py, scripts/ai_router_*.py
```

Everything else requires human review.

### 2. All Strategy Auto-Iteration

Current status: strategy universe registered, not fully executable.

Registered candidates:

- 26 total candidates.
- 5 enabled direct routes.
- 21 shadow candidates.

Needed for each shadow strategy:

- Adapter: map route decision into that strategy's config/executor actions.
- Feature requirements: what market data and account data it needs.
- Risk limits: max position, max loss, max stale orders, cooldown.
- Backtest/paper validation profile.
- Promotion criteria from shadow to enabled.

Promotion rule should look like:

```text
shadow -> paper-enabled -> small-live-canary -> full-live
```

No strategy should jump directly from registry to live routing.

### 3. Auto-Repair And Auto-Deploy

Current status: auto-deploy to paper exists.

Needed:

- Pre-deploy check:
  - tests pass;
  - current paper bot not in protect;
  - estimated loss above threshold;
  - open orders below threshold, or explicit restart policy.

- Post-deploy check:
  - container up;
  - candles ready;
  - router decision logged;
  - no traceback;
  - paper order or intentional no-trade reason within N minutes.

- Rollback:
  - restore last known good release snapshot;
  - redeploy paper;
  - write incident report.

### 4. Data And Scoring

Current status: metrics are log/SQLite based.

Needed:

- A feature store for candles, decisions, candidate scores, fills, and PnL.
- Per-regime scorecards:
  - grid in range;
  - trend in trend;
  - protect during spikes;
  - shadow strategy paper simulations.

- Objective function:

```text
score = net_pnl - fee_penalty - drawdown_penalty - churn_penalty - stale_order_penalty
```

### 5. Safety Boundaries

Must remain hard-coded:

- Paper first.
- No live auto-deploy without explicit approval.
- No shorting when `allow_short=false`.
- No leverage increase from the loop.
- No new connector/API key writes from the loop.
- No destructive git commands.
- Stop/protect always overrides strategy selection.

## Recommended Next Build Steps

1. Add post-deploy verification to `ai_router_iteration_loop.py`.
2. Add a strategy adapter checklist file for all 21 shadow candidates.
3. Add a backtest batch runner for enabled strategies.
4. Add a release ledger JSONL.
5. Add auto-rollback for failed paper deploy.
6. Only then add patch-generation automation.
