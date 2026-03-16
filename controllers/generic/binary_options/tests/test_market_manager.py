"""Tests for MarketManager — 3-layer market selection."""
import math
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from controllers.generic.binary_options.market_manager import MarketManager, _parse_title

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(dt: datetime) -> float:
    return dt.timestamp()


def _make_market(coin, strike, expiry_dt, slug=None, yes_price=0.50, volume=100, **kw):
    slug = slug or f"{coin.lower()}-{strike}-slug"
    return {
        "title": f"${coin} above ${strike} on Mar 16?",
        "type": "CLOB",
        "expiry": expiry_dt,
        "yes_price": yes_price,
        "no_price": 1.0 - yes_price,
        "slug": slug,
        "market_id": f"id-{slug}",
        "id": f"id-{slug}",
        "pyth_address": "0xabc",
        "max_spread": 0.035,
        "volume": volume,
        **kw,
    }


NOW_DT = datetime(2026, 3, 16, 19, 0, 0, tzinfo=timezone.utc)
NOW_TS = _ts(NOW_DT)
EXPIRY_1H = NOW_DT + timedelta(hours=1)
EXPIRY_2H = NOW_DT + timedelta(hours=2)
EXPIRY_SOON = NOW_DT + timedelta(minutes=3)  # 180s — within default close_secs=300


class MockConnector:
    def __init__(self, markets=None, order_books=None):
        self._markets = markets or []
        self._order_books = order_books or {}

    def get_active_markets(self):
        return self._markets

    def get_order_book(self, slug):
        return self._order_books.get(slug)


class MockRuntimeBridge:
    def __init__(self, overrides=None):
        self._ov = overrides or {}

    def get_coin_param(self, coin, key, default=None):
        return self._ov.get(key, default)


class MockRoster:
    def __init__(self, banned=None):
        self._banned = set(banned or [])

    def tier(self, coin):
        return "BANNED" if coin in self._banned else "MAIN"

    def size_multiplier(self, coin):
        return 0.0 if coin in self._banned else 1.0


# ---------------------------------------------------------------------------
# Tests: _parse_title
# ---------------------------------------------------------------------------

class TestParseTitle:
    def test_standard(self):
        assert _parse_title("$BTC above $84,000 on Mar 16?") == ("BTC", 84000.0)

    def test_no_comma(self):
        assert _parse_title("$SOL above $135.50 on Mar 16") == ("SOL", 135.50)

    def test_no_match(self):
        assert _parse_title("Some random market") is None


# ---------------------------------------------------------------------------
# Tests: discover
# ---------------------------------------------------------------------------

class TestDiscover:
    def _setup(self, markets, banned=None, rb_ov=None):
        conn = MockConnector(markets=markets)
        rb = MockRuntimeBridge(rb_ov or {})
        roster = MockRoster(banned=banned)
        config = MagicMock()
        mm = MarketManager(conn, config, roster, rb)
        return mm

    def test_basic_atm_selection(self):
        """Picks market closest to spot."""
        mkts = [
            _make_market("BTC", 83000, EXPIRY_1H, slug="btc-83k"),
            _make_market("BTC", 84000, EXPIRY_1H, slug="btc-84k"),
            _make_market("BTC", 86000, EXPIRY_1H, slug="btc-86k"),
        ]
        mm = self._setup(mkts)
        result = mm.discover({"BTC": 84100.0}, NOW_TS, force=True)
        assert "BTC" in result
        assert result["BTC"]["strike"] == 84000.0

    def test_fallback_yes_price(self):
        """Without spot, uses |yes_price - 0.50| for ATM."""
        mkts = [
            _make_market("ETH", 3000, EXPIRY_1H, slug="eth-3k", yes_price=0.70),
            _make_market("ETH", 3100, EXPIRY_1H, slug="eth-3.1k", yes_price=0.48),
        ]
        mm = self._setup(mkts)
        result = mm.discover({}, NOW_TS, force=True)
        assert result["ETH"]["slug"] == "eth-3.1k"  # closer to 0.50

    def test_tiebreak_earlier_expiry(self):
        """Equal ATM distance → earlier expiry wins."""
        mkts = [
            _make_market("SOL", 135, EXPIRY_2H, slug="sol-late"),
            _make_market("SOL", 135, EXPIRY_1H, slug="sol-early"),
        ]
        mm = self._setup(mkts)
        result = mm.discover({"SOL": 135.0}, NOW_TS, force=True)
        assert result["SOL"]["slug"] == "sol-early"

    def test_skip_banned(self):
        """BANNED coins are excluded."""
        mkts = [
            _make_market("BTC", 84000, EXPIRY_1H),
            _make_market("DOGE", 0.15, EXPIRY_1H),
        ]
        mm = self._setup(mkts, banned=["DOGE"])
        result = mm.discover({"BTC": 84000}, NOW_TS, force=True)
        assert "BTC" in result
        assert "DOGE" not in result

    def test_skip_expired(self):
        """Markets already expired are excluded."""
        past = NOW_DT - timedelta(hours=1)
        mkts = [_make_market("BTC", 84000, past)]
        mm = self._setup(mkts)
        result = mm.discover({"BTC": 84000}, NOW_TS, force=True)
        assert len(result) == 0

    def test_skip_amm(self):
        """AMM markets are excluded."""
        mkts = [_make_market("BTC", 84000, EXPIRY_1H, type="AMM")]
        mm = self._setup(mkts)
        result = mm.discover({"BTC": 84000}, NOW_TS, force=True)
        assert len(result) == 0

    def test_hourly_trigger(self):
        """Without force, re-discover only on hourly boundary."""
        mkts = [_make_market("BTC", 84000, EXPIRY_2H)]
        mm = self._setup(mkts)
        # First call always discovers (no locked markets)
        r1 = mm.discover({"BTC": 84000}, NOW_TS, force=False)
        assert "BTC" in r1
        # Same hour → returns cached
        r2 = mm.discover({"BTC": 84000}, NOW_TS + 30, force=False)
        assert r2 == r1
        # Next hour → re-discovers
        r3 = mm.discover({"BTC": 84000}, NOW_TS + 3600, force=False)
        assert "BTC" in r3


