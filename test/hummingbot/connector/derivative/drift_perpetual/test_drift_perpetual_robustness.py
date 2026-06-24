"""
Defensive-parse contract tests for drift_perpetual.

A DEX-gateway connector that RAISES on an unexpected payload tears down
the order-book stream / funding poll / order flow. These tests pin the
hardened contract: malformed gateway JSON is skipped-and-logged, never
raised; and an unknown marketIndex fails the order cleanly instead of
POSTing {"marketIndex": null}. Happy-path equivalence is covered by the
existing per-module suites; this file only exercises the drift seams
([A1] book nesting, [A2] trades shape, funding, market-index map).
"""
import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

from bidict import bidict

from hummingbot.connector.derivative.drift_perpetual import drift_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.drift_perpetual.drift_perpetual_api_order_book_data_source import (
    DriftPerpetualAPIOrderBookDataSource as OBDS,
)
from hummingbot.connector.derivative.drift_perpetual.drift_perpetual_derivative import DriftPerpetualDerivative
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType


class DriftPerpetualOBDefensiveTests(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        super().setUp()
        self.connector = MagicMock()
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="SOL-PERP")
        self.ds = OBDS(trading_pairs=["SOL-PERP"], connector=self.connector, api_factory=MagicMock())

    def test_to_dec_returns_none_on_garbage(self):
        for bad in (None, "", "abc", "1,2", object()):
            self.assertIsNone(OBDS._to_dec(bad))
        self.assertEqual(Decimal("5"), OBDS._to_dec("5"))  # valid still works

    def test_scaled_helpers_none_on_garbage(self):
        self.assertIsNone(OBDS._scaled_price(None))
        self.assertIsNone(OBDS._scaled_size("xyz"))

    def test_levels_skips_malformed_entries_not_raise(self):
        entries = [
            {"price": 142_000_000, "size": 2_000_000_000},  # good
            {"price": 142_000_000},                          # missing size
            {"size": 1_000_000_000},                         # missing price
            {"price": "junk", "size": "junk"},               # non-numeric
            "not-a-dict",                                     # wrong type
            {"price": None, "size": None},                    # null
        ]
        out = OBDS._levels(entries)
        self.assertEqual([(Decimal("142"), Decimal("2"))], out)  # only the good one

    async def test_snapshot_with_unresolvable_market_is_skipped_not_raised(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(
            side_effect=Exception("unknown market"))
        q: asyncio.Queue = asyncio.Queue()
        # must NOT raise (would kill the book stream)
        await self.ds._parse_order_book_snapshot_message({"data": {"market": "???"}}, q)
        self.assertTrue(q.empty())

    async def test_snapshot_garbage_payload_no_raise(self):
        q: asyncio.Queue = asyncio.Queue()
        for raw in ({}, {"data": None}, {"data": "notadict"}, {"data": {"bids": "x", "asks": 5}}):
            await self.ds._parse_order_book_snapshot_message(raw, q)  # no exception

    async def test_trade_batch_one_bad_one_good(self):
        q: asyncio.Queue = asyncio.Queue()
        raw = {"data": {"market": "SOL-PERP", "trades": [
            {"ts": 1, "side": "buy", "price": 142_000_000, "size": 2_000_000_000},  # good
            {"ts": "bad", "side": "sell", "price": None, "size": None},             # bad -> skip
        ]}}
        await self.ds._parse_trade_message(raw, q)
        self.assertEqual(1, q.qsize())  # only the good trade survived
        self.assertEqual(Decimal("142"), q.get_nowait().content["price"])

    async def test_trade_non_list_payload_no_raise(self):
        q: asyncio.Queue = asyncio.Queue()
        await self.ds._parse_trade_message({"data": {"market": "SOL-PERP", "trades": "nope"}}, q)
        self.assertTrue(q.empty())

    def test_funding_non_numeric_coerces_zero_not_raise(self):
        self.assertEqual(Decimal("0"),
                         OBDS._funding_rate_from_record({"fundingRate": "x", "oraclePriceTwap": "y"}))
        info = self.ds._funding_info_from_record(
            "SOL-PERP", {"oraclePriceTwap": "junk", "markPriceTwap": None, "fundingRate": "z"})
        self.assertEqual(Decimal("0"), info.index_price)
        self.assertEqual(Decimal("0"), info.mark_price)


class DriftPerpetualPlaceOrderGuardTests(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        super().setUp()
        self.tp = combine_to_hb_trading_pair("SOL", CONSTANTS.CURRENCY)
        self.connector = DriftPerpetualDerivative(trading_pairs=[self.tp], trading_required=False)
        self.connector._set_trading_pair_symbol_map(bidict({"SOL-PERP": self.tp}))

    async def test_place_order_raises_when_market_index_unknown(self):
        # map intentionally empty -> must raise (clean FAIL), never POST null
        self.connector._market_index_map = {}
        self.connector._api_post = AsyncMock()
        with self.assertRaises(ValueError):
            await self.connector._place_order(
                order_id="HBOT-1", trading_pair=self.tp, amount=Decimal("1"),
                trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100"),
                position_action=PositionAction.OPEN,
            )
        self.connector._api_post.assert_not_called()  # no null-marketIndex POST

    async def test_place_order_market_index_zero_is_valid(self):
        # index 0 is a real Drift market — guard must use `is None`, not falsy
        self.connector._market_index_map = {self.tp: 0}
        self.connector._api_post = AsyncMock(return_value={"signature": "sig"})
        ex_id, _ = await self.connector._place_order(
            order_id="HBOT-2", trading_pair=self.tp, amount=Decimal("1"),
            trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100"),
            position_action=PositionAction.OPEN,
        )
        self.assertEqual("sig", ex_id)
        self.assertEqual(0, self.connector._api_post.call_args.kwargs["data"]["orders"][0]["marketIndex"])
