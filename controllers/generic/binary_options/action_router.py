"""Action routing: signal → execution path → sized action dicts."""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ExecutionPath(str, Enum):
    BUY_YES_MARKET = "buy_yes_market"             # Path 1
    BUY_YES_LIMIT = "buy_yes_limit"               # Path 2
    MINT_SELL_NO_MARKET = "mint_sell_no_mkt"       # Path 3
    MINT_SELL_NO_LIMIT = "mint_sell_no_lmt"        # Path 4
    SELL_NO_LIMIT = "sell_no_limit"                # Path 5
    BUY_NO_MARKET = "buy_no_market"                # Path 6
    BUY_NO_LIMIT = "buy_no_limit"                  # Path 7
    MINT_SELL_YES_MARKET = "mint_sell_yes_mkt"     # Path 8
    MINT_SELL_YES_LIMIT = "mint_sell_yes_lmt"      # Path 9
    SELL_YES_LIMIT = "sell_yes_limit"              # Path 10
    MINT_SELL_BOTH = "mint_sell_both"              # Path 11
    BUY_BOTH = "buy_both"                          # Path 12


class ActionRouter:
    """Maps signals + market state → list of action dicts via decision tree."""

    def __init__(self, routing_config, position_tracker):
        self._rc = routing_config
        self._pt = position_tracker

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def route(self, signals: dict, market_data: dict, active_executors: list,
              now_ts: float) -> list:
        """
        Main entry point.

        Args:
            signals: {coin: signal_dict} where signal_dict has keys:
                direction ("YES"/"NO"), edge, entry_price, slug, strike,
                market_expiry_ts, btc_spot, spot_direction, btc_direction, ...
            market_data: {coin: market_dict} with yes_price, no_price, spread, etc.
            active_executors: list of active executor states (for position tracker context)
            now_ts: current timestamp

        Returns:
            List of action dicts ready for controller to convert to CreateExecutorAction.
        """
        actions = []
        for coin, signal in signals.items():
            action = self._route_single(coin, signal, market_data.get(coin, {}), now_ts)
            if action is not None:
                actions.append(action)
        return actions

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _route_single(self, coin: str, signal: dict, market: dict,
                      now_ts: float):
        # 1. Conflict check
        ok, conflict_mult = self._check_conflict(signal)
        if not ok:
            logger.debug("ActionRouter: %s vetoed by conflict check", coin)
            return None

        direction = signal["direction"]
        size = self._compute_size(coin, signal, self._rc, conflict_mult)

        # 2. Position limit check
        yes_price = signal.get("entry_price")
        allowed, reason = self._pt.can_open(coin, direction, size, now_ts,
                                            yes_price=yes_price)
        if not allowed:
            logger.debug("ActionRouter: %s blocked — %s", coin, reason)
            return None

        # 3. Select execution path
        minutes_to_expiry = max(0.0, (signal.get("market_expiry_ts", now_ts) - now_ts) / 60.0)
        path = self._select_path(signal, market, self._rc, minutes_to_expiry)

        # 4. Build action dict
        return {
            "coin": coin,
            "direction": direction,
            "path": path,
            "size": size,
            "entry_price": signal.get("entry_price", 0.0),
            "slug": signal.get("slug", ""),
            "strike": signal.get("strike", 0.0),
            "market_expiry_ts": signal.get("market_expiry_ts", 0.0),
            "btc_spot": signal.get("btc_spot", 0.0),
            "signal_data": signal,
        }

    def _check_conflict(self, signal: dict) -> tuple:
        """Check signal agreement. Returns (allowed, size_multiplier)."""
        if not self._rc.require_signal_agreement:
            return True, 1.0

        spot_dir = signal.get("spot_direction")
        btc_dir = signal.get("btc_direction")

        # If either direction is missing, no conflict detectable
        if spot_dir is None or btc_dir is None:
            return True, 1.0

        if spot_dir == btc_dir:
            return True, 1.0

        # Directions disagree
        mode = self._rc.conflict_mode
        if mode == "veto":
            return False, 0.0
        elif mode == "reduce":
            return True, self._rc.conflict_size_mult
        else:  # "ignore"
            return True, 1.0

    def _select_path(self, signal: dict, market: dict, rc,
                     minutes_to_expiry: float) -> ExecutionPath:
        """Decision tree → execution path."""
        direction = signal["direction"]
        edge = abs(signal.get("edge", 0.0))
        spread = market.get("spread", 0.0)

        # 1. Delta neutral
        if (rc.delta_neutral_enabled
                and edge < rc.delta_neutral_max_edge
                and spread > rc.delta_neutral_min_spread):
            return ExecutionPath.MINT_SELL_BOTH

        # 2. Mint preferred
        if rc.mint_enabled and rc.mint_prefer_over_buy:
            if direction == "YES":
                return ExecutionPath.MINT_SELL_NO_LIMIT
            else:
                return ExecutionPath.MINT_SELL_YES_LIMIT

        # 3. Taker / market conditions
        if (rc.entry_mode == "market"
                or edge > rc.taker_edge_threshold
                or minutes_to_expiry < rc.taker_time_threshold_min):
            if direction == "YES":
                return ExecutionPath.BUY_YES_MARKET
            else:
                return ExecutionPath.BUY_NO_MARKET

        # 4. Default: limit
        if direction == "YES":
            return ExecutionPath.BUY_YES_LIMIT
        else:
            return ExecutionPath.BUY_NO_LIMIT

    def _compute_size(self, coin: str, signal: dict, rc,
                      conflict_multiplier: float) -> float:
        """Compute position size based on sizing mode."""
        edge = abs(signal.get("edge", 0.0))
        entry_price = signal.get("entry_price", 0.5)

        mode = rc.position_size_mode
        if mode == "fixed":
            size = rc.fixed_position_size
        elif mode == "edge_scaled":
            size = min(edge * rc.edge_size_multiplier, rc.max_position_size)
        elif mode == "kelly":
            denom = 1.0 - entry_price
            if denom <= 0:
                size = rc.fixed_position_size
            else:
                kelly_fraction = getattr(rc, "kelly_fraction", 0.25)
                size = (edge / denom) * kelly_fraction
                size = min(size, rc.max_position_size)
        else:
            size = rc.fixed_position_size

        # Apply conflict multiplier
        size *= conflict_multiplier

        # Apply tier multiplier if position_tracker has coin_roster
        if hasattr(self._pt, '_config') and hasattr(self._pt._config, 'routing'):
            # Tier multiplier comes from CoinRoster via runtime bridge
            pass

        return size