# ---------------------------------------------------------------------------
# Tests: evaluate
# ---------------------------------------------------------------------------

class TestEvaluate:
    def test_scoring_and_hysteresis(self):
        """New market must beat current by hysteresis margin to switch."""
        mkts = [
            _make_market("BTC", 84000, EXPIRY_1H, slug="btc-current"),
            _make_market("BTC", 84500, EXPIRY_1H, slug="btc-better"),
        ]
        obs = {
            "btc-current": {
                "bid": 0.50, "ask": 0.52,
                "bid_depth": 100, "ask_depth": 100,
                "bids_levels": [{"price": 0.50, "size": 100}],
                "asks_levels": [{"price": 0.52, "size": 100}],
            },
            "btc-better": {
                "bid": 0.50, "ask": 0.51,
                "bid_depth": 500, "ask_depth": 500,
                "bids_levels": [{"price": 0.50, "size": 500}],
                "asks_levels": [{"price": 0.51, "size": 500}],
            },
        }
        conn = MockConnector(markets=mkts, order_books=obs)
        rb = MockRuntimeBridge({"msel_eval_interval_s": 0, "msel_hysteresis_pct": 0.10,
                                 "msel_depth_weight": 0.5, "msel_atm_weight": 0.5})
        mm = MarketManager(conn, MagicMock(), MockRoster(), rb)

        # Seed locked markets via discover
        mm.discover({"BTC": 84000}, NOW_TS, force=True)
        assert mm._locked_markets["BTC"]["slug"] == "btc-current"

        # Evaluate — btc-better has much more depth, should switch
        result = mm.evaluate(NOW_TS + 1, force=True)
        assert result["BTC"]["slug"] == "btc-better"

    def test_hysteresis_blocks_marginal(self):
        """Marginal improvement blocked by hysteresis."""
        mkts = [
            _make_market("BTC", 84000, EXPIRY_1H, slug="btc-a"),
            _make_market("BTC", 84100, EXPIRY_1H, slug="btc-b"),
        ]
        # Nearly identical order books
        ob = {
            "bid": 0.50, "ask": 0.52,
            "bid_depth": 100, "ask_depth": 100,
            "bids_levels": [{"price": 0.50, "size": 100}],
            "asks_levels": [{"price": 0.52, "size": 100}],
        }
        conn = MockConnector(markets=mkts, order_books={"btc-a": ob, "btc-b": ob})
        rb = MockRuntimeBridge({"msel_eval_interval_s": 0, "msel_hysteresis_pct": 0.10,
                                 "msel_depth_weight": 0.5, "msel_atm_weight": 0.5})
        mm = MarketManager(conn, MagicMock(), MockRoster(), rb)
        mm.discover({"BTC": 84000}, NOW_TS, force=True)
        original = mm._locked_markets["BTC"]["slug"]

        mm.evaluate(NOW_TS + 1, force=True)
        # Should NOT switch — scores essentially equal
        assert mm._locked_markets["BTC"]["slug"] == original

    def test_drain_coins_skip_evaluate(self):
        """Draining coins are not switched."""
        mkts = [_make_market("BTC", 84000, EXPIRY_1H, slug="btc-a")]
        conn = MockConnector(markets=mkts)
        rb = MockRuntimeBridge({"msel_eval_interval_s": 0})
        mm = MarketManager(conn, MagicMock(), MockRoster(), rb)
        mm.discover({"BTC": 84000}, NOW_TS, force=True)
        mm._drain_coins.add("BTC")
        # Even with force, draining coins stay put
        mm.evaluate(NOW_TS + 1, force=True)
        assert "BTC" in mm._locked_markets


