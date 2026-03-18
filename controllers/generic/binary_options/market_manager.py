"""Three-layer market selection for BinaryOptionsController."""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Title regex: "$TICKER above $STRIKE on DATE"
_TITLE_RE = re.compile(
    r"\$([A-Z]+)\s+above\s+\$([\d,.]+)\s+on\s+(.+?)(?:\s*\?)?$",
    re.IGNORECASE,
)

# Time formats for parsing expiry from title (same as limitless_client.py)
_TIME_FMTS = ["%b %d, %H:%M UTC", "%b %d, %Y, %H:%M UTC", "%b %d, %Y"]


def _parse_time(s: str) -> Optional[datetime]:
    """Parse expiry datetime from title date string (e.g. 'Mar 16, 23:00 UTC')."""
    now = datetime.now(timezone.utc)
    for fmt in _TIME_FMTS:
        try:
            dt = datetime.strptime(s.strip(), fmt)
            if dt.year == 1900:
                dt = dt.replace(year=now.year)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_title(title: str) -> Optional[Tuple[str, float, Optional[datetime]]]:
    """Extract (ticker, strike_float, expiry_dt) from market title, or None."""
    m = _TITLE_RE.search(title)
    if not m:
        return None
    ticker = m.group(1).upper()
    strike_str = m.group(2).replace(",", "")
    try:
        strike = float(strike_str)
    except ValueError:
        return None
    expiry_dt = _parse_time(m.group(3).strip())
    return ticker, strike, expiry_dt


def _normalize_prob(value: Any) -> Optional[float]:
    """Convert venue/API prices into 0..1 fractions when possible."""
    if value is None:
        return None
    try:
        prob = float(value)
    except (TypeError, ValueError):
        return None
    if prob > 1.0:
        prob /= 100.0
    return prob


