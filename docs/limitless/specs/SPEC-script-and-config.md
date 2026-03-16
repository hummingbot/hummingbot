# SPEC: Top-Level Script + Controller Config YAML

Two small boilerplate pieces needed to run the controller.

---

## 1. Top-Level Script

**File:** `scripts/binary_options_strategy.py`

Extends `StrategyV2Base` (same pattern as `v2_with_controllers.py`).
This is what Hummingbot runs — it loads the controller, connects to exchange, manages lifecycle.

```python
import os
from decimal import Decimal
from typing import Dict, Optional

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.models.executor_actions import StopExecutorAction


class BinaryOptionsStrategyConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)

    # --- Drawdown protection ---
    max_global_drawdown_quote: Optional[float] = None       # USDC, stop everything if hit
    max_controller_drawdown_quote: Optional[float] = None   # USDC, stop single controller

    # --- Controller configs ---
    controllers_config: list[str] = []    # list of controller YAML filenames
    # e.g. ["binary_options.yml"]


class BinaryOptionsStrategy(StrategyV2Base):
    """
    Binary options strategy runner.

    Loads BinaryOptionsController(s) from YAML configs.
    Manages global drawdown, performance reporting, kill switches.

    Usage in Hummingbot:
        start --script binary_options_strategy.py --conf binary_options_strategy.yml
    """

    def __init__(self, connectors: Dict[str, ConnectorBase], config: BinaryOptionsStrategyConfig):
        super().__init__(connectors, config)
        self.config = config

    def on_tick(self):
        super().on_tick()
        if not self._is_stop_triggered:
            self.check_manual_kill_switch()
            if self.config.max_controller_drawdown_quote:
                self._check_max_controller_drawdown()
            if self.config.max_global_drawdown_quote:
                self._check_max_global_drawdown()

    def _check_max_controller_drawdown(self):
        """Stop individual controller if drawdown exceeds limit."""
        for controller_id, controller in self.controllers.items():
            report = self.get_performance_report(controller_id)
            if report.global_pnl_quote < -Decimal(str(self.config.max_controller_drawdown_quote)):
                self.logger().warning(
                    f"Controller {controller_id} hit max drawdown "
                    f"({report.global_pnl_quote}). Stopping."
                )
                controller.stop()
                # Stop unfilled executors
                active = self.filter_executors(
                    executors=self.get_executors_by_controller(controller_id),
                    filter_func=lambda x: x.is_active and not x.is_trading,
                )
                self.executor_orchestrator.execute_actions(
                    [StopExecutorAction(controller_id=controller_id, executor_id=e.id)
                     for e in active]
                )

    def _check_max_global_drawdown(self):
        """Stop everything if global drawdown exceeds limit."""
        total_pnl = sum(
            self.get_performance_report(cid).global_pnl_quote
            for cid in self.controllers
        )
        if total_pnl < -Decimal(str(self.config.max_global_drawdown_quote)):
            self.logger().warning(f"Global drawdown hit ({total_pnl}). Stopping all.")
            for controller in self.controllers.values():
                controller.stop()

    def format_status(self) -> str:
        """Dashboard display — delegates to controllers."""
        lines = ["Binary Options Strategy\n"]
        for controller_id, controller in self.controllers.items():
            report = self.get_performance_report(controller_id)
            lines.append(f"  Controller: {controller_id}")
            lines.append(f"  PnL: {report.global_pnl_quote:.4f} USDC")
            lines.append(f"  Volume: {report.volume_traded:.2f}")
            lines.extend(controller.to_format_status())
            lines.append("")
        return "\n".join(lines)
```

### Script Config YAML

**File:** `conf/scripts/binary_options_strategy.yml`

```yaml
max_global_drawdown_quote: 50.0
max_controller_drawdown_quote: 25.0
controllers_config:
  - binary_options.yml
```

---

## 2. Controller Config YAML

**File:** `conf/controllers/binary_options.yml`

This is what `BacktestingEngineBase.load_controller_config()` reads.
Also loaded by `StrategyV2Base` when starting controllers.

