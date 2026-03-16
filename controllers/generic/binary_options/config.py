"""Configuration, runtime bridge, and coin roster for BinaryOptionsController."""
import json
import logging
import os
import time
from typing import Optional

from pydantic import BaseModel, Field

from hummingbot.strategy_v2.controllers.controller_base import ControllerConfigBase

from .fair_value import halflife_to_alpha

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Action routing config (nested Pydantic model)
# ---------------------------------------------------------------------------

class ActionRoutingConfig(BaseModel):
    """Decision-tree toggles for entry/exit/mint/position routing."""

    # Entry
    entry_mode: str = Field(default="limit", description="limit | market | auto")
    taker_edge_threshold: float = Field(default=0.15)
    taker_time_threshold_min: float = Field(default=5.0)

    # Mint (Phase 2)
    mint_enabled: bool = Field(default=False)
    mint_min_spread: float = Field(default=0.03)
    mint_prefer_over_buy: bool = Field(default=False)

    # Delta neutral (Phase 2)
    delta_neutral_enabled: bool = Field(default=False)
    delta_neutral_max_edge: float = Field(default=0.03)
    delta_neutral_min_spread: float = Field(default=0.02)

    # Signal agreement
    require_signal_agreement: bool = Field(default=False)
    conflict_mode: str = Field(default="veto", description="veto | reduce | ignore")
    conflict_size_mult: float = Field(default=0.5)

    # Exit routing
    exit_mode: str = Field(default="limit", description="limit | market | auto")
    exit_taker_urgency_min: float = Field(default=2.0)
    hold_to_settlement: bool = Field(default=True)
    settlement_hold_threshold: float = Field(default=0.70)

    # Position management
    max_positions_per_coin: int = Field(default=1)
    max_total_positions: int = Field(default=5)
    position_size_mode: str = Field(default="fixed", description="fixed | edge_scaled | kelly")
    fixed_position_size: float = Field(default=5.0)
    max_position_size: float = Field(default=20.0)
    edge_size_multiplier: float = Field(default=100.0)


# ---------------------------------------------------------------------------
# Controller config
# ---------------------------------------------------------------------------

class QuoteConfig(BaseModel):
    """Configuration for the quote manager (market-making on binary options)."""
    enabled: bool = False
    inner_fraction: float = 0.2
    outer_fraction: float = 0.9
    skew_sensitivity: float = 0.5
    base_size: int = 100
    max_size: int = 500
    reprice_threshold: float = 0.01
    odds_min: float = 0.05
    odds_max: float = 0.95
    min_hours_for_quoting: float = 0.25
    max_capital_per_market: float = 50.0
    max_total_capital: float = 200.0


class BinaryOptionsControllerConfig(ControllerConfigBase):
    """Top-level config for the BinaryOptionsController."""

    controller_type: str = "generic"
    controller_name: str = "binary_options"
    connector_name: str = "limitless"
    # Placeholder pair to trigger connector instantiation
    # (actual markets are discovered dynamically via connector.get_active_markets)
    # NOTE: Must be 2-part (BASE-QUOTE) to satisfy Hummingbot's market init
    trading_pair: str = "BTC-USDC"

    runtime_json_path: str = Field(
        ..., description="Path to runtime.json (hot-reloaded by RuntimeBridge)"
    )
    config_json_path: str = Field(
        ..., description="Path to config.json (static divergence config)"
    )

    poll_interval_ms: int = Field(default=1500)
    vol_warmup_ticks: int = Field(default=20)

    routing: ActionRoutingConfig = Field(default_factory=ActionRoutingConfig)
    quoting: QuoteConfig = Field(default_factory=QuoteConfig)

    def update_markets(self, markets):
        """Register connector so Hummingbot instantiates it."""
        # markets is a GroupedSetDict; call add_or_update directly
        if hasattr(markets, 'add_or_update'):
            return markets.add_or_update(self.connector_name, self.trading_pair)
        return markets

    def get_controller_class(self):
        from .controller import BinaryOptionsController
        return BinaryOptionsController


# ---------------------------------------------------------------------------
# RuntimeBridge — hot-reloadable runtime.json reader
# ---------------------------------------------------------------------------

class RuntimeBridge:
    """Reads runtime.json with mtime-based hot-reload."""

    _RESERVED_KEYS = {"coins", "_meta"}

    def __init__(self, path: str, check_interval: float = 30.0):
        self._path = path
        self._check_interval = check_interval
        self._last_check: float = 0.0
        self._last_mtime: float = 0.0
        self._data: dict = {}
        # Initial load
        self._reload()

    def _reload(self) -> None:
        try:
            with open(self._path, "r") as f:
                self._data = json.load(f)
            self._last_mtime = os.stat(self._path).st_mtime
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("RuntimeBridge: failed to load %s: %s", self._path, e)

    def check(self) -> bool:
        """Stat the file; reload if mtime changed. Returns True if reloaded."""
        now = time.monotonic()
        if now - self._last_check < self._check_interval:
            return False
        self._last_check = now
        try:
            mtime = os.stat(self._path).st_mtime
        except FileNotFoundError:
            return False
        if mtime != self._last_mtime:
            self._reload()
            return True
        return False

    def get_coin_param(self, coin: str, key: str, default=None):
        """Resolve: coins[COIN][key] → top-level key → default."""
        coins = self._data.get("coins", {})
        coin_data = coins.get(coin, {})
        if key in coin_data:
            return coin_data[key]
        if key in self._data:
            return self._data[key]
        return default

    def get_alphas(self, coin: str, interval_secs: float) -> tuple:
        """Return (baseline_alpha, current_alpha, mispricing_alpha) via halflife."""
        bl_hl = self.get_coin_param(coin, "baseline_halflife_secs", 35.0)
        cur_hl = self.get_coin_param(coin, "current_halflife_secs", 12.0)
        mis_hl = self.get_coin_param(coin, "mispricing_halflife_secs", 23.0)
        return (
            halflife_to_alpha(bl_hl, interval_secs),
            halflife_to_alpha(cur_hl, interval_secs),
            halflife_to_alpha(mis_hl, interval_secs),
        )

    def should_trade(self) -> bool:
        """True if trading_enabled and not paused."""
        return bool(self._data.get("trading_enabled", False)) and not bool(
            self._data.get("paused", False)
        )

    @property
    def overrides(self) -> dict:
        """All non-coin, non-meta keys from runtime.json."""
        return {k: v for k, v in self._data.items() if k not in self._RESERVED_KEYS}


# ---------------------------------------------------------------------------
# CoinRoster — tier management
# ---------------------------------------------------------------------------

_TIER_MULTIPLIERS = {
    "BANNED": 0.0,
    "REHAB": 0.5,
    "PROBATION": 0.75,
    "MAIN": 1.0,
}


class CoinRoster:
    """Read-only tier management backed by RuntimeBridge."""

    def __init__(self, runtime_bridge: RuntimeBridge):
        self._rb = runtime_bridge

    def tier(self, coin: str) -> str:
        """Get coin tier from runtime.json, default MAIN."""
        return self._rb.get_coin_param(coin, "tier", "MAIN")

    def size_multiplier(self, coin: str) -> float:
        """Return position-size multiplier for the coin's tier."""
        return _TIER_MULTIPLIERS.get(self.tier(coin), 1.0)

    def ensure_listed(self, coin: str) -> None:
        """No-op — controller is read-only; evaluator manages tiers."""
        pass
