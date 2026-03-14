import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import GRVTPerpetualDerivative
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, PriceType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount


class GRVTPerpetualDerivativeTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.connector = GRVTPerpetualDerivative(
            grvt_perpetual_api_key="",
            grvt_perpetual_api_secret="",
            trading_pairs=[],
            trading_required=False,
        )

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_format_trading_rules_filters_perpetual(self):
        markets = [
            {
                "symbol": "BTC-USDT",
                "pair": "BTC-USDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "status": "TRADING",
                "contractType": "PERPETUAL",
                "filters": [
                    {
                        "filterType": "LOT_SIZE",
                        "minQty": "0.001",
                        "stepSize": "0.001",
                    },
                    {
                        "filterType": "PRICE_FILTER",
                        "tickSize": "0.01",
                    },
                    {
                        "filterType": "MIN_NOTIONAL",
                        "notional": "5",
                    }
                ],
                "marginAsset": "USDT",
            },
            {
                "symbol": "ETH-USDT",
                "pair": "ETH-USDT",
                "baseAsset": "ETH",
                "quoteAsset": "USDT",
                "status": "TRADING",
                "contractType": "PERPETUAL",
                "filters": [
                    {
                        "filterType": "LOT_SIZE",
                        "minQty": "0.01",
                        "stepSize": "0.01",
                    },
                    {
                        "filterType": "PRICE_FILTER",
                        "tickSize": "0.01",
                    },
                ],
                "marginAsset": "USDT",
            },
        ]

        rules = self.async_run_with_timeout(self.connector._format_trading_rules(markets))
        self.assertEqual(2, len(rules))

    def test_initialize_trading_pair_symbols_from_exchange_info(self):
        markets = [
            {
                "symbol": "BTC-USDT",
                "pair": "BTC-USDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "status": "TRADING",
                "contractType": "PERPETUAL",
            },
        ]
        self.connector._initialize_trading_pair_symbols_from_exchange_info(markets)
        mapping = self.connector._trading_pair_symbol_map
        self.assertEqual("BTC-USDT", mapping.get("BTC-USDT"))


class GRVTPerpetualDerivativeAsyncTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []

        self.connector = GRVTPerpetualDerivative(
            grvt_perpetual_api_key="",
            grvt_perpetual_api_secret="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector.logger().setLevel(1)
        self.connector.logger().addHandler(self)

        self.connector._auth = MagicMock()
        self.connector._account_balances = {"USDT": Decimal("1000")}
        self.connector._account_available_balances = {"USDT": Decimal("1000")}
        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    async def test_supported_order_types(self):
        self.assertEqual(
            [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER],
            self.connector.supported_order_types()
        )

    async def test_supported_position_modes(self):
        self.assertEqual(
            [PositionMode.ONEWAY, PositionMode.HEDGE],
            self.connector.supported_position_modes()
        )

    async def test_place_order_market(self):
        self.connector._api_post = AsyncMock(return_value={
            "orderId": "12345",
            "symbol": "BTC-USDT",
            "side": "BUY",
            "quantity": "0.1",
            "type": "MARKET",
            "status": "FILLED",
            "price": "0",
            "clientOrderId": "test_order_id",
            "updateTime": 1234567890,
        })

        o_id, txn_time = await self.connector._place_order(
            order_id="test_order_id",
            trading_pair=self.trading_pair,
            amount=Decimal("0.1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.MARKET,
            price=Decimal("50000"),
        )

        self.assertEqual("12345", o_id)
        self.assertEqual(1234567890, txn_time)

    async def test_place_order_limit(self):
        self.connector._api_post = AsyncMock(return_value={
            "orderId": "12345",
            "symbol": "BTC-USDT",
            "side": "BUY",
            "quantity": "0.1",
            "type": "LIMIT",
            "status": "NEW",
            "price": "50000",
            "clientOrderId": "test_order_id",
            "updateTime": 1234567890,
        })

        o_id, txn_time = await self.connector._place_order(
            order_id="test_order_id",
            trading_pair=self.trading_pair,
            amount=Decimal("0.1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50000"),
        )

        self.assertEqual("12345", o_id)

    async def test_cancel_order(self):
        tracked_order = InFlightOrder(
            client_order_id="test_order_id",
            exchange_order_id="exchange_12345",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("0.1"),
            price=Decimal("50000"),
        )
        tracked_order.update_state(OrderState.OPEN, 1234567890)

        self.connector._api_delete = AsyncMock(return_value={
            "orderId": "exchange_12345",
            "symbol": "BTC-USDT",
            "status": "CANCELED",
        })

        result = await self.connector._place_cancel("test_order_id", tracked_order)
        self.assertTrue(result)

    async def test_cancel_order_not_found(self):
        tracked_order = InFlightOrder(
            client_order_id="test_order_id",
            exchange_order_id="exchange_12345",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("0.1"),
            price=Decimal("50000"),
        )

        self.connector._api_delete = AsyncMock(return_value={
            "code": -1,
            "msg": "Order not found",
        })

        with self.assertRaises(IOError):
            await self.connector._place_cancel("test_order_id", tracked_order)

    async def test_update_balances(self):
        self.connector._api_get = AsyncMock(return_value={
            "assets": [
                {
                    "asset": "USDT",
                    "walletBalance": "1000.0",
                    "availableBalance": "900.0",
                },
                {
                    "asset": "BTC",
                    "walletBalance": "0.5",
                    "availableBalance": "0.4",
                }
            ]
        })

        await self.connector._update_balances()

        self.assertEqual(Decimal("1000"), self.connector._account_balances.get("USDT"))
        self.assertEqual(Decimal("900"), self.connector._account_available_balances.get("USDT"))
        self.assertEqual(Decimal("0.5"), self.connector._account_balances.get("BTC"))

    async def test_update_positions(self):
        self.connector._api_get = AsyncMock(return_value=[
            {
                "symbol": "BTC-USDT",
                "positionSide": "LONG",
                "positionAmt": "0.5",
                "entryPrice": "50000.0",
                "unRealizedProfit": "100.0",
                "leverage": "10",
            }
        ])

        await self.connector._update_positions()

        position = self.connector._perpetual_trading.get_position(self.trading_pair, PositionSide.LONG)
        self.assertIsNotNone(position)
        self.assertEqual(Decimal("0.5"), position.amount)
        self.assertEqual(Decimal("50000"), position.entry_price)

    async def test_request_order_status(self):
        self.connector._api_get = AsyncMock(return_value={
            "orderId": "exchange_12345",
            "symbol": "BTC-USDT",
            "clientOrderId": "test_order_id",
            "status": "FILLED",
            "price": "50000",
            "updateTime": 1234567890,
        })

        tracked_order = InFlightOrder(
            client_order_id="test_order_id",
            exchange_order_id="exchange_12345",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("0.1"),
            price=Decimal("50000"),
        )

        order_update = await self.connector._request_order_status(tracked_order)
        self.assertEqual(OrderState.FILLED, order_update.new_state)

    async def test_get_last_traded_price(self):
        self.connector._api_get = AsyncMock(return_value={
            "lastPrice": "50000.0",
        })

        price = await self.connector._get_last_traded_price(self.trading_pair)
        self.assertEqual(50000.0, price)

    async def test_set_leverage(self):
        self.connector._api_post = AsyncMock(return_value={
            "symbol": "BTC-USDT",
            "leverage": 10,
        })

        success, msg = await self.connector._set_trading_pair_leverage(self.trading_pair, 10)
        self.assertTrue(success)

    async def test_format_trading_rules(self):
        exchange_info = {
            "symbols": [
                {
                    "symbol": "BTC-USDT",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "contractType": "PERPETUAL",
                    "filters": [
                        {
                            "filterType": "LOT_SIZE",
                            "minQty": "0.001",
                            "stepSize": "0.001",
                        },
                        {
                            "filterType": "PRICE_FILTER",
                            "tickSize": "0.01",
                        },
                        {
                            "filterType": "MIN_NOTIONAL",
                            "notional": "5",
                        }
                    ],
                    "marginAsset": "USDT",
                }
            ]
        }

        rules = await self.connector._format_trading_rules(exchange_info)
        self.assertEqual(1, len(rules))
        rule = rules[0]
        self.assertEqual("BTC-USDT", rule.trading_pair)
        self.assertEqual(Decimal("0.001"), rule.min_order_size)
        self.assertEqual(Decimal("0.01"), rule.min_price_increment)
