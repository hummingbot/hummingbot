import asyncio
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.limitless.limitless_exchange import LimitlessExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow


class TestLimitlessExchange(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.ev_loop.close()
        asyncio.set_event_loop(None)
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.exchange = LimitlessExchange(trading_pairs=["ETH-USDC", "ETHNO-USDC"])
        self.exchange._slug_map = {
            "ETH-USDC": "eth-market",
            "ETHNO-USDC": "eth-market",
        }
        self.exchange._trading_rules = {
            "ETH-USDC": TradingRule(
                trading_pair="ETH-USDC",
                min_order_size=Decimal("0.01"),
                min_base_amount_increment=Decimal("0.01"),
                min_price_increment=Decimal("0.01"),
                min_order_value=Decimal("0.01"),
            ),
            "ETHNO-USDC": TradingRule(
                trading_pair="ETHNO-USDC",
                min_order_size=Decimal("0.01"),
                min_base_amount_increment=Decimal("0.01"),
                min_price_increment=Decimal("0.01"),
                min_order_value=Decimal("0.01"),
            ),
        }

        yes_order_book = OrderBook()
        yes_order_book.apply_snapshot(
            bids=[OrderBookRow(0.42, 7, 11), OrderBookRow(0.40, 5, 10)],
            asks=[OrderBookRow(0.58, 6, 12), OrderBookRow(0.60, 9, 9)],
            update_id=12,
        )
        yes_order_book.last_trade_price = 0.55
        self.exchange._set_order_book_tracker(
            SimpleNamespace(
                order_books={
                    "ETH-USDC": yes_order_book,
                }
            )
        )

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_get_order_book_flips_no_pair(self):
        no_order_book = self.exchange.get_order_book("ETHNO-USDC")
        bid_entries = list(no_order_book.bid_entries())
        ask_entries = list(no_order_book.ask_entries())

        self.assertEqual(2, len(bid_entries))
        self.assertAlmostEqual(0.42, bid_entries[0].price)
        self.assertEqual(6.0, bid_entries[0].amount)
        self.assertEqual(12, bid_entries[0].update_id)
        self.assertAlmostEqual(0.40, bid_entries[1].price)
        self.assertEqual(9.0, bid_entries[1].amount)
        self.assertEqual(9, bid_entries[1].update_id)

        self.assertEqual(2, len(ask_entries))
        self.assertAlmostEqual(0.58, ask_entries[0].price)
        self.assertEqual(7.0, ask_entries[0].amount)
        self.assertEqual(11, ask_entries[0].update_id)
        self.assertAlmostEqual(0.60, ask_entries[1].price)
        self.assertEqual(5.0, ask_entries[1].amount)
        self.assertEqual(10, ask_entries[1].update_id)

        self.assertAlmostEqual(0.45, no_order_book.last_trade_price)

    def test_get_price_flips_no_pair(self):
        self.assertEqual(Decimal("0.58"), self.exchange.get_price("ETHNO-USDC", True))
        self.assertEqual(Decimal("0.42"), self.exchange.get_price("ETHNO-USDC", False))

    def test_place_order_routes_sell_to_inner_sell(self):
        self.exchange._inner_started = True
        self.exchange._inner_connector = SimpleNamespace(
            buy=AsyncMock(return_value={"order_id": "buy-id"}),
            sell=AsyncMock(return_value={"order_id": "sell-id"}),
        )

        exchange_order_id, _ = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="client-id",
                trading_pair="ETHNO-USDC",
                amount=Decimal("3"),
                trade_type=TradeType.SELL,
                order_type=None,
                price=Decimal("0.61"),
            )
        )

        self.assertEqual("sell-id", exchange_order_id)
        self.exchange._inner_connector.sell.assert_awaited_once_with(
            market_slug="eth-market",
            price=0.61,
            size=3.0,
            order_type="GTC",
            token="NO",
        )
        self.exchange._inner_connector.buy.assert_not_awaited()

    def test_paper_mode_setter_updates_inner_connector(self):
        self.exchange._inner_connector = SimpleNamespace(_paper_mode=False)

        self.exchange.paper_mode = True

        self.assertTrue(self.exchange.paper_mode)
        self.assertTrue(self.exchange._inner_connector._paper_mode)

    def test_update_balances_uses_synthetic_usdc_in_paper_mode(self):
        self.exchange.paper_mode = True
        self.exchange._inner_started = True
        self.exchange._inner_connector = SimpleNamespace(get_balance=AsyncMock(side_effect=AssertionError("should not fetch")))
        self.exchange._account_balances["BTC"] = Decimal("1")
        self.exchange._account_available_balances["BTC"] = Decimal("1")
        self.exchange.logger = MagicMock(return_value=MagicMock(info=MagicMock()))

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertEqual(Decimal("1000000"), self.exchange._account_balances["USDC"])
        self.assertEqual(Decimal("1000000"), self.exchange._account_available_balances["USDC"])
        self.assertNotIn("BTC", self.exchange._account_balances)
        self.exchange._inner_connector.get_balance.assert_not_awaited()

    def test_update_balances_fetches_connector_balance_in_live_mode(self):
        self.exchange.paper_mode = False
        self.exchange._inner_started = True
        self.exchange._inner_connector = SimpleNamespace(
            get_balance=AsyncMock(return_value={
                "clob": [{
                    "orders": {"totalCollateralLocked": "2000000"},
                    "positions": {
                        "yes": {"cost": "3000000"},
                        "no": {"cost": "1000000"},
                    },
                }],
            }),
            _account=SimpleNamespace(address="0x0"),
        )
        self.exchange.logger = MagicMock(return_value=MagicMock(debug=MagicMock(), warning=MagicMock()))

        self.async_run_with_timeout(self.exchange._update_balances())

        self.exchange._inner_connector.get_balance.assert_awaited_once()
        self.assertEqual(Decimal("4"), self.exchange._account_balances["USDC"])
        self.assertEqual(Decimal("2"), self.exchange._account_available_balances["USDC"])
