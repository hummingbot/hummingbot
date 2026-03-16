"""Limitless Market Making Bot — Phase 1.

Bracket-quote market maker for Limitless prediction markets.
Posts bid/ask around mid price, manages inventory via Avellaneda-Stoikov lite skew,
handles market lifecycle (ACTIVE → WIND_DOWN → HANDS_OFF), and rolls to new markets.

Usage:
    python3 mm_bot.py [--paper] [--market SLUG] [--config PATH]
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from connector import ConnectorError, LimitlessConnector

logger = logging.getLogger("mm_bot")

# ── Constants ──────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DEFAULT_CONFIG = PROJECT_DIR / "config" / "mm_config.json"
TRADES_CSV = PROJECT_DIR / "data" / "trades.csv"


class Phase(Enum):
    ACTIVE = "ACTIVE"
    WIND_DOWN = "WIND_DOWN"
    HANDS_OFF = "HANDS_OFF"
    WAITING = "WAITING"  # between markets


# ── Config ─────────────────────────────────────────────────────

class MMConfig:
    """Market making configuration loaded from JSON."""

    DEFAULTS = {
        "ticker": "BTC",
        "timeframes": ["1H"],
        "base_spread": 0.04,
        "base_size": 20.0,
        "skew_factor": 0.01,
        "max_inventory": 100.0,
        "wind_down_multiplier": 2.0,
        "tick_interval_s": 5,
        "active_phase_end_min": 15,
        "wind_down_end_min": 5,
        "hands_off_min": 5,
        "max_order_size_usd": 20.0,
        "min_spread": 0.02,
        "max_spread": 0.10,
        "reprice_threshold": 0.01,
        "max_loss_per_hour": 50.0,
        "paper_mode": True,
        "log_level": "INFO",
    }

    def __init__(self, path: Optional[str] = None):
        data = dict(self.DEFAULTS)
        if path and os.path.exists(path):
            with open(path) as f:
                data.update(json.load(f))
            logger.info("Config loaded from %s", path)
        else:
            logger.warning("No config file at %s, using defaults", path)

        for k, v in data.items():
            setattr(self, k, v)


# ── Trade Logger ───────────────────────────────────────────────

class TradeLogger:
    """Append-only CSV trade log."""

    HEADER = [
        "timestamp", "market_slug", "side", "price", "size",
        "fill_type", "inventory_after", "pnl_est",
    ]

    def __init__(self, path: Path):
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with open(path, "w", newline="") as f:
                csv.writer(f).writerow(self.HEADER)

    def log(self, market_slug: str, side: str, price: float, size: float,
            fill_type: str, inventory_after: float, pnl_est: float):
        with open(self._path, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.now(timezone.utc).isoformat(),
                market_slug, side, f"{price:.4f}", f"{size:.2f}",
                fill_type, f"{inventory_after:.2f}", f"{pnl_est:.4f}",
            ])


# ── Market Maker ───────────────────────────────────────────────

class MarketMaker:
    """Core market making engine.

    Manages a single market at a time: discovers markets, posts quotes,
    tracks inventory, handles lifecycle phases, and rolls to new markets.
    """

    def __init__(self, connector: LimitlessConnector, config: MMConfig):
        self.connector = connector
        self.cfg = config
        self.trade_log = TradeLogger(TRADES_CSV)

        # State
        self._market_slug: Optional[str] = None
        self._market_data: Optional[dict] = None
        self._phase = Phase.WAITING
        self._inventory: float = 0.0  # net YES shares (positive = long YES)
        self._active_bid_id: Optional[str] = None
        self._active_ask_id: Optional[str] = None
        self._bid_price: float = 0.0
        self._ask_price: float = 0.0
        self._bid_size: float = 0.0
        self._ask_size: float = 0.0
        self._fills: list[dict] = []
        self._realized_pnl: float = 0.0
        self._hour_loss: float = 0.0
        self._hour_start: float = time.time()
        self._running = False
        self._expiry_ts: Optional[float] = None
        self._last_known_orders: dict[str, dict] = {}  # order_id -> order info

    # ── Lifecycle Phase ────────────────────────────────────────

    def _get_phase(self) -> Phase:
        """Determine current phase based on time to expiry."""
        if self._expiry_ts is None:
            return Phase.WAITING

        now = time.time()
        ttx_s = self._expiry_ts - now  # seconds to expiry
        ttx_min = ttx_s / 60.0

        if ttx_min <= 0:
            return Phase.WAITING
        if ttx_min <= self.cfg.hands_off_min:
            return Phase.HANDS_OFF
        if ttx_min <= (self.cfg.hands_off_min + self.cfg.wind_down_end_min):
            return Phase.WIND_DOWN
        return Phase.ACTIVE

    def _parse_expiry(self, market_data: dict) -> Optional[float]:
        """Extract expiry timestamp from market data.

        Limitless expiration_date is just a date string like 'Mar 15, 2026'.
        The actual expiry time is embedded in the title: 'on Mar 15, 11:30 UTC'.
        We parse from the title first, falling back to other formats.
        """
        import re
        from datetime import datetime as dt, timezone

        # Try parsing from title: "on Mar 15, 11:30 UTC" or "on Mar 15, 11:30 UTC?"
        title = market_data.get("title") or ""
        m = re.search(r'on\s+(\w+\s+\d+),?\s+(\d{1,2}:\d{2})\s*UTC', title)
        if m:
            try:
                date_part = m.group(1)  # "Mar 15"
                time_part = m.group(2)  # "11:30"
                year = dt.now(timezone.utc).year
                d = dt.strptime(f"{date_part} {year} {time_part}", "%b %d %Y %H:%M")
                d = d.replace(tzinfo=timezone.utc)
                return d.timestamp()
            except Exception:
                pass

        # Fallback: numeric or ISO expiration_date
        exp = market_data.get("expiration_date")
        if exp is None:
            return None
        if isinstance(exp, (int, float)):
            return float(exp)
        try:
            if isinstance(exp, str):
                exp_clean = exp.replace("Z", "+00:00")
                d = dt.fromisoformat(exp_clean)
                return d.timestamp()
        except Exception:
            pass
        return None

    # ── Market Discovery ───────────────────────────────────────

    async def discover_market(self) -> Optional[str]:
        """Find the best active market for configured ticker."""
        try:
            markets = await self.connector.get_active_markets(ticker=self.cfg.ticker)
        except ConnectorError as e:
            logger.error("Market discovery failed: %s", e)
            return None

        if not markets:
            logger.warning("No active markets for ticker=%s", self.cfg.ticker)
            return None

        # Filter by timeframe tags if present in title
        now = time.time()
        candidates = []
        for m in markets:
            slug = m.get("slug", "")
            exp = self._parse_expiry(m)
            if exp is None or exp <= now:
                continue  # already expired
            # Check timeframe hint in slug/title
            title = (m.get("title") or "").lower()
            slug_lower = slug.lower()
            tf_match = False
            for tf in self.cfg.timeframes:
                tf_lower = tf.lower()
                if tf_lower in slug_lower or tf_lower in title:
                    tf_match = True
                    break
            # If no timeframe filter matches, still consider if only option
            candidates.append((slug, exp, tf_match, m))

        # Prefer timeframe matches
        tf_matches = [(s, e, m_data) for s, e, tf, m_data in candidates if tf]
        pool = tf_matches if tf_matches else [(s, e, m_data) for s, e, _, m_data in candidates]

        if not pool:
            logger.warning("No valid market candidates found")
            return None

        # Pick the one expiring soonest that still has enough time
        pool.sort(key=lambda x: x[1])
        for slug, exp, m_data in pool:
            ttx_min = (exp - now) / 60.0
            if ttx_min > self.cfg.hands_off_min:
                self._market_data = m_data
                self._expiry_ts = exp
                # Cache market in connector and subscribe WS
                try:
                    await self.connector.get_market(slug)
                except Exception as e:
                    logger.warning("Failed to cache market %s: %s", slug, e)
                try:
                    await self.connector.subscribe_market(slug)
                except Exception as e:
                    logger.warning("Failed to subscribe WS for %s: %s", slug, e)
                logger.info("Discovered market: %s (expires in %.1f min)", slug, ttx_min)
                return slug

        logger.warning("All markets too close to expiry")
        return None

    # ── Inventory Management ───────────────────────────────────

    def _inventory_decay(self, inv_abs: float) -> float:
        """Reduce size as inventory grows. Returns multiplier 0.1-1.0."""
        return max(0.1, 1.0 - (inv_abs / self.cfg.max_inventory) * 0.8)

    def _compute_quotes(self, mid: float) -> tuple[float, float, float, float]:
        """Compute bid/ask price and size based on mid, inventory, and phase.

        Returns (bid_price, ask_price, bid_size, ask_size).
        """
        spread = self.cfg.base_spread
        if self._phase == Phase.WIND_DOWN:
            spread *= self.cfg.wind_down_multiplier

        # Clamp spread
        spread = max(self.cfg.min_spread, min(self.cfg.max_spread, spread))

        # Inventory skew (Avellaneda-Stoikov lite)
        skew = self._inventory * self.cfg.skew_factor

        bid_price = mid - spread / 2.0 - skew
        ask_price = mid + spread / 2.0 - skew

        # Clamp to valid prediction market range
        bid_price = max(0.01, min(0.99, bid_price))
        ask_price = max(0.01, min(0.99, ask_price))

        # Ensure bid < ask
        if bid_price >= ask_price:
            mid_adj = (bid_price + ask_price) / 2.0
            bid_price = max(0.01, mid_adj - self.cfg.min_spread / 2.0)
            ask_price = min(0.99, mid_adj + self.cfg.min_spread / 2.0)

        # Size with inventory decay
        inv_abs = abs(self._inventory)
        bid_size = self.cfg.base_size
        ask_size = self.cfg.base_size

        if inv_abs > 0:
            decay = self._inventory_decay(inv_abs)
            if self._inventory > 0:
                # Long YES — reduce bid (buying) size, keep ask (selling)
                bid_size *= decay
            else:
                # Long NO — reduce ask (selling) size, keep bid (buying)
                ask_size *= decay

        # Hard limit: stop quoting heavy side if over max inventory
        if self._inventory >= self.cfg.max_inventory:
            bid_size = 0.0
        elif self._inventory <= -self.cfg.max_inventory:
            ask_size = 0.0

        return bid_price, ask_price, bid_size, ask_size

    # ── Order Management ───────────────────────────────────────

    async def _cancel_order(self, order_id: Optional[str], label: str) -> None:
        """Cancel a single order, clearing local tracking."""
        if order_id is None:
            return
        try:
            await self.connector.cancel(order_id)
            logger.debug("Cancelled %s order %s", label, order_id)
        except ConnectorError as e:
            logger.warning("Cancel %s %s failed: %s", label, order_id, e)

    async def _cancel_all_orders(self) -> None:
        """Cancel all orders on current market."""
        if self._market_slug:
            try:
                await self.connector.cancel_all(self._market_slug)
            except ConnectorError as e:
                logger.warning("Cancel all failed: %s", e)
        self._active_bid_id = None
        self._active_ask_id = None
        self._bid_price = 0.0
        self._ask_price = 0.0
        self._bid_size = 0.0
        self._ask_size = 0.0
        self._last_known_orders.clear()

    async def _settle_and_redeem(self, market_slug: str) -> None:
        """Wait for market resolution then redeem winning tokens."""
        logger.info("Waiting for %s to resolve...", market_slug[:40])
        max_wait = 120  # 2 min max wait for resolution
        waited = 0
        while waited < max_wait:
            try:
                # Re-fetch market to check resolution status
                market = await self.connector.get_market(market_slug)
                status = market.get("status", "") if isinstance(market, dict) else getattr(market, "status", "")
                if status == "RESOLVED":
                    logger.info("Market resolved. Redeeming positions...")
                    try:
                        result = await self.connector.redeem_positions(market_slug)
                        redeemed = result.get("usdc_redeemed", 0)
                        balance = result.get("usdc_balance", 0)
                        logger.info(
                            "Redeemed +$%.4f USDC (balance: $%.4f)",
                            redeemed, balance,
                        )
                    except ConnectorError as e:
                        logger.error("Redeem failed: %s", e)
                    return
                else:
                    logger.debug("Market status: %s, waiting...", status)
            except ConnectorError as e:
                logger.warning("Failed to check market status: %s", e)

            await asyncio.sleep(10)
            waited += 10

        logger.warning("Market %s not resolved after %ds, skipping redeem", market_slug[:40], max_wait)

    def _needs_reprice(self, new_bid: float, new_ask: float) -> bool:
        """Check if prices moved enough to warrant cancel-replace."""
        if self._active_bid_id is None and self._active_ask_id is None:
            return True
        bid_diff = abs(new_bid - self._bid_price)
        ask_diff = abs(new_ask - self._ask_price)
        return bid_diff >= self.cfg.reprice_threshold or ask_diff >= self.cfg.reprice_threshold

    async def _detect_fills(self) -> None:
        """Detect fills by checking if tracked orders are still open."""
        if not self._market_slug:
            return

        # In paper mode, check connector's tracked orders
        if self.connector.paper_mode:
            tracked = self.connector.tracked_orders
            for oid, label, side, price, size in [
                (self._active_bid_id, "bid", "BUY", self._bid_price, self._bid_size),
                (self._active_ask_id, "ask", "SELL", self._ask_price, self._ask_size),
            ]:
                if oid and oid not in tracked:
                    # Order gone from tracker — treat as filled
                    self._on_fill(side, price, size)
                    if label == "bid":
                        self._active_bid_id = None
                    else:
                        self._active_ask_id = None
            return

        # Live mode: poll open orders
        try:
            open_orders = await self.connector.get_open_orders(self._market_slug)
            open_ids = set()
            for o in open_orders:
                oid = getattr(o, "id", None) or (o.get("id") if isinstance(o, dict) else None)
                if oid:
                    open_ids.add(str(oid))

            for oid, label, side, price, size in [
                (self._active_bid_id, "bid", "BUY", self._bid_price, self._bid_size),
                (self._active_ask_id, "ask", "SELL", self._ask_price, self._ask_size),
            ]:
                if oid and str(oid) not in open_ids:
                    self._on_fill(side, price, size)
                    if label == "bid":
                        self._active_bid_id = None
                    else:
                        self._active_ask_id = None

        except ConnectorError as e:
            logger.warning("Fill detection failed: %s", e)

    def _on_fill(self, side: str, price: float, size: float) -> None:
        """Handle a detected fill."""
        if side == "BUY":
            self._inventory += size
            spread_half = abs(self._ask_price - price) if self._ask_price else 0
        else:
            self._inventory -= size
            spread_half = abs(price - self._bid_price) if self._bid_price else 0

        pnl_est = spread_half * size  # rough estimate
        self._realized_pnl += pnl_est

        logger.info(
            "FILL %s %.1f@%.4f | inv=%.1f | pnl_est=$%.4f",
            side, size, price, self._inventory, pnl_est,
        )

        self.trade_log.log(
            market_slug=self._market_slug or "unknown",
            side=side, price=price, size=size,
            fill_type="maker", inventory_after=self._inventory,
            pnl_est=pnl_est,
        )

        self._fills.append({
            "time": time.time(), "side": side, "price": price,
            "size": size, "inventory_after": self._inventory,
        })

    # ── Risk Controls ──────────────────────────────────────────

    def _check_risk(self) -> bool:
        """Check risk limits. Returns True if safe to continue."""
        # Reset hourly loss tracker
        if time.time() - self._hour_start > 3600:
            self._hour_loss = 0.0
            self._hour_start = time.time()

        if self._hour_loss > self.cfg.max_loss_per_hour:
            logger.error("KILL SWITCH: hourly loss $%.2f > $%.2f",
                         self._hour_loss, self.cfg.max_loss_per_hour)
            return False
        return True

    # ── Core Tick ──────────────────────────────────────────────

    async def tick(self) -> None:
        """Single iteration of the market making loop."""
        if not self._market_slug:
            return

        # Update phase
        prev_phase = self._phase
        self._phase = self._get_phase()

        if self._phase != prev_phase:
            logger.info("Phase change: %s → %s", prev_phase.value, self._phase.value)

        # WAITING: need a new market
        if self._phase == Phase.WAITING:
            await self._cancel_all_orders()
            return

        # HANDS_OFF: cancel everything, hold positions
        if self._phase == Phase.HANDS_OFF:
            if prev_phase != Phase.HANDS_OFF:
                logger.info("HANDS_OFF: cancelling all orders, holding inventory=%.1f",
                            self._inventory)
                await self._cancel_all_orders()
            return

        # Risk check
        if not self._check_risk():
            await self._cancel_all_orders()
            self._running = False
            return

        # Detect fills from previous tick
        await self._detect_fills()

        # Get mid price
        try:
            mid = await self.connector.get_mid_price(self._market_slug)
        except ConnectorError as e:
            # No orderbook / no bid-ask → circuit breaker
            logger.warning("No mid price available — skipping tick (%s)", e)
            return

        # Check spread sanity (circuit breaker)
        try:
            best_bid, best_ask = await self.connector.get_best_bid_ask(self._market_slug)
            if best_bid is not None and best_ask is not None:
                market_spread = best_ask - best_bid
                if market_spread < self.cfg.min_spread:
                    logger.warning("Market spread %.4f < min_spread %.4f — skipping",
                                   market_spread, self.cfg.min_spread)
                    return
        except ConnectorError:
            pass

        # Compute quotes
        bid_price, ask_price, bid_size, ask_size = self._compute_quotes(mid)

        # Check if reprice needed
        phase_changed = (prev_phase != self._phase)
        if not phase_changed and not self._needs_reprice(bid_price, ask_price):
            return  # prices haven't moved enough

        # Cancel stale orders and place new ones
        await self._cancel_all_orders()

        # Place bid
        if bid_size > 0:
            try:
                result = await self.connector.buy(
                    self._market_slug, bid_price, bid_size, "GTC", "YES",
                )
                self._active_bid_id = result.get("order_id")
                self._bid_price = bid_price
                self._bid_size = bid_size
            except ConnectorError as e:
                logger.error("Bid placement failed: %s", e)

        # Place ask (BUY NO at complementary price — equivalent to selling YES)
        if ask_size > 0:
            try:
                no_price = round(1.0 - ask_price, 4)
                result = await self.connector.buy(
                    self._market_slug, no_price, ask_size, "GTC", "NO",
                )
                self._active_ask_id = result.get("order_id")
                self._ask_price = ask_price
                self._ask_size = ask_size
            except ConnectorError as e:
                logger.error("Ask placement failed: %s", e)

        # Log state
        ttx = (self._expiry_ts - time.time()) / 60.0 if self._expiry_ts else 0
        logger.info(
            "%s | mid=%.4f | bid=%.4f(%s) ask=%.4f(%s) | inv=%.1f | phase=%s | ttx=%.1fm",
            self._market_slug, mid,
            bid_price, f"{bid_size:.1f}" if bid_size > 0 else "OFF",
            ask_price, f"{ask_size:.1f}" if ask_size > 0 else "OFF",
            self._inventory, self._phase.value, ttx,
        )

    # ── Main Loop ──────────────────────────────────────────────

    async def run(self, market_override: Optional[str] = None) -> None:
        """Main market making loop."""
        self._running = True
        logger.info("MarketMaker starting (paper=%s)", self.connector.paper_mode)

        await self.connector.start()

        try:
            while self._running:
                # Discover or use override market
                if self._market_slug is None or self._phase == Phase.WAITING:
                    if market_override:
                        slug = market_override
                        try:
                            m = await self.connector.get_market(slug)
                            self._market_data = m
                            self._expiry_ts = self._parse_expiry(m)
                            self._market_slug = slug
                            logger.info("Using market override: %s", slug)
                        except ConnectorError as e:
                            logger.error("Failed to load market %s: %s", slug, e)
                            await asyncio.sleep(self.cfg.tick_interval_s)
                            continue
                    else:
                        slug = await self.discover_market()
                        if slug:
                            self._market_slug = slug
                            self._inventory = 0.0  # reset for new market
                            self._fills.clear()
                        else:
                            logger.info("No market available, waiting...")
                            await asyncio.sleep(self.cfg.tick_interval_s * 2)
                            continue

                    self._phase = self._get_phase()

                # Run tick
                try:
                    await self.tick()
                except Exception as e:
                    logger.exception("Tick error: %s", e)

                await asyncio.sleep(self.cfg.tick_interval_s)

                # Check if market expired → redeem + rollover
                if self._phase == Phase.WAITING:
                    logger.info("Market expired. Inventory=%.1f, PnL=$%.4f. Settling...",
                                self._inventory, self._realized_pnl)

                    # Wait for market to resolve, then redeem
                    settled_slug = self._market_slug
                    if settled_slug and not self.connector.paper_mode:
                        await self._settle_and_redeem(settled_slug)

                    self._market_slug = None
                    self._market_data = None
                    self._expiry_ts = None
                    if market_override:
                        logger.info("Market override expired, stopping.")
                        break

        finally:
            logger.info("Shutting down — cancelling all orders")
            await self._cancel_all_orders()
            await self.connector.stop()
            logger.info("MarketMaker stopped. Total PnL: $%.4f", self._realized_pnl)

    def stop(self) -> None:
        """Signal the main loop to stop."""
        logger.info("Stop requested")
        self._running = False


# ── Entry Point ────────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> None:
    fmt = "%(asctime)s %(name)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO),
                        format=fmt, datefmt="%H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="Limitless Market Making Bot")
    parser.add_argument("--paper", action="store_true", help="Force paper trading mode")
    parser.add_argument("--market", type=str, default=None, help="Override market slug")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG),
                        help="Path to config JSON")
    args = parser.parse_args()

    cfg = MMConfig(args.config)
    if args.paper:
        cfg.paper_mode = True

    setup_logging(cfg.log_level)

    connector = LimitlessConnector(
        markets=[args.market] if args.market else [],
        paper_mode=cfg.paper_mode,
        max_order_size_usd=cfg.max_order_size_usd,
    )

    mm = MarketMaker(connector, cfg)

    # Signal handling
    loop = asyncio.new_event_loop()

    def _shutdown(sig, _frame):
        logger.info("Received signal %s, shutting down...", sig)
        mm.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        loop.run_until_complete(mm.run(market_override=args.market))
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