```yaml
# === Controller identity ===
controller_type: generic
controller_name: binary_options
id: binary_options_main

# === Connection ===
connector_name: limitless
trading_pair: BINARY-USD    # placeholder — controller manages multiple pairs internally

# === Budget ===
total_amount_quote: 100.0   # total USDC budget

# === Runtime config paths ===
runtime_json_path: /home/tiger/.openclaw/workspace/skills/limitless-recon/data/runtime.json
config_json_path: /home/tiger/.openclaw/workspace/skills/limitless-recon/config.json

# === Signal engine ===
poll_interval_ms: 1500
vol_warmup_ticks: 20

# === Action routing (decision tree toggles) ===
routing:
  # Entry method
  entry_mode: limit                # limit | market | auto
  taker_edge_threshold: 0.15      # edge above this → market order (if auto)
  taker_time_threshold_min: 5.0   # minutes to expiry → allow taker

  # Mint paths (Phase 2)
  mint_enabled: false
  mint_min_spread: 0.03
  mint_prefer_over_buy: false

  # Delta neutral (Phase 2)
  delta_neutral_enabled: false
  delta_neutral_max_edge: 0.03
  delta_neutral_min_spread: 0.02

  # Signal agreement
  require_signal_agreement: false
  conflict_mode: veto             # veto | reduce | ignore
  conflict_size_mult: 0.5

  # Exit routing
  exit_mode: limit                # limit | market | auto
  exit_taker_urgency_min: 2.0
  hold_to_settlement: true
  settlement_hold_threshold: 0.70

  # Position management
  max_positions_per_coin: 1
  max_total_positions: 5
  position_size_mode: fixed       # fixed | edge_scaled | kelly
  fixed_position_size: 5.0
  max_position_size: 20.0
  edge_size_multiplier: 100.0
```

### How it loads

1. `StrategyV2Base.__init__()` reads `controllers_config` list from script config
2. For each YAML: `BacktestingEngineBase.get_controller_config_instance_from_yml(path)`
3. Finds `controller_type=generic`, `controller_name=binary_options`
4. Imports `controllers.generic.binary_options` module
5. Finds `BinaryOptionsControllerConfig` class (extends `ControllerConfigBase`)
6. Instantiates with YAML values → creates `BinaryOptionsController`

### Module discovery path

Controller module must be at:
```
controllers/generic/binary_options/__init__.py
```

And `__init__.py` or the module itself must export the config class that extends `ControllerConfigBase`.
The engine scans for subclasses of `ControllerConfigBase` in the module.

---

## 3. Connector Registration

The Limitless connector must be registered in Hummingbot's connector framework.
This is already done (connector files exist at `hummingbot/connector/exchange/limitless/`).

For the controller to create executors that trade on Limitless:
```yaml
connector_name: limitless
```
Must match the connector's registered name in `hummingbot/client/settings.py` or equivalent.

---

## 4. Startup Flow

```
User runs: start --script binary_options_strategy.py

1. Hummingbot loads BinaryOptionsStrategyConfig from script YAML
2. Connects to Limitless exchange (connector)
3. Loads controller YAMLs → BinaryOptionsControllerConfig
4. Creates BinaryOptionsController instances
5. Creates ExecutorOrchestrator
6. Starts control loop:
   └─ on_tick() every 1s:
       ├─ controller.update_processed_data() — signals, markets
       ├─ controller.determine_executor_actions() — entries, exits
       ├─ orchestrator.execute_actions() — spawn/stop executors
       ├─ executors run their own control_task() loops (0.5s)
       └─ strategy checks drawdown, kill switches
```

---

## 5. Implementation Notes

- The script is mostly boilerplate — `v2_with_controllers.py` already works for 90% of cases.
  Our version adds: specific drawdown thresholds, clean format_status for binary options.
- The YAML config is the main customization point. All routing params live here.
- Per-coin signal params (z-threshold, cooldown, etc.) live in `runtime.json`, NOT the YAML.
  The YAML has the paths to runtime.json so the controller can find it.
- Multiple controller instances possible (e.g., one for hourly markets, one for daily).