def _normalize_api_midpoint(value: Any) -> Optional[float]:
    """Venue midpoint is already fractional; values outside 0..1 are invalid."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_valid_prob(value: Optional[float]) -> bool:
    return value is not None and 0.0 < value < 1.0


def _build_price_surface(
    yes_bid: Optional[float],
    yes_ask: Optional[float],
    yes_mid: Optional[float],
) -> Dict[str, Optional[float] | bool]:
    no_bid = (1.0 - yes_ask) if _is_valid_prob(yes_ask) else None
    no_ask = (1.0 - yes_bid) if _is_valid_prob(yes_bid) else None
    no_mid = (1.0 - yes_mid) if yes_mid is not None else None
    quote_valid = yes_mid is not None
    return {
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "yes_mid": yes_mid,
        "no_bid": no_bid,
        "no_ask": no_ask,
        "no_mid": no_mid,
        "quote_valid": quote_valid,
    }


class MarketManager:
    """Wraps 3-layer market selection using the Hummingbot connector."""

    def __init__(
        self,
        connector,
        config,
        roster,
        runtime_bridge,
        exposure_guard: Optional[Callable[[str], bool]] = None,
        switch_policy: str = "flat_only",
    ):
        """
        connector:      Hummingbot connector (get_active_markets, get_order_book, etc.)
        config:         BinaryOptionsControllerConfig
        roster:         CoinRoster
        runtime_bridge: RuntimeBridge
        """
        self._connector = connector
        self._config = config
        self._roster = roster
        self._rb = runtime_bridge
        self._exposure_guard = exposure_guard
        self._switch_policy = switch_policy
        self._locked_markets: Dict[str, dict] = {}
        self._last_discover_ts: float = 0.0
        self._last_evaluate_ts: float = 0.0
        self._drain_coins: Set[str] = set()
        self._prev_market_data: Dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def locked_markets(self) -> Dict[str, dict]:
        return dict(self._locked_markets)

    @property
    def drain_coins(self) -> Set[str]:
        return set(self._drain_coins)

    # ------------------------------------------------------------------
    # Layer 1: discover
    # ------------------------------------------------------------------

    async def discover(self, spots: Dict[str, float], now_ts: float, force: bool = False) -> Dict[str, dict]:
        """Market discovery + ATM selection per coin.

        Args:
            spots: {coin: spot_price} e.g. {"BTC": 84000.0}
            now_ts: current unix timestamp
            force: bypass timing checks

        Returns:
            {coin: market_dict} of selected markets
        """
        # Trigger conditions: no locked markets, hourly boundary, or force
        if not force and self._locked_markets:
            # Check hourly boundary: different hour than last discover
            last_hour = int(self._last_discover_ts // 3600)
            cur_hour = int(now_ts // 3600)
            if last_hour == cur_hour:
                return dict(self._locked_markets)

        self._last_discover_ts = now_ts

        # Fetch all active markets from connector
        raw_markets = await self._connector.get_active_markets()
        if not raw_markets:
            logger.warning("discover: connector returned no active markets")
            return dict(self._locked_markets)

        now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
        include_subhourly = bool(getattr(self._config, 'include_subhourly', False))

        # Collect candidates per ticker
        candidates: Dict[str, list] = {}  # {ticker: [market_dict, ...]}

        logger.info("discover: processing %d raw markets", len(raw_markets) if raw_markets else 0)
        for mkt in raw_markets:
            title = mkt.get("title", "")
            parsed = _parse_title(title)
            if not parsed:
                logger.debug("discover: skipping unparseable title: %s", title[:50])
                continue
            ticker, strike, title_expiry = parsed
            logger.debug("discover: parsed %s strike=%s expiry=%s", ticker, strike, title_expiry)

            # Coin whitelist filter (from YAML config)
            coin_whitelist = getattr(self._config, 'coins', [])
            if coin_whitelist and ticker not in coin_whitelist:
                continue

            # Skip BANNED coins
            if self._roster.tier(ticker) == "BANNED":
                continue

            # CLOB only — check tradeType (SDK field) or trade_type
            trade_type = mkt.get("tradeType", mkt.get("trade_type", "clob"))
            if trade_type and trade_type.lower() != "clob":
                continue

            # Expiry: prefer parsed from title (has exact time), fall back to API field
            expiry_dt = title_expiry
            if not expiry_dt:
                expiry = mkt.get("expiry") or mkt.get("expiration_date")
                if isinstance(expiry, (int, float)):
                    expiry_dt = datetime.fromtimestamp(expiry, tz=timezone.utc)
                elif isinstance(expiry, datetime):
                    expiry_dt = expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc)
                elif isinstance(expiry, str):
                    expiry_dt = _parse_time(expiry)
            if not expiry_dt:
                logger.debug("discover: no valid expiry for %s", title[:50])
                continue

            # Must not be expired
            if expiry_dt <= now_dt:
                continue

            # Timeframe filter: hourly-only unless include_subhourly is enabled
            if not include_subhourly and expiry_dt.minute != 0:
                continue

            # Configurable look-ahead from YAML config
            hours_until = (expiry_dt - now_dt).total_seconds() / 3600
            max_expiry_h = getattr(self._config, 'max_expiry_hours', 1.0)
            if hours_until > max_expiry_h:
                continue

            # Extract yes/no prices — handle both list and dict format
            prices = mkt.get("prices", [])
            if isinstance(prices, list) and len(prices) >= 2:
                yes_price = float(prices[0])
                no_price = float(prices[1])
            elif isinstance(prices, dict):
                yes_price = float(prices.get("yes", 0.5))
                no_price = float(prices.get("no", 0.5))
            else:
                yes_price = float(mkt.get("yes_price", 0.5))
                no_price = float(mkt.get("no_price", 0.5))
            # Normalize if prices are in cents (>2.0 sum)
            if yes_price + no_price > 2.0:
                yes_price /= 100.0
                no_price /= 100.0

            market_dict = {
                "coin": ticker,
                "yes_price": yes_price,
                "no_price": no_price,
                "strike": strike,
                "slug": mkt.get("slug", ""),
                "market_id": mkt.get("market_id", mkt.get("id", "")),
                "title": title,
                "expiry": expiry_dt,
                "pyth_address": mkt.get("pyth_address", ""),
                "max_spread": float(mkt.get("max_spread", 0.035)),
                "volume": float(mkt.get("volume", 0)),
            }

            candidates.setdefault(ticker, []).append(market_dict)

        # ATM selection per ticker
        selected: Dict[str, dict] = {}
        for ticker, mkts in candidates.items():
            spot = spots.get(ticker)
            best = None
            best_dist = float("inf")
            best_expiry = None

            for md in mkts:
                if spot and spot > 0:
                    dist = abs(spot - md["strike"]) / spot
                else:
                    dist = abs(md["yes_price"] - 0.50)

                expiry_dt = md["expiry"]

                # Pick closest; tie-break by earlier expiry
                if (dist < best_dist) or (
                    math.isclose(dist, best_dist, abs_tol=1e-9) and
                    best_expiry is not None and expiry_dt < best_expiry
                ):
                    best = md
                    best_dist = dist
                    best_expiry = expiry_dt

            if best:
                selected[ticker] = best

        self._locked_markets = selected
        logger.info("discover: selected %d markets: %s", len(selected), list(selected.keys()))
        return dict(self._locked_markets)

    # ------------------------------------------------------------------
    # Layer 2: evaluate
    # ------------------------------------------------------------------

    async def evaluate(self, now_ts: float, force: bool = False) -> Dict[str, dict]:
        """WS-based scoring for market switching within a ticker.

        Only runs every msel_eval_interval_s. Hysteresis prevents frivolous switching.
        Pinned (open position) and draining coins never switch.
        """
        interval = float(self._rb.get_coin_param("_global", "msel_eval_interval_s", 60.0))
        if not force and (now_ts - self._last_evaluate_ts) < interval:
            return dict(self._locked_markets)

        self._last_evaluate_ts = now_ts

        depth_weight = float(self._rb.get_coin_param("_global", "msel_depth_weight", 0.5))
        atm_weight = float(self._rb.get_coin_param("_global", "msel_atm_weight", 0.5))
        volume_weight = float(self._rb.get_coin_param("_global", "msel_volume_weight", 0.0))
        hysteresis = float(self._rb.get_coin_param("_global", "msel_hysteresis_pct", 0.10))

        # Get all active markets for re-scoring
        raw_markets = await self._connector.get_active_markets()
        if not raw_markets:
            return dict(self._locked_markets)

        now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
        include_subhourly = bool(getattr(self._config, 'include_subhourly', False))

        # Group valid candidates by ticker
        ticker_candidates: Dict[str, list] = {}
        for mkt in raw_markets:
            parsed = _parse_title(mkt.get("title", ""))
            if not parsed:
                continue
            ticker, strike, _ = parsed
            if self._roster.tier(ticker) == "BANNED":
                continue
            if ticker not in self._locked_markets:
                continue  # only evaluate tickers we already track

            # Use title-parsed expiry (has exact time)
            title = mkt.get("title", "")
            title_parsed = _parse_title(title)
            if title_parsed:
                _, _, title_expiry = title_parsed
                expiry_dt = title_expiry
            else:
                expiry_dt = None
            if not expiry_dt:
                expiry = mkt.get("expiry") or mkt.get("expiration_date")
                if isinstance(expiry, (int, float)):
                    expiry_dt = datetime.fromtimestamp(expiry, tz=timezone.utc)
                elif isinstance(expiry, datetime):
                    expiry_dt = expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc)
                elif isinstance(expiry, str):
                    expiry_dt = _parse_time(expiry)
            if not expiry_dt or expiry_dt <= now_dt:
                continue

            # Timeframe filter: hourly-only unless include_subhourly is enabled
            if not include_subhourly and expiry_dt.minute != 0:
                continue

            # Extract prices from list or dict
            prices = mkt.get("prices", [])
            if isinstance(prices, list) and len(prices) >= 2:
                yes_p = float(prices[0])
                no_p = float(prices[1])
            elif isinstance(prices, dict):
                yes_p = float(prices.get("yes", 0.5))
                no_p = float(prices.get("no", 0.5))
            else:
                yes_p = float(mkt.get("yes_price", 0.5))
                no_p = float(mkt.get("no_price", 0.5))
            if yes_p + no_p > 2.0:
                yes_p /= 100.0
                no_p /= 100.0

            slug = mkt.get("slug", "")
            ticker_candidates.setdefault(ticker, []).append({
                "slug": slug,
                "market_id": mkt.get("market_id", mkt.get("id", "")),
                "title": title,
                "strike": strike,
                "coin": ticker,
                "expiry": expiry_dt,
                "yes_price": yes_p,
                "no_price": no_p,
                "pyth_address": mkt.get("pyth_address", ""),
                "max_spread": float(mkt.get("max_spread", 0.035)),
                "volume": float(mkt.get("volume", 0)),
            })

        async def _score(md: dict) -> float:
            """Collect score inputs for normalized depth, ATM proximity, and volume."""
            slug = md.get("slug", "")
            ob = await self._connector.get_order_book_data(slug)
            near_depth = 0.0
            if ob:
                bids = ob.get("bids", [])
                asks = ob.get("asks", [])
                best_bid = float(bids[0]["price"]) if bids else 0.5
                best_ask = float(asks[0]["price"]) if asks else 0.5
                if best_bid > 1.0:
                    best_bid /= 100.0
                if best_ask > 1.0:
                    best_ask /= 100.0
                mid = (best_bid + best_ask) / 2.0
                # Depth within 0.30 of mid
                for levels in (bids, asks):
                    for level in levels:
                        price = float(level.get("price", 0))
                        if price > 1.0:
                            price /= 100.0
                        if abs(price - mid) <= 0.30:
                            near_depth += float(level.get("size", 0))
                md["_bid"] = best_bid
            else:
                md["_bid"] = md.get("yes_price", 0.5)

            atm_proximity = 1.0 - abs(md.get("_bid", 0.5) - 0.50)
            # Normalized: we use raw values; normalization across candidates
            md["_near_depth"] = near_depth
            md["_atm_proximity"] = atm_proximity
            md["_volume"] = float(md.get("volume", 0.0) or 0.0)
            return near_depth, atm_proximity, md["_volume"]

        switches = {}
        for ticker, cands in ticker_candidates.items():
            # Skip pinned (draining) coins
            if ticker in self._drain_coins:
                continue

            # Score all candidates
            for c in cands:
                await _score(c)

            # Normalize
            max_depth = max((c["_near_depth"] for c in cands), default=1.0) or 1.0
            max_atm = max((c["_atm_proximity"] for c in cands), default=1.0) or 1.0
            max_volume = max((c["_volume"] for c in cands), default=0.0) or 1.0

            def full_score(c):
                return (
                    depth_weight * (c["_near_depth"] / max_depth) +
                    atm_weight * (c["_atm_proximity"] / max_atm) +
                    volume_weight * (c["_volume"] / max_volume)
                )

            current_slug = self._locked_markets[ticker].get("slug")
            current_score = 0.0
            best_cand = None
            best_score = -1.0

            for c in cands:
                s = full_score(c)
                if c["slug"] == current_slug:
                    current_score = s
                if s > best_score:
                    best_score = s
                    best_cand = c

            if best_cand and best_cand["slug"] != current_slug:
                if best_score > current_score * (1.0 + hysteresis):
                    if (
                        self._switch_policy == "flat_only"
                        and self._exposure_guard is not None
                        and self._exposure_guard(ticker)
                    ):
                        logger.info(
                            "evaluate: retained %s on %s due to flat_only exposure gate",
                            ticker,
                            current_slug,
                        )
                        continue
                    # Switch
                    new_md = {k: v for k, v in best_cand.items() if not k.startswith("_")}
                    self._locked_markets[ticker] = new_md
                    switches[ticker] = new_md
                    logger.info(
                        "evaluate: switched %s from %s to %s (%.3f > %.3f × %.2f)",
                        ticker, current_slug, best_cand["slug"],
                        best_score, current_score, 1.0 + hysteresis,
                    )

        return dict(self._locked_markets)

    # ------------------------------------------------------------------
    # Layer 3: build_market_data
    # ------------------------------------------------------------------

    async def build_market_data(self, now_ts: float) -> Dict[str, dict]:
        """Per-tick price refresh from connector order books.

        Returns {coin: {yes_price, no_price, bid, ask, bid_depth, ask_depth,
                        strike, slug, expiry, ...}}
        Recycles previous data if connector is unavailable.
        """
        result: Dict[str, dict] = {}

        for coin, md in self._locked_markets.items():
            slug = md.get("slug", "")
            ob = await self._connector.get_order_book_data(slug)
            expiry = md.get("expiry")
            expiry_ts = expiry.timestamp() if isinstance(expiry, datetime) else None

            if ob:
                bids = ob.get("bids") or ob.get("bids_levels") or []
                asks = ob.get("asks") or ob.get("asks_levels") or []
                best_bid = _normalize_prob(bids[0].get("price")) if bids else _normalize_prob(ob.get("bid"))
                best_ask = _normalize_prob(asks[0].get("price")) if asks else _normalize_prob(ob.get("ask"))
                bid_depth = sum(float(b.get("size", 0)) for b in bids) if bids else float(ob.get("bid_depth", 0.0) or 0.0)
                ask_depth = sum(float(a.get("size", 0)) for a in asks) if asks else float(ob.get("ask_depth", 0.0) or 0.0)

                yes_mid_api = _normalize_api_midpoint(ob.get("adjustedMidpoint"))
                if not _is_valid_prob(yes_mid_api):
                    yes_mid_api = None

                local_mid_valid = (
                    _is_valid_prob(best_bid)
                    and _is_valid_prob(best_ask)
                    and best_bid < best_ask
                )
                yes_mid_local = ((best_bid + best_ask) / 2.0) if local_mid_valid else None
                yes_mid = yes_mid_api if yes_mid_api is not None else yes_mid_local
                price_surface = _build_price_surface(best_bid, best_ask, yes_mid)

                entry = {
                    "coin": coin,
                    "yes_price": best_bid if best_bid > 0 else md.get("yes_price", 0.5),
                    "no_price": 1.0 - best_bid if best_bid > 0 else md.get("no_price", 0.5),
                    "bid": best_bid or 0.0,
                    "ask": best_ask or 0.0,
                    "yes_bid": price_surface["yes_bid"],
                    "yes_ask": price_surface["yes_ask"],
                    "yes_mid_local": yes_mid_local,
                    "yes_mid_api": yes_mid_api,
                    "yes_mid": price_surface["yes_mid"],
                    "no_bid": price_surface["no_bid"],
                    "no_ask": price_surface["no_ask"],
                    "no_mid": price_surface["no_mid"],
                    "quote_valid": price_surface["quote_valid"],
                    "price_surface": price_surface,
                    "bid_depth": bid_depth,
                    "ask_depth": ask_depth,
                    "strike": md.get("strike", 0.0),
                    "slug": slug,
                    "expiry": expiry,
                    "expiry_ts": expiry_ts,
                    "market_id": md.get("market_id", ""),
                    "pyth_address": md.get("pyth_address", ""),
                    "max_spread": md.get("max_spread", 0.035),
                    "volume": md.get("volume", 0),
                }
                result[coin] = entry
                self._prev_market_data[coin] = entry
            elif coin in self._prev_market_data:
                # Recycle non-trading fields, but invalidate midpoint-derived MM inputs.
                prev = dict(self._prev_market_data[coin])
                prev_surface = _build_price_surface(prev.get("yes_bid"), prev.get("yes_ask"), None)
                prev.update({
                    "yes_mid_local": None,
                    "yes_mid_api": None,
                    "yes_mid": prev_surface["yes_mid"],
                    "no_mid": prev_surface["no_mid"],
                    "quote_valid": prev_surface["quote_valid"],
                    "price_surface": prev_surface,
                })
                result[coin] = prev
            else:
                # Static fallback preserves compatibility fields only; midpoint remains invalid.
                price_surface = _build_price_surface(None, None, None)
                result[coin] = {
                    "coin": coin,
                    "yes_price": md.get("yes_price", 0.5),
                    "no_price": md.get("no_price", 0.5),
                    "bid": md.get("yes_price", 0.5),
                    "ask": md.get("yes_price", 0.5),
                    "yes_bid": price_surface["yes_bid"],
                    "yes_ask": price_surface["yes_ask"],
                    "yes_mid_local": None,
                    "yes_mid_api": None,
                    "yes_mid": price_surface["yes_mid"],
                    "no_bid": price_surface["no_bid"],
                    "no_ask": price_surface["no_ask"],
                    "no_mid": price_surface["no_mid"],
                    "quote_valid": price_surface["quote_valid"],
                    "price_surface": price_surface,
                    "bid_depth": 0.0,
                    "ask_depth": 0.0,
                    "strike": md.get("strike", 0.0),
                    "slug": slug,
                    "expiry": expiry,
                    "expiry_ts": expiry_ts,
                    "market_id": md.get("market_id", ""),
                    "pyth_address": md.get("pyth_address", ""),
                    "max_spread": md.get("max_spread", 0.035),
                    "volume": md.get("volume", 0),
                }

        return result

    # ------------------------------------------------------------------
    # Expiry management
    # ------------------------------------------------------------------

    def check_expiry(self, active_executors: list, now_ts: float) -> Set[str]:
        """Check for expiring markets; manage drain mode.

        Args:
            active_executors: list of executor objects with .trading_pair or coin attribute
            now_ts: current unix timestamp

        Returns:
            Set of coins that are expiring (added to drain)
        """
        close_secs = float(self._rb.get_coin_param("_global", "close_before_expiry_secs", 300.0))
        now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
        expiring: Set[str] = set()
        expired_coins: list = []

        # Coins with active positions
        active_coins: Set[str] = set()
        for ex in active_executors:
            coin = getattr(ex, "coin", None) or getattr(ex, "trading_pair", "").split("-")[0]
            if coin:
                active_coins.add(coin.upper())

        for coin, md in list(self._locked_markets.items()):
            expiry_dt = md.get("expiry")
            if not isinstance(expiry_dt, datetime):
                continue

            secs_left = (expiry_dt - now_dt).total_seconds()

            if secs_left <= 0:
                # Already expired
                expired_coins.append(coin)
                self._drain_coins.discard(coin)
                continue

            if secs_left <= close_secs and coin in active_coins:
                self._drain_coins.add(coin)
                expiring.add(coin)

        # Remove expired markets
        for coin in expired_coins:
            del self._locked_markets[coin]
            logger.info("check_expiry: removed expired market for %s", coin)

        return expiring
