import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.drift_perpetual import drift_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.drift_perpetual.drift_perpetual_api_order_book_data_source import (
    DriftPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class DriftPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.trading_pair = "SOL-PERP"
        cls.ex_symbol = "SOL-PERP"

    def setUp(self) -> None:
        super().setUp()
        self.connector = MagicMock()
        # Drift uses identity pair<->symbol mapping for *-PERP markets.
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_symbol)
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        self.data_source = DriftPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=MagicMock(),
        )

    # --- precision scaling (driftpy-verified; #1 connector bug class) ---

    def test_scaled_price_uses_1e6_precision(self):
        # 142.5 USDC -> 142_500_000 on-chain at PRICE_PRECISION 1e6
        self.assertEqual(Decimal("142.5"), DriftPerpetualAPIOrderBookDataSource._scaled_price(142_500_000))
        self.assertEqual(Decimal(CONSTANTS.PRICE_PRECISION), Decimal(1_000_000))

    def test_scaled_size_uses_1e9_precision(self):
        # 3.25 SOL -> 3_250_000_000 on-chain at BASE_PRECISION 1e9
        self.assertEqual(Decimal("3.25"), DriftPerpetualAPIOrderBookDataSource._scaled_size(3_250_000_000))
        self.assertEqual(Decimal(CONSTANTS.BASE_PRECISION), Decimal(1_000_000_000))

    def test_scaling_accepts_string_input_without_float_error(self):
        # DLOB sends ints, but be robust to stringified bigints (no binary
        # float contamination — Decimal(str(raw)) is exact).
        self.assertEqual(Decimal("0.000001"), DriftPerpetualAPIOrderBookDataSource._scaled_price("1"))
        self.assertEqual(Decimal("0.000000001"), DriftPerpetualAPIOrderBookDataSource._scaled_size("1"))

    def test_levels_maps_entries_to_price_size_tuples(self):
        entries = [{"price": 142_500_000, "size": 3_250_000_000},
                   {"price": 142_400_000, "size": 1_000_000_000}]
        self.assertEqual(
            [(Decimal("142.5"), Decimal("3.25")), (Decimal("142.4"), Decimal("1"))],
            DriftPerpetualAPIOrderBookDataSource._levels(entries),
        )

    def test_levels_handles_empty_and_none(self):
        self.assertEqual([], DriftPerpetualAPIOrderBookDataSource._levels([]))
        self.assertEqual([], DriftPerpetualAPIOrderBookDataSource._levels(None))

    def test_get_bids_and_asks_splits_book_and_tolerates_missing_side(self):
        book = {"bids": [{"price": 142_000_000, "size": 2_000_000_000}], "asks": []}
        bids, asks = self.data_source._get_bids_and_asks(book)
        self.assertEqual([(Decimal("142"), Decimal("2"))], bids)
        self.assertEqual([], asks)
        # entirely-empty book must not raise
        self.assertEqual(([], []), self.data_source._get_bids_and_asks({}))

    # --- channel routing ---

    def test_channel_originating_message_routes_to_correct_queue(self):
        self.assertEqual(
            self.data_source._snapshot_messages_queue_key,
            self.data_source._channel_originating_message({"channel": CONSTANTS.WS_DLOB_CHANNEL_ORDERBOOK}),
        )
        self.assertEqual(
            self.data_source._trade_messages_queue_key,
            self.data_source._channel_originating_message({"channel": CONSTANTS.WS_DLOB_CHANNEL_TRADES}),
        )
        # unknown / heartbeat envelopes ignored
        self.assertEqual("", self.data_source._channel_originating_message({"channel": "heartbeat"}))
        self.assertEqual("", self.data_source._channel_originating_message({}))

    # --- funding maths ---

    def test_funding_rate_is_fraction_of_oracle_twap(self):
        rate = DriftPerpetualAPIOrderBookDataSource._funding_rate_from_record(
            {"fundingRate": "0.05", "oraclePriceTwap": "100"}
        )
        self.assertEqual(Decimal("0.0005"), rate)

    def test_funding_rate_divide_by_zero_guarded(self):
        rate = DriftPerpetualAPIOrderBookDataSource._funding_rate_from_record(
            {"fundingRate": "0.05", "oraclePriceTwap": "0"}
        )
        self.assertEqual(Decimal("0"), rate)
        # missing keys also guarded
        self.assertEqual(Decimal("0"), DriftPerpetualAPIOrderBookDataSource._funding_rate_from_record({}))

    @patch("hummingbot.connector.derivative.drift_perpetual."
           "drift_perpetual_api_order_book_data_source.time.time", return_value=1_715_770_000.0)
    def test_next_funding_time_is_next_hour_boundary(self, _mock_time):
        nxt = DriftPerpetualAPIOrderBookDataSource._next_funding_time()
        self.assertEqual(0, nxt % 3600)
        self.assertGreater(nxt, 1_715_770_000.0)
        self.assertLessEqual(nxt - 1_715_770_000.0, 3600)

    def test_funding_info_from_record_maps_fields(self):
        info = self.data_source._funding_info_from_record(
            self.trading_pair,
            {"oraclePriceTwap": "142.0", "markPriceTwap": "142.3", "fundingRate": "1.42", "oraclePriceTwap2": "x"},
        )
        self.assertIsInstance(info, FundingInfo)
        self.assertEqual(self.trading_pair, info.trading_pair)
        self.assertEqual(Decimal("142.0"), info.index_price)
        self.assertEqual(Decimal("142.3"), info.mark_price)
        self.assertEqual(Decimal("1.42") / Decimal("142.0"), info.rate)

    # --- async snapshot / trade parsing ---

    async def test_parse_order_book_snapshot_message_emits_scaled_snapshot(self):
        queue: asyncio.Queue = asyncio.Queue()
        raw = {"channel": CONSTANTS.WS_DLOB_CHANNEL_ORDERBOOK, "data": {
            "market": self.ex_symbol, "slot": 987654,
            "bids": [{"price": 142_000_000, "size": 5_000_000_000}],
            "asks": [{"price": 142_100_000, "size": 4_000_000_000}],
        }}
        await self.data_source._parse_order_book_snapshot_message(raw, queue)
        msg = queue.get_nowait()
        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(987654, msg.content["update_id"])  # slot is the seq
        self.assertEqual([(Decimal("142"), Decimal("5"))], msg.content["bids"])
        self.assertEqual([(Decimal("142.1"), Decimal("4"))], msg.content["asks"])

    async def test_parse_order_book_snapshot_falls_back_to_nonce_without_slot(self):
        queue: asyncio.Queue = asyncio.Queue()
        raw = {"data": {"market": self.ex_symbol, "bids": [], "asks": []}}
        await self.data_source._parse_order_book_snapshot_message(raw, queue)
        msg = queue.get_nowait()
        # no slot -> a monotonic nonce update_id is synthesized (non-zero)
        self.assertGreater(msg.content["update_id"], 0)

    async def test_parse_trade_message_classifies_side_and_scales(self):
        queue: asyncio.Queue = asyncio.Queue()
        raw = {"channel": CONSTANTS.WS_DLOB_CHANNEL_TRADES, "data": {"market": self.ex_symbol, "trades": [
            {"ts": 1_715_770_111, "side": "buy", "price": 142_000_000, "size": 2_000_000_000},
            {"ts": 1_715_770_112, "side": "sell", "price": 142_050_000, "size": 1_500_000_000},
        ]}}
        await self.data_source._parse_trade_message(raw, queue)
        first = queue.get_nowait()
        second = queue.get_nowait()
        self.assertEqual(OrderBookMessageType.TRADE, first.type)
        self.assertEqual(Decimal("142"), first.content["price"])
        self.assertEqual(Decimal("2"), first.content["amount"])
        # buy vs sell map to distinct trade_type codes
        self.assertNotEqual(first.content["trade_type"], second.content["trade_type"])

    async def test_parse_order_book_diff_is_noop(self):
        # Drift DLOB is snapshot-only; the diff hook must never enqueue.
        queue: asyncio.Queue = asyncio.Queue()
        await self.data_source._parse_order_book_diff_message({"data": {}}, queue)
        self.assertTrue(queue.empty())
