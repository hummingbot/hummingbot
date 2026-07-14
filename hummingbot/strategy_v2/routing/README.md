# Strategy Routing V2

This package is the paper-first end-to-end control plane for multi-account strategy routing.

Implemented:

- strict paper-first account configuration validation;
- account/subaccount graph and worker isolation checks;
- deterministic scoring with bounded optional AI adjustments;
- compatibility-aware account allocation;
- global allocation, reserve, exposure, and drawdown gates;
- Evolution per-strategy paper Release Manifest adaptation and authorization;
- fail-closed single-writer preflight against Evolution auto-start;
- safe transition state machine;
- deterministic RoutePlan generation and idempotent JSONL ledger.
- Evolution controller-to-candidate feature adapter;
- DeepSeek JSON adapter with timeout, bounded output, and persistent circuit breaker;
- paper worker start/stop planning, command allowlisting, state persistence, and runtime reconciliation;
- Hummingbot runtime snapshot ingestion;
- manual, idempotent paper transfer simulation;
- one-shot and watch-mode routing service.

Hard-disabled here:

- live account trading or live worker activation;
- exchange internal-transfer APIs;
- automatic transfers;
- AI-generated orders, leverage, strategy configs, or risk overrides.

Validate the tracked paper example:

```bash
python3 scripts/validate_strategy_routing_config.py
```

Run the real Evolution release through a deterministic paper-plan smoke:

```bash
python3 scripts/run_strategy_router.py \
  --market reports/examples/strategy_router_market.smoke.json \
  --accounts reports/examples/strategy_router_accounts.smoke.json \
  --now 1783887600
```

Add `--apply-paper-workers` only when Docker and `CONFIG_PASSWORD` are available.
The worker adapter revalidates the candidate/hash, script path, controller path,
and `_paper_trade` connector before executing an allowlisted `run_*_paper.sh`.

For an already-running legacy paper container, adopt it without restarting:

```bash
python3 scripts/adopt_strategy_router_worker.py \
  --account binance-mm \
  --runtime data/pmm_mister_paper_runtime.json \
  --approved-by <operator>
```

Then use `--market-runtime` and `--runtime-map` to consume Hummingbot's live
read-only snapshot. Routing requires three distinct decision IDs before drain.
If restart credentials are absent, drain is rejected before Docker stop.

Run the isolated unit tests:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q test/hummingbot/strategy_v2/routing
```
