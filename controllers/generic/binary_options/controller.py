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
from hummingbot.strategy_v2.executors.position_executor.data_types import (
    PositionExecutorConfig,
    TrailingStop,
    TripleBarrierConfig,
)
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction

from .action_router import ActionRouter
from .config import BinaryOptionsControllerConfig, CoinRoster, RuntimeBridge
from .exit_monitor import ExitMonitor
from .market_manager import MarketManager
from .position_tracker import PositionTracker
from .quote_manager import QuoteManager
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

        # Spot feed (Binance primary, Pyth fallback)
        self.spot_feed = SpotFeed(config)
        self.spot_feed.core_tickers.add("BTC")

        # Signal engine (takes a plain dict config)
        signal_cfg = _load_signal_config(config.config_json_path)
        self.signal_engine = SignalEngine(signal_cfg, self.runtime_bridge)

        # Market manager (connector wired in on_start)
        self.market_manager = MarketManager(
            None,
            config,
            self.roster,
            self.runtime_bridge,
            exposure_guard=self._coin_has_exposure,
            switch_policy=config.switch_policy,
        )

        # Position tracker + exit monitor
        self.position_tracker = PositionTracker(config, self.runtime_bridge)
        self.exit_monitor = ExitMonitor(config, self.runtime_bridge)

        # Action router
        self.action_router = ActionRouter(config.routing, self.position_tracker)

        # Quote manager (MM mode)
        self.quote_manager = QuoteManager(config.quoting, self.runtime_bridge)

        # MM executor map: "COIN:SIDE" -> executor_id
        self._mm_executor_map: Dict[str, str] = {}
        self._mm_pending_replacements: Dict[str, dict] = {}
        self._mm_pending_cancels: set = set()  # keys awaiting cancel confirmation
        self._mm_executor_created_ts: Dict[str, float] = {}  # key → creation timestamp

        self._last_log_ts: float = 0.0

    async def on_start(self):
        """Called by subclasses or manually — not by ControllerBase."""
        pass

    def _coin_has_exposure(self, coin: str) -> bool:
        """True when the coin has filled inventory or an open position."""
        coin = coin.upper()

        open_positions = getattr(self.position_tracker, "_open_positions", {})
        for position in open_positions.values():
            if position.get("coin", "").upper() == coin:
                return True

        for executor in self.executors_info:
            if getattr(executor, "is_closed", False):
                continue
            executor_coin = (
                getattr(executor, "coin", None)
                or getattr(executor, "trading_pair", "").split("-", 1)[0]
            )
            if not executor_coin or executor_coin.upper() != coin:
                continue

            filled_amount = getattr(executor, "filled_amount_quote", None)
            if filled_amount is not None and float(filled_amount) > 0:
                return True

        return False

    def _ensure_connector(self):
        """Wire the connector from market_data_provider on first tick."""
        if self.market_manager._connector is not None:
            self._apply_connector_paper_mode(self.market_manager._connector)
            return
        connector = self.market_data_provider.connectors.get(self.config.connector_name)
        if connector:
            self.market_manager._connector = connector
            self._apply_connector_paper_mode(connector)

            logger.info("BinaryOptionsController: connector '%s' wired to market_manager",
                        self.config.connector_name)
        else:
            logger.debug("BinaryOptionsController: connector '%s' not yet available",
                         self.config.connector_name)

    def _apply_connector_paper_mode(self, connector) -> None:
        """Push controller paper_mode into the exchange connector."""
        if hasattr(connector, "paper_mode"):
            connector.paper_mode = self.config.paper_mode

    async def update_processed_data(self):
        """Called every tick by the V2 control loop."""
        now_ts = time.time()

        # 0. Wire connector on first tick
        self._ensure_connector()

        # 1. Hot-reload runtime.json if changed
        self.runtime_bridge.check()

        # 2. Fetch spot prices
        spots = self.spot_feed.get_prices(now_ts)
        btc_spot = spots.get("BTC", 0.0)

        # 3. Market discovery + evaluation + build
        await self.market_manager.discover(spots, now_ts)
        await self.market_manager.evaluate(now_ts)
        market_data = await self.market_manager.build_market_data(now_ts)

        # 3b. Register discovered markets with connector for order execution
        connector = self.market_manager._connector
        if connector and hasattr(connector, "register_market"):
            for coin, md in market_data.items():
                slug = md.get("slug", "")
                if slug:
                    await connector.register_market(slug, f"{coin}-USDC")
        if (now_ts - self._last_log_ts) >= 30.0:
            logger.info("tick: %d coins tracked (ETH-USDC), btc_ref=%.2f", len(market_data), btc_spot)
            for coin, md in market_data.items():
                logger.debug(
                    "  %s: yes=%.4f bid=%.4f ask=%.4f strike=%.2f",
                    coin,
                    md.get("yes_price", 0.0),
                    md.get("bid", 0.0),
                    md.get("ask", 0.0),
                    md.get("strike", 0.0),
                )
            self._last_log_ts = now_ts

        # 4. Update spot feed — add locked coins so Binance fetches them
        for coin in market_data:
            self.spot_feed.core_tickers.add(coin)
        # Also pass pyth addresses if available (fallback)
        pyth_addresses = {}
        for coin, md in market_data.items():
            addr = md.get("pyth_address", "")
            if addr:
                pyth_addresses[coin] = addr
        if pyth_addresses:
            self.spot_feed.update_addresses(pyth_addresses)

        # 5. Signal engine tick
        signals = self.signal_engine.tick(spots, market_data, btc_spot, now_ts)
        for coin, sig in signals.items():
            spot_z = sig.get("z_score", 0.0)
            btc_z = sig.get("btc_z_score", 0.0)
            misp = sig.get("mispricing", 0.0)
            if spot_z != 0.0 or btc_z != 0.0 or misp != 0.0:
                logger.info(
                    "signal[%s]: spot_z=%.3f btc_z=%.3f misp=%.4f fair=%.4f yes=%.4f vol=%.4f conf=%s",
                    coin, spot_z, btc_z, misp,
                    sig.get("model_prob", 0.0),
                    self.processed_data.get("market_data", {}).get(coin, {}).get("yes_price", 0.0),
                    sig.get("vol", 0.0),
                    sig.get("confidence", "LOW"),
                )

        # 6. Gather MM data if quoting enabled
        if self.config.quoting.enabled:
            orderbook_mids = {}
            reward_spreads = {}
            hours_left_map = {}
            price_surfaces = {}
            for coin, md in market_data.items():
                yes_mid = md.get("yes_mid")
                if not md.get("quote_valid") or yes_mid is None:
                    continue
                orderbook_mids[coin] = yes_mid
                reward_spreads[coin] = md.get("reward_spread", 0.03)
                price_surfaces[coin] = md.get("price_surface") or {
                    "yes_bid": md.get("yes_bid"),
                    "yes_ask": md.get("yes_ask"),
                    "yes_mid": md.get("yes_mid"),
                    "no_bid": md.get("no_bid") if md.get("no_bid") is not None else (round(1.0 - md.get("yes_ask"), 12) if md.get("yes_ask") is not None else None),
                    "no_ask": md.get("no_ask") if md.get("no_ask") is not None else (round(1.0 - md.get("yes_bid"), 12) if md.get("yes_bid") is not None else None),
                    "no_mid": md.get("no_mid") if md.get("no_mid") is not None else (round(1.0 - md.get("yes_mid"), 12) if md.get("yes_mid") is not None else None),
                    "quote_valid": md.get("quote_valid", False),
                }
                expiry = md.get("expiry_ts", now_ts + 3600)
                hours_left_map[coin] = max(0, (expiry - now_ts) / 3600)
        else:
            orderbook_mids = {}
            reward_spreads = {}
            hours_left_map = {}
            price_surfaces = {}

        # 7. Store processed data
        self.processed_data.update({
            "coins": signals,
            "btc_spot": btc_spot,
            "spots": spots,
            "market_data": market_data,
            "now_ts": now_ts,
            "orderbook_mids": orderbook_mids,
            "price_surfaces": price_surfaces,
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
        if exit_dicts:
            logger.info(
                "exit_monitor: %d exits → %s",
                len(exit_dicts),
                [ed.get("executor_id", "") for ed in exit_dicts],
            )
        for ed in exit_dicts:
            actions.append(StopExecutorAction(
                controller_id=self.config.id,
                executor_id=ed["executor_id"],
            ))

        # 4. Action router → CreateExecutorAction
        entry_dicts = self.action_router.route(signals, market_data, self.executors_info, now_ts)
        if entry_dicts:
            logger.info(
                "action_router: %d entries → %s",
                len(entry_dicts),
                [ad.get("coin", "") for ad in entry_dicts],
            )
        elif signals:
            logger.debug(
                "action_router: no entries (signals: %s)",
                [
                    f"{coin}:{sig.get('direction') or '-'}:{sig.get('edge', 0.0):.4f}"
                    for coin, sig in signals.items()
                    if (
                        sig.get("z_score", 0.0) != 0.0
                        or sig.get("btc_z_score", 0.0) != 0.0
                        or sig.get("edge", 0.0) != 0.0
                        or sig.get("direction") is not None
                        or sig.get("entry_path") is not None
                        or sig.get("spot_signal", False)
                        or sig.get("btc_signal", False)
                    )
                ],
            )
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
        price_surfaces = self.processed_data.get("price_surfaces", {})
        reward_spreads = self.processed_data.get("reward_spreads", {})
        hours_left = self.processed_data.get("hours_left", {})

        if not self.runtime_bridge.should_trade():
            return actions

        self._sync_mm_closed_executors(prune_missing=True)

        # Warmup gate: don't quote until signals are valid (vol needs ~100 ticks)
        coins = list(market_data.keys())
        warmed = [
            c for c in orderbook_mids.keys()
            if abs(signals.get(c, {}).get("z_score", 0.0)) > 0
            and abs(signals.get(c, {}).get("btc_z_score", 0.0)) > 0
        ]
        if not warmed:
            return actions

        quote_actions = self.quote_manager.tick(
            warmed, signals, orderbook_mids, reward_spreads, hours_left, price_surfaces=price_surfaces
        )
        action_summary = "none"
        if quote_actions.actions:
            counts: Dict[str, int] = {}
            for qa in quote_actions.actions:
                counts[qa.action] = counts.get(qa.action, 0) + 1
            action_summary = ",".join(
                f"{action}={count}" for action, count in sorted(counts.items())
            )
        logger.info("mm_tick: %d coins, actions: %s", len(coins), action_summary)

        for qa in quote_actions.actions:
            trading_pair = f"{qa.coin}-USDC"
            if not trading_pair:
                continue
            key = f"{qa.coin}:{qa.side}"

            if qa.action == "place":
                in_map = key in self._mm_executor_map
                in_repl = key in self._mm_pending_replacements
                in_cancel = key in self._mm_pending_cancels
                if in_map or in_repl or in_cancel:
                    logger.info(
                        "BLOCKED place %s: map=%s repl=%s cancel=%s mid=%s",
                        key, in_map, in_repl, in_cancel,
                        self._mm_executor_map.get(key, "n/a"),
                    )
                    continue
                self._create_mm_executor_action(
                    actions=actions,
                    coin=qa.coin,
                    side=qa.side,
                    trading_pair=trading_pair,
                    price=qa.price,
                    size=qa.size,
                    hours_left=hours_left,
                    now_ts=now_ts,
                )

            elif qa.action == "cancel":
                self._mm_pending_replacements.pop(key, None)
                executor_id = self._mm_executor_map.pop(key, None)
                self._mm_executor_created_ts.pop(key, None)
                self._mm_pending_cancels.discard(key)
                if executor_id:
                    actions.append(StopExecutorAction(
                        controller_id=self.config.id,
                        executor_id=executor_id,
                    ))
                self.quote_manager.clear_order(qa.coin, qa.side)

            elif qa.action == "update":
                replacement = {
                    "coin": qa.coin,
                    "side": qa.side,
                    "price": qa.price,
                    "size": qa.size,
                    "trading_pair": trading_pair,
                    "ts": now_ts,
                }
                old_id = self._mm_executor_map.pop(key, None)
                self._mm_executor_created_ts.pop(key, None)
                self._mm_pending_cancels.discard(key)
                already_pending = key in self._mm_pending_replacements
                self._mm_pending_replacements[key] = replacement
                if old_id and not already_pending:
                    actions.append(StopExecutorAction(
                        controller_id=self.config.id,
                        executor_id=old_id,
                    ))
                elif not old_id:
                    self._create_pending_mm_replacement(
                        key=key,
                        actions=actions,
                        hours_left=hours_left,
                    )

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
                                self._mm_pending_replacements.pop(opp_key, None)
                                opp_id = self._mm_executor_map.get(opp_key)
                                if opp_id:
                                    actions.append(StopExecutorAction(
                                        controller_id=self.config.id,
                                        executor_id=opp_id,
                                    ))
                    break

        self._sync_mm_closed_executors(prune_missing=False)
        for key in list(self._mm_pending_replacements.keys()):
            if key not in self._mm_executor_map:
                self._create_pending_mm_replacement(
                    key=key,
                    actions=actions,
                    hours_left=hours_left,
                )

        return actions

    def _create_mm_executor_action(
        self,
        actions: List,
        coin: str,
        side: str,
        trading_pair: str,
        price: float,
        size: float,
        hours_left: dict,
        now_ts: float,
    ) -> None:
        executor_config = self._make_mm_executor_config(
            coin, trading_pair, price, size, hours_left, now_ts, side=side
        )
        key = f"{coin}:{side}"
        self._mm_executor_map[key] = executor_config.id
        self._mm_executor_created_ts[key] = time.time()
        self.quote_manager.set_order_id(coin, side, executor_config.id)
        logger.info(
            "PLACE %s %s @ %.4f size=%.2f pair=%s",
            coin, side, float(executor_config.entry_price),
            float(executor_config.amount), executor_config.trading_pair,
        )
        actions.append(CreateExecutorAction(
            controller_id=self.config.id,
            executor_config=executor_config,
        ))

    def _create_pending_mm_replacement(self, key: str, actions: List, hours_left: dict) -> None:
        replacement = self._mm_pending_replacements.pop(key, None)
        if replacement is None:
            return
        self._create_mm_executor_action(
            actions=actions,
            coin=replacement["coin"],
            side=replacement["side"],
            trading_pair=replacement["trading_pair"],
            price=replacement["price"],
            size=replacement["size"],
            hours_left=hours_left,
            now_ts=replacement["ts"],
        )

    def _sync_mm_closed_executors(self, prune_missing: bool) -> None:
        executor_ids = {
            getattr(ei, "id", "")
            for ei in self.executors_info
            if getattr(ei, "id", "")
        }
        for ei in self.executors_info:
            if not getattr(ei, "is_closed", False):
                continue
            eid = getattr(ei, "id", "")
            if not eid:
                continue
            pnl = float(ei.net_pnl_quote) if hasattr(ei, "net_pnl_quote") else 0.0
            for key, mapped_id in list(self._mm_executor_map.items()):
                if mapped_id == eid:
                    coin = key.split(":")[0]
                    self._mm_executor_map.pop(key, None)
                    self._mm_executor_created_ts.pop(key, None)
                    self._mm_pending_cancels.discard(key)
                    self.quote_manager.on_close_fill(coin)
                    self.position_tracker.record_close(coin, eid, pnl)
                    break

        if prune_missing:
            now = time.time()
            for key, mapped_id in list(self._mm_executor_map.items()):
                if mapped_id not in executor_ids:
                    # Grace period: don't prune executors created < 10s ago (hbot hasn't registered yet)
                    created = self._mm_executor_created_ts.get(key, 0)
                    if now - created < 10:
                        continue
                    self._mm_executor_map.pop(key, None)
                    self._mm_executor_created_ts.pop(key, None)
                    self._mm_pending_cancels.discard(key)

    def _make_mm_executor_config(
        self, coin: str, trading_pair: str, price: float, size: float,
        hours_left: dict, now_ts: float, side: str = "YES",
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

        # Both sides use TradeType.BUY for PositionExecutor —
        # Hummingbot's SELL path needs asks in orderbook (we don't have them).
        # NO side uses "COINNO-USDC" trading pair so connector can route token.
        # Format: ETH-USDC -> ETHNO-USDC (single dash for Hummingbot base-quote compat)
        if side == "NO":
            entry = Decimal(str(price))
            tp_for_executor = trading_pair.replace("-USDC", "NO-USDC")
        else:
            entry = Decimal(str(price))
            tp_for_executor = trading_pair

        return PositionExecutorConfig(
            timestamp=now_ts,
            trading_pair=tp_for_executor,
            connector_name=self.config.connector_name,
            side=TradeType.BUY,
            entry_price=entry,
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
