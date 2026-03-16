"""BinaryOptionsController — thin orchestrator wiring all modules together.

This is the ONLY module that imports Hummingbot V2 classes. All other modules
return plain dicts; this module converts them to executor actions.
"""
from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from typing import Dict, List

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TrailingStop, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction

from .action_router import ActionRouter
from .config import BinaryOptionsControllerConfig, CoinRoster, RuntimeBridge
from .exit_monitor import ExitMonitor
from .market_manager import MarketManager
from .position_tracker import PositionTracker
from .quote_manager import QuoteManager, QuoteAction, QuoteActions
from .signal_engine import SignalEngine
from .spot_feed import SpotFeed

logger = logging.getLogger(__name__)


def _load_signal_config(path: str) -> dict:
    """Load the static config.json used by SignalEngine."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Failed to load signal config from %s: %s", path, e)
        return {}


class BinaryOptionsController(ControllerBase):
    """Phase 1 binary-options controller for Limitless markets."""

    def __init__(self, config: BinaryOptionsControllerConfig, market_data_provider, actions_queue):
        super().__init__(config, market_data_provider, actions_queue)

        # Runtime bridge (hot-reloadable runtime.json)
        self.runtime_bridge = RuntimeBridge(config.runtime_json_path)
        self.roster = CoinRoster(self.runtime_bridge)

        # Spot feed (Pyth primary, Binance fallback)
        self.spot_feed = SpotFeed(config)

        # Signal engine (takes a plain dict config)
        signal_cfg = _load_signal_config(config.config_json_path)
        self.signal_engine = SignalEngine(signal_cfg, self.runtime_bridge)

        # Market manager (connector wired in on_start)
        self.market_manager = MarketManager(None, config, self.roster, self.runtime_bridge)

        # Position tracker + exit monitor
        self.position_tracker = PositionTracker(config, self.runtime_bridge)
        self.exit_monitor = ExitMonitor(config, self.runtime_bridge)

        # Action router
        self.action_router = ActionRouter(config.routing, self.position_tracker)

        # Quote manager (MM mode)
        self.quote_manager = QuoteManager(config.quoting, self.runtime_bridge)

        # MM executor map: "COIN:SIDE" -> executor_id
        self._mm_executor_map: Dict[str, str] = {}

    async def on_start(self):
        """Wire the connector once available.
        NOTE: ControllerBase doesn't have self.connectors — that's on the Strategy.
        Market discovery uses Limitless REST API directly (via market_manager),
        not the Hummingbot connector. Phase 2 may wire the connector here.
        """
        pass

    async def update_processed_data(self):
        """Called every tick by the V2 control loop."""
        now_ts = time.time()

        # 1. Hot-reload runtime.json if changed
        self.runtime_bridge.check()

        # 2. Fetch spot prices
        spots = self.spot_feed.get_prices(now_ts)
        btc_spot = spots.get("BTC", 0.0)

        # 3. Market discovery + evaluation + build
        self.market_manager.discover(spots, now_ts)
        self.market_manager.evaluate(now_ts)
        market_data = self.market_manager.build_market_data(now_ts)

        # 4. Update spot feed with pyth addresses from discovered markets
        pyth_addresses = {}
        for coin, md in market_data.items():
            addr = md.get("pyth_address", "")
            if addr:
                pyth_addresses[coin] = addr
        if pyth_addresses:
            self.spot_feed.update_addresses(pyth_addresses)

        # 5. Signal engine tick
        signals = self.signal_engine.tick(spots, market_data, btc_spot, now_ts)

        # 6. Gather MM data if quoting enabled
        if self.config.quoting.enabled:
            orderbook_mids = {}
            reward_spreads = {}
            hours_left_map = {}
            for coin, md in market_data.items():
                orderbook_mids[coin] = md.get("yes_price", 0.5)
                reward_spreads[coin] = md.get("reward_spread", 0.03)
                expiry = md.get("expiry_ts", now_ts + 3600)
                hours_left_map[coin] = max(0, (expiry - now_ts) / 3600)
        else:
            orderbook_mids = {}
            reward_spreads = {}
            hours_left_map = {}

        # 7. Store processed data
        self.processed_data.update({
            "coins": signals,
            "btc_spot": btc_spot,
            "spots": spots,
            "market_data": market_data,
            "now_ts": now_ts,
            "orderbook_mids": orderbook_mids,
            "reward_spreads": reward_spreads,
            "hours_left": hours_left_map,
        })

    def determine_executor_actions(self) -> List:
        """Return Create/Stop actions based on processed data."""
        actions: List = []
        now_ts = self.processed_data.get("now_ts", time.time())
        market_data = self.processed_data.get("market_data", {})
        btc_spot = self.processed_data.get("btc_spot", 0.0)
        signals = self.processed_data.get("coins", {})

        # 0. MM mode branch
        if self.config.quoting.enabled:
            return self._determine_mm_actions()

        # 1. Trading disabled → no actions
        if not self.runtime_bridge.should_trade():
            return actions

        # 2. Check expiry (returns set of expired executor IDs — handled internally)
        self.market_manager.check_expiry(self.executors_info, now_ts)

        # 3. Exit monitor → StopExecutorAction
        exit_dicts = self.exit_monitor.check_all(
            self.executors_info, btc_spot, market_data, now_ts
        )
        for ed in exit_dicts:
            actions.append(StopExecutorAction(
                controller_id=self.config.id,
                executor_id=ed["executor_id"],
            ))

        # 4. Action router → CreateExecutorAction
        entry_dicts = self.action_router.route(signals, market_data, self.executors_info, now_ts)
        for ad in entry_dicts:
            coin = ad.get("coin", "")

            # Per-coin barrier params from runtime bridge
            sl = self.runtime_bridge.get_coin_param(coin, "stop_loss_pct", 0.03)
            tp = self.runtime_bridge.get_coin_param(coin, "take_profit_pct", 0.10)
            tt = self.runtime_bridge.get_coin_param(coin, "trailing_trigger_pct", 0.05)
            td = self.runtime_bridge.get_coin_param(coin, "trailing_distance_pct", 0.02)
            timeout = int(self.runtime_bridge.get_coin_param(coin, "base_timeout_secs", 3600))

            triple_barrier = TripleBarrierConfig(
                stop_loss=Decimal(str(sl)),
                take_profit=Decimal(str(tp)),
                time_limit=timeout,
                trailing_stop={
                    "activation_price": Decimal(str(tt)),
                    "trailing_delta": Decimal(str(td)),
                } if tt and td else None,
                open_order_type=OrderType.LIMIT_MAKER,
            )

            trading_pair = ad.get("slug", ad.get("trading_pair", ""))
            entry_price = ad.get("entry_price")
            amount = ad.get("size", 0.0)

            executor_config = PositionExecutorConfig(
                timestamp=now_ts,
                trading_pair=trading_pair,
                connector_name=self.config.connector_name,
                side=TradeType.BUY,
                entry_price=Decimal(str(entry_price)) if entry_price else None,
                amount=Decimal(str(amount)),
                triple_barrier_config=triple_barrier,
            )

            create_action = CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=executor_config,
            )
            actions.append(create_action)

            # 5. Register with exit monitor and position tracker
            direction = ad.get("direction", "YES")
            self.exit_monitor.register_entry(
                executor_config.id, coin, direction, btc_spot
            )
            self.position_tracker.record_open(
                coin=coin,
                executor_id=executor_config.id,
                direction=direction,
                size=float(amount),
                entry_price=float(entry_price) if entry_price else 0.0,
            )

        # 6. Sync closed executors
        for ei in self.executors_info:
            is_closed = ei.is_closed if hasattr(ei, "is_closed") else False
            if not is_closed:
                continue
            eid = ei.id if hasattr(ei, "id") else ""
            if not eid:
                continue
            # Get coin from exit monitor's records
            coin = self.exit_monitor._executor_coins.get(eid, "")
            pnl = float(ei.net_pnl_quote) if hasattr(ei, "net_pnl_quote") else 0.0
            self.position_tracker.record_close(coin, eid, pnl)
            self.exit_monitor.unregister(eid)

        return actions

    def _determine_mm_actions(self) -> List:
        """MM mode: each quote = a PositionExecutor with full barriers."""
        actions: List = []
        now_ts = self.processed_data.get("now_ts", time.time())
        signals = self.processed_data.get("coins", {})
        market_data = self.processed_data.get("market_data", {})
        orderbook_mids = self.processed_data.get("orderbook_mids", {})
        reward_spreads = self.processed_data.get("reward_spreads", {})
        hours_left = self.processed_data.get("hours_left", {})

        if not self.runtime_bridge.should_trade():
            return actions

        coins = list(market_data.keys())
        quote_actions = self.quote_manager.tick(
            coins, signals, orderbook_mids, reward_spreads, hours_left
        )

        for qa in quote_actions.actions:
            trading_pair = market_data.get(qa.coin, {}).get("slug", "")
            if not trading_pair:
                continue

            if qa.action == "place":
                coin = qa.coin
                executor_config = self._make_mm_executor_config(
                    coin, trading_pair, qa.price, qa.size, hours_left, now_ts
                )
                self._mm_executor_map[f"{qa.coin}:{qa.side}"] = executor_config.id
                actions.append(CreateExecutorAction(
                    controller_id=self.config.id,
                    executor_config=executor_config,
                ))

            elif qa.action == "cancel":
                key = f"{qa.coin}:{qa.side}"
                executor_id = self._mm_executor_map.pop(key, None)
                if executor_id:
                    actions.append(StopExecutorAction(
                        controller_id=self.config.id,
                        executor_id=executor_id,
                    ))

            elif qa.action == "update":
                key = f"{qa.coin}:{qa.side}"
                old_id = self._mm_executor_map.pop(key, None)
                if old_id:
                    actions.append(StopExecutorAction(
                        controller_id=self.config.id,
                        executor_id=old_id,
                    ))
                executor_config = self._make_mm_executor_config(
                    qa.coin, trading_pair, qa.price, qa.size, hours_left, now_ts
                )
                self._mm_executor_map[key] = executor_config.id
                actions.append(CreateExecutorAction(
                    controller_id=self.config.id,
                    executor_config=executor_config,
                ))

            # close_order is NOT handled — PositionExecutor manages exit via barriers

        # Detect fills: notify quote_manager so it can pull opposing side
        for ei in self.executors_info:
            is_active = hasattr(ei, 'is_active') and ei.is_active
            if not is_active:
                continue
            eid = ei.id if hasattr(ei, 'id') else ''
            for key, mapped_id in list(self._mm_executor_map.items()):
                if mapped_id == eid:
                    coin, side = key.split(":", 1)
                    fill_price = float(ei.entry_price) if hasattr(ei, 'entry_price') else 0.0
                    fill_size = float(ei.filled_amount_quote) if hasattr(ei, 'filled_amount_quote') else 0.0
                    if fill_price > 0:
                        fill_actions = self.quote_manager.on_fill(coin, side, fill_price, fill_size)
                        for fa in fill_actions.actions:
                            if fa.action == "cancel":
                                opp_key = f"{fa.coin}:{fa.side}"
                                opp_id = self._mm_executor_map.pop(opp_key, None)
                                if opp_id:
                                    actions.append(StopExecutorAction(
                                        controller_id=self.config.id,
                                        executor_id=opp_id,
                                    ))
                    break

        # Sync closed executors
        for ei in self.executors_info:
            is_closed = ei.is_closed if hasattr(ei, 'is_closed') else False
            if not is_closed:
                continue
            eid = ei.id if hasattr(ei, 'id') else ''
            if eid:
                pnl = float(ei.net_pnl_quote) if hasattr(ei, 'net_pnl_quote') else 0.0
                for key, mapped_id in list(self._mm_executor_map.items()):
                    if mapped_id == eid:
                        coin = key.split(":")[0]
                        self._mm_executor_map.pop(key)
                        self.quote_manager.on_close_fill(coin)
                        self.position_tracker.record_close(coin, eid, pnl)
                        break

        return actions

    def _make_mm_executor_config(
        self, coin: str, trading_pair: str, price: float, size: float,
        hours_left: dict, now_ts: float,
    ) -> PositionExecutorConfig:
        """Build a PositionExecutorConfig with full TripleBarrier for MM quotes."""
        sl = self.runtime_bridge.get_coin_param(coin, "stop_loss_pct", 0.03)
        tp = self.runtime_bridge.get_coin_param(coin, "tp_distance", 0.05)
        tt = self.runtime_bridge.get_coin_param(coin, "trailing_trigger_pct", 0.05)
        td = self.runtime_bridge.get_coin_param(coin, "trailing_distance_pct", 0.02)
        timeout = int(hours_left.get(coin, 1) * 3600)

        triple_barrier = TripleBarrierConfig(
            stop_loss=Decimal(str(sl)),
            take_profit=Decimal(str(tp)),
            trailing_stop=TrailingStop(
                activation_price=Decimal(str(tt)),
                trailing_delta=Decimal(str(td)),
            ) if tt and td else None,
            time_limit=timeout,
            open_order_type=OrderType.LIMIT_MAKER,
        )

        return PositionExecutorConfig(
            timestamp=now_ts,
            trading_pair=trading_pair,
            connector_name=self.config.connector_name,
            side=TradeType.BUY,
            entry_price=Decimal(str(price)),
            amount=Decimal(str(size)),
            triple_barrier_config=triple_barrier,
        )

    def to_format_status(self) -> List[str]:
        """Dashboard display for the Hummingbot status command."""
        lines = []
        trading = self.runtime_bridge.should_trade()
        lines.append(f"  Trading: {'ON' if trading else 'OFF'}")
        lines.append(f"  Open positions: {self.position_tracker.open_count}")
        lines.append(f"  Total exposure: {self.position_tracker.total_exposure:.2f}")

        signals = self.processed_data.get("coins", {})
        btc_spot = self.processed_data.get("btc_spot", 0.0)
        lines.append(f"  BTC spot: {btc_spot:.2f}")

        if signals:
            lines.append("  Signals:")
            for coin, sig in sorted(signals.items()):
                direction = sig.get("direction", "—")
                edge = sig.get("edge", 0.0)
                lines.append(f"    {coin}: dir={direction} edge={edge:.4f}")

        if self.config.quoting.enabled:
            lines.append("  MM Quoting: ON")
            for coin in sorted(self.processed_data.get("market_data", {}).keys()):
                state = self.quote_manager.state(coin).value
                lines.append(f"    {coin}: {state}")

        return lines