# ---------------------------------------------------------------------------
# Tests: build_market_data
# ---------------------------------------------------------------------------

class TestBuildMarketData:
    def test_returns_prices_from_connector(self):
        mkts = [_make_market("BTC", 84000, EXPIRY_1H, slug="btc-slug")]
        ob = {"bid": 0.52, "ask": 0.54, "bid_depth": 200, "ask_depth": 150}
        conn = MockConnector(markets=mkts, order_books={"btc-slug": ob})
        rb = MockRuntimeBridge()
        mm = MarketManager(conn, MagicMock(), MockRoster(), rb)
        mm.discover({"BTC": 84000}, NOW_TS, force=True)

        data = mm.build_market_data(NOW_TS)
        assert "BTC" in data
        assert data["BTC"]["bid"] == 0.52
        assert data["BTC"]["ask"] == 0.54
        assert data["BTC"]["bid_depth"] == 200

    def test_recycles_previous_on_missing(self):
        mkts = [_make_market("BTC", 84000, EXPIRY_1H, slug="btc-slug")]
        ob = {"bid": 0.52, "ask": 0.54, "bid_depth": 200, "ask_depth": 150}
        conn = MockConnector(markets=mkts, order_books={"btc-slug": ob})
        rb = MockRuntimeBridge()
        mm = MarketManager(conn, MagicMock(), MockRoster(), rb)
        mm.discover({"BTC": 84000}, NOW_TS, force=True)

        # First call populates cache
        mm.build_market_data(NOW_TS)

        # Remove order book — should recycle
        conn._order_books = {}
        data = mm.build_market_data(NOW_TS + 1)
        assert data["BTC"]["bid"] == 0.52  # recycled


# ---------------------------------------------------------------------------
# Tests: check_expiry
# ---------------------------------------------------------------------------

class TestCheckExpiry:
    def test_detects_expiring_with_positions(self):
        """Coins with active positions near expiry → drain set."""
        mkts = [_make_market("BTC", 84000, EXPIRY_SOON, slug="btc-soon")]
        conn = MockConnector(markets=mkts)
        rb = MockRuntimeBridge({"close_before_expiry_secs": 300})
        mm = MarketManager(conn, MagicMock(), MockRoster(), rb)
        mm.discover({"BTC": 84000}, NOW_TS, force=True)

        executor = MagicMock()
        executor.coin = "BTC"
        expiring = mm.check_expiry([executor], NOW_TS)
        assert "BTC" in expiring
        assert "BTC" in mm.drain_coins

    def test_removes_expired_markets(self):
        """Already-expired markets are removed from locked_markets."""
        past = NOW_DT - timedelta(seconds=1)
        mkts = [_make_market("BTC", 84000, EXPIRY_1H, slug="btc-ok")]
        conn = MockConnector(markets=mkts)
        rb = MockRuntimeBridge({"close_before_expiry_secs": 300})
        mm = MarketManager(conn, MagicMock(), MockRoster(), rb)
        # Manually inject an expired market
        mm._locked_markets["ETH"] = {
            "coin": "ETH", "slug": "eth-expired", "expiry": past,
            "strike": 3000, "yes_price": 0.5, "no_price": 0.5,
        }
        mm.check_expiry([], NOW_TS)
        assert "ETH" not in mm.locked_markets

    def test_no_drain_without_positions(self):
        """Near-expiry but no active positions → not added to drain."""
        mkts = [_make_market("BTC", 84000, EXPIRY_SOON, slug="btc-soon")]
        conn = MockConnector(markets=mkts)
        rb = MockRuntimeBridge({"close_before_expiry_secs": 300})
        mm = MarketManager(conn, MagicMock(), MockRoster(), rb)
        mm.discover({"BTC": 84000}, NOW_TS, force=True)

        expiring = mm.check_expiry([], NOW_TS)  # no executors
        assert len(expiring) == 0
