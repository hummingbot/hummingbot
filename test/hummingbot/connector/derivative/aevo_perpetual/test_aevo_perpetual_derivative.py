import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

import hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative import AevoPerpetualDerivative
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, PriceType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount


class AevoPerpetualDerivativeTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.connector = AevoPerpetualDerivative(
            aevo_perpetual_api_key="",
            aevo_perpetual_api_secret="",
            aevo_perpetual_signing_key="",
            aevo_perpetual_account_address="",
            trading_pairs=[],
            trading_required=False,
        )

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_format_trading_rules_filters_perpetual(self):
        markets = [
            {
                "instrument_id": 1,
                "instrument_name": "ETH-PERP",
                "instrument_type": "PERPETUAL",
                "underlying_asset": "ETH",
                "quote_asset": "USDC",
                "price_step": "0.1",
                "amount_step": "0.01",
                "min_order_value": "10",
                "is_active": True,
            },
            {
                "instrument_id": 2,
                "instrument_name": "ETH-30JUN23-1600-C",
                "instrument_type": "OPTION",
                "underlying_asset": "ETH",
                "quote_asset": "USDC",
                "price_step": "0.1",
                "amount_step": "0.01",
                "min_order_value": "10",
                "is_active": True,
            },
        ]

        rules = self.async_run_with_timeout(self.connector._format_trading_rules(markets))
        self.assertEqual(1, len(rules))
        rule = rules[0]
        self.assertEqual("ETH-USDC", rule.trading_pair)
        self.assertEqual(Decimal("0.1"), rule.min_price_increment)
        self.assertEqual(Decimal("0.01"), rule.min_base_amount_increment)
        self.assertEqual(Decimal("10"), rule.min_order_value)

    def test_initialize_trading_pair_symbols_from_exchange_info(self):
        markets = [
            {
                "instrument_id": 1,
                "instrument_name": "ETH-PERP",
                "instrument_type": "PERPETUAL",
                "underlying_asset": "ETH",
                "quote_asset": "USDC",
                "price_step": "0.1",
                "amount_step": "0.01",
                "min_order_value": "10",
                "is_active": True,
            },
        ]
        self.connector._initialize_trading_pair_symbols_from_exchange_info(markets)
        self.assertEqual(1, self.connector._instrument_ids["ETH-USDC"])
        self.assertEqual("ETH-PERP", self.connector._instrument_names["ETH-USDC"])


class AevoPerpetualDerivativeAsyncTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "ETH"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-PERP"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []

        self.connector = AevoPerpetualDerivative(
            aevo_perpetual_api_key="",
            aevo_perpetual_api_secret="",
            aevo_perpetual_signing_key="",
            aevo_perpetual_account_address="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector.logger().setLevel(1)
        self.connector.logger().addHandler(self)

        self.connector._auth = MagicMock()
        self.connector._auth.sign_order = MagicMock(return_value="signature")
        self.connector._account_address = "0xabc"
        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    async def test_get_price_by_type_uses_funding_fallback(self):
        funding_info = MagicMock()
        funding_info.mark_price = Decimal("2000")
        funding_info.index_price = Decimal("1999")
        self.connector.get_funding_info = MagicMock(return_value=funding_info)

        with patch(
            "hummingbot.connector.perpetual_derivative_py_base.PerpetualDerivativePyBase.get_price_by_type",
            return_value=Decimal("nan"),
        ):
            price = self.connector.get_price_by_type(self.trading_pair, PriceType.MidPrice)

        self.assertEqual(Decimal("2000"), price)

    async def test_get_price_by_type_returns_nan_for_non_fallback_types(self):
        with patch(
            "hummingbot.connector.perpetual_derivative_py_base.PerpetualDerivativePyBase.get_price_by_type",
            return_value=Decimal("nan"),
        ):
            price = self.connector.get_price_by_type(self.trading_pair, PriceType.BestBid)

        self.assertTrue(price.is_nan())

    async def test_supported_order_types(self):
        self.assertEqual(
            [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET],
            self.connector.supported_order_types(),
        )

    async def test_supported_position_modes(self):
        self.assertEqual([PositionMode.ONEWAY], self.connector.supported_position_modes())

    async def test_get_funding_price_fallback_handles_missing_info(self):
        self.connector.get_funding_info = MagicMock(side_effect=KeyError("missing"))

        result = self.connector._get_funding_price_fallback(self.trading_pair)

        self.assertIsNone(result)

    async def test_get_funding_price_fallback_uses_index_price(self):
        funding_info = MagicMock()
        funding_info.mark_price = Decimal("0")
        funding_info.index_price = Decimal("10")
        self.connector.get_funding_info = MagicMock(return_value=funding_info)

        result = self.connector._get_funding_price_fallback(self.trading_pair)

        self.assertEqual(Decimal("10"), result)

    async def test_initialize_trading_pair_symbols_resolves_duplicates(self):
        exchange_info = [
            {
                "instrument_id": 1,
                "instrument_name": self.ex_trading_pair,
                "instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE,
                "underlying_asset": self.base_asset,
                "quote_asset": self.quote_asset,
                "is_active": True,
            },
            {
                "instrument_id": 2,
                "instrument_name": f"{self.base_asset}{self.quote_asset}",
                "instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE,
                "underlying_asset": self.base_asset,
                "quote_asset": self.quote_asset,
                "is_active": True,
            },
        ]

        self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_info)

        mapping = await self.connector.trading_pair_symbol_map()
        self.assertEqual(self.trading_pair, mapping[f"{self.base_asset}{self.quote_asset}"])
        self.assertNotIn(self.ex_trading_pair, mapping)

    async def test_make_trading_rules_request(self):
        self.connector._api_get = AsyncMock(return_value=[{"instrument_name": self.ex_trading_pair}])

        result = await self.connector._make_trading_rules_request()

        self.assertEqual([{"instrument_name": self.ex_trading_pair}], result)
        self.connector._api_get.assert_awaited_once_with(
            path_url=CONSTANTS.MARKETS_PATH_URL,
            params={"instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE},
        )

    async def test_make_trading_pairs_request(self):
        self.connector._api_get = AsyncMock(return_value=[{"instrument_name": self.ex_trading_pair}])

        result = await self.connector._make_trading_pairs_request()

        self.assertEqual([{"instrument_name": self.ex_trading_pair}], result)
        self.connector._api_get.assert_awaited_once_with(
            path_url=CONSTANTS.MARKETS_PATH_URL,
            params={"instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE},
        )

    async def test_get_all_pairs_prices_formats_response(self):
        self.connector._api_get = AsyncMock(return_value=[
            {
                "instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE,
                "instrument_name": self.ex_trading_pair,
                "index_price": "2000",
            },
            {
                "instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE,
                "instrument_name": "BTC-PERP",
                "index_price": "50000",
            },
            {
                "instrument_type": "OPTION",
                "instrument_name": "ETH-30JUN23-1600-C",
                "mark_price": "10",
            },
            {
                "instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE,
                "mark_price": "123",
            },
        ])

        result = await self.connector.get_all_pairs_prices()

        self.assertEqual(
            [
                {"symbol": self.ex_trading_pair, "price": "2000"},
                {"symbol": "BTC-PERP", "price": "50000"},
            ],
            result,
        )
        self.connector._api_get.assert_awaited_once_with(
            path_url=CONSTANTS.MARKETS_PATH_URL,
            params={"instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE},
            limit_id=CONSTANTS.MARKETS_PATH_URL,
        )

    async def test_create_order_book_data_source(self):
        data_source = self.connector._create_order_book_data_source()

        self.assertIsInstance(data_source, OrderBookTrackerDataSource)
        self.assertEqual([self.trading_pair], data_source._trading_pairs)
        self.assertEqual(self.connector._domain, data_source._domain)

    async def test_get_collateral_tokens(self):
        rule = TradingRule(
            trading_pair=self.trading_pair,
            min_base_amount_increment=Decimal("0.1"),
            min_price_increment=Decimal("0.1"),
            min_order_size=Decimal("0.1"),
            min_order_value=Decimal("10"),
            buy_order_collateral_token=self.quote_asset,
            sell_order_collateral_token=self.quote_asset,
        )
        self.connector._trading_rules[self.trading_pair] = rule

        self.assertEqual(self.quote_asset, self.connector.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(self.quote_asset, self.connector.get_sell_collateral_token(self.trading_pair))

    @patch("hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative.safe_ensure_future")
    async def test_buy_market_adjusts_price_with_slippage(self, safe_future_mock):
        self.connector.get_mid_price = MagicMock(return_value=Decimal("100"))
        self.connector.quantize_order_price = MagicMock(return_value=Decimal("101"))
        self.connector._create_order = MagicMock()

        order_id = self.connector.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.MARKET,
            price=Decimal("nan"),
        )

        self.assertIsNotNone(order_id)
        expected_raw_price = Decimal("100") * (Decimal("1") + CONSTANTS.MARKET_ORDER_SLIPPAGE)
        self.connector.quantize_order_price.assert_called_once_with(self.trading_pair, expected_raw_price)
        self.connector._create_order.assert_called_once()
        self.assertEqual(Decimal("101"), self.connector._create_order.call_args.kwargs["price"])
        self.assertEqual(1, safe_future_mock.call_count)

    @patch("hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative.safe_ensure_future")
    async def test_sell_market_adjusts_price_with_slippage(self, safe_future_mock):
        self.connector.get_mid_price = MagicMock(return_value=Decimal("100"))
        self.connector.quantize_order_price = MagicMock(return_value=Decimal("99"))
        self.connector._create_order = MagicMock()

        order_id = self.connector.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.MARKET,
            price=Decimal("nan"),
        )

        self.assertIsNotNone(order_id)
        expected_raw_price = Decimal("100") * (Decimal("1") - CONSTANTS.MARKET_ORDER_SLIPPAGE)
        self.connector.quantize_order_price.assert_called_once_with(self.trading_pair, expected_raw_price)
        self.connector._create_order.assert_called_once()
        self.assertEqual(Decimal("99"), self.connector._create_order.call_args.kwargs["price"])
        self.assertEqual(1, safe_future_mock.call_count)

    async def test_place_order_raises_when_instrument_missing(self):
        with self.assertRaises(KeyError):
            await self.connector._place_order(
                order_id="order-1",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("100"),
            )

        self.assertTrue(self._is_logged("ERROR", f"Order order-1 rejected: instrument not found for {self.trading_pair}."))

    async def test_place_order_successful(self):
        self.connector._instrument_ids[self.trading_pair] = 101
        self.connector._api_post = AsyncMock(return_value={"order_id": "123"})

        with patch("hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative.time.time", return_value=10):
            with patch("hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative.random.randint", return_value=55):
                with patch.object(web_utils, "decimal_to_int", side_effect=[111, 222]):
                    exchange_order_id, _ = await self.connector._place_order(
                        order_id="order-1",
                        trading_pair=self.trading_pair,
                        amount=Decimal("2"),
                        trade_type=TradeType.BUY,
                        order_type=OrderType.LIMIT_MAKER,
                        price=Decimal("3"),
                    )

        self.assertEqual("123", exchange_order_id)
        self.connector._auth.sign_order.assert_called_once_with(
            is_buy=True,
            limit_price=111,
            amount=222,
            salt=55,
            instrument=101,
            timestamp=10,
        )
        self.connector._api_post.assert_awaited_once()
        sent_payload = self.connector._api_post.call_args.kwargs["data"]
        self.assertEqual(101, sent_payload["instrument"])
        self.assertTrue(sent_payload["post_only"])
        self.assertEqual("GTC", sent_payload["time_in_force"])

    async def test_place_order_raises_on_error_response(self):
        self.connector._instrument_ids[self.trading_pair] = 101
        self.connector._api_post = AsyncMock(return_value={"error": "bad request"})

        with self.assertRaises(IOError):
            await self.connector._place_order(
                order_id="order-2",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("100"),
            )

    async def test_place_cancel_returns_false_when_no_exchange_id(self):
        order = MagicMock(spec=InFlightOrder)
        order.get_exchange_order_id = AsyncMock(return_value=None)

        result = await self.connector._place_cancel("order-3", order)

        self.assertFalse(result)

    async def test_place_cancel_raises_on_error(self):
        order = InFlightOrder(
            client_order_id="order-4",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            creation_timestamp=1,
            exchange_order_id="100",
        )
        self.connector._api_delete = AsyncMock(return_value={"error": "rejected"})

        with self.assertRaises(IOError):
            await self.connector._place_cancel("order-4", order)

    async def test_request_order_status_maps_state(self):
        order = InFlightOrder(
            client_order_id="order-5",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            creation_timestamp=1,
            exchange_order_id="200",
        )
        self.connector._api_get = AsyncMock(return_value={
            "order_id": "200",
            "order_status": "filled",
            "timestamp": "1000000000",
        })

        update = await self.connector._request_order_status(order)

        self.assertEqual(order.client_order_id, update.client_order_id)
        self.assertEqual(order.exchange_order_id, update.exchange_order_id)
        self.assertEqual(OrderState.FILLED, update.new_state)
        self.assertEqual(1.0, update.update_timestamp)

    async def test_all_trade_updates_for_order_filters(self):
        order = InFlightOrder(
            client_order_id="order-6",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=Decimal("1"),
            creation_timestamp=1,
            exchange_order_id="300",
            position=PositionAction.CLOSE,
        )
        self.connector._api_get = AsyncMock(return_value={
            "trade_history": [
                {
                    "order_id": "300",
                    "trade_id": "t1",
                    "created_timestamp": "1000000000",
                    "price": "100",
                    "amount": "2",
                    "fees": "0.01",
                },
                {
                    "order_id": "999",
                    "trade_id": "t2",
                    "created_timestamp": "1000000001",
                    "price": "99",
                    "amount": "1",
                    "fees": "0.02",
                },
            ]
        })

        updates = await self.connector._all_trade_updates_for_order(order)

        self.assertEqual(1, len(updates))
        update = updates[0]
        self.assertEqual("t1", update.trade_id)
        self.assertEqual(Decimal("100"), update.fill_price)
        self.assertEqual(Decimal("2"), update.fill_base_amount)
        self.assertEqual(TokenAmount(amount=Decimal("0.01"), token=self.quote_asset), update.fee.flat_fees[0])

    async def test_update_balances_updates_and_removes(self):
        self.connector._account_balances = {"OLD": Decimal("1")}
        self.connector._account_available_balances = {"OLD": Decimal("1")}
        self.connector._api_get = AsyncMock(return_value={
            "collaterals": [
                {
                    "collateral_asset": self.quote_asset,
                    "available_balance": "10",
                    "balance": "12",
                }
            ]
        })

        await self.connector._update_balances()

        self.assertEqual({"USDC": Decimal("12")}, self.connector._account_balances)
        self.assertEqual({"USDC": Decimal("10")}, self.connector._account_available_balances)

    async def test_update_balances_logs_warning_when_missing_collaterals(self):
        self.connector._api_get = AsyncMock(return_value={})

        await self.connector._update_balances()

        self.assertTrue(
            self._is_logged("WARNING", "Aevo account response did not include collaterals; balance update skipped.")
        )

    async def test_update_positions_sets_and_clears_positions(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        self.connector._api_get = AsyncMock(side_effect=[
            {
                "positions": [
                    {
                        "instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE,
                        "instrument_name": self.ex_trading_pair,
                        "side": "buy",
                        "amount": "2",
                        "avg_entry_price": "100",
                        "unrealized_pnl": "1",
                        "leverage": "3",
                    }
                ]
            },
            {"positions": []},
        ])

        await self.connector._update_positions()
        positions = list(self.connector.account_positions.values())
        self.assertEqual(1, len(positions))
        self.assertEqual(PositionSide.LONG, positions[0].position_side)
        self.assertEqual(Decimal("2"), positions[0].amount)

        await self.connector._update_positions()
        self.assertEqual(0, len(self.connector.account_positions))

    async def test_update_positions_sets_short_position_amount_as_negative(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        self.connector._api_get = AsyncMock(return_value={
            "positions": [
                {
                    "instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE,
                    "instrument_name": self.ex_trading_pair,
                    "side": "sell",
                    "amount": "2",
                    "avg_entry_price": "100",
                    "unrealized_pnl": "1",
                    "leverage": "3",
                }
            ]
        })

        await self.connector._update_positions()

        positions = list(self.connector.account_positions.values())
        self.assertEqual(1, len(positions))
        self.assertEqual(PositionSide.SHORT, positions[0].position_side)
        self.assertEqual(Decimal("-2"), positions[0].amount)

    async def test_update_positions_does_not_override_configured_leverage(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        self.connector._perpetual_trading.set_leverage(self.trading_pair, 3)
        self.connector._api_get = AsyncMock(return_value={
            "positions": [
                {
                    "instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE,
                    "instrument_name": self.ex_trading_pair,
                    "side": "buy",
                    "amount": "2",
                    "avg_entry_price": "100",
                    "unrealized_pnl": "1",
                    "leverage": "1",
                }
            ]
        })

        await self.connector._update_positions()

        self.assertEqual(3, self.connector._perpetual_trading.get_leverage(self.trading_pair))

    async def test_set_trading_pair_leverage_missing_instrument(self):
        result = await self.connector._set_trading_pair_leverage(self.trading_pair, 5)

        self.assertEqual((False, "Instrument not found"), result)

    async def test_set_trading_pair_leverage_success(self):
        self.connector._instrument_ids[self.trading_pair] = 100
        self.connector._api_post = AsyncMock(return_value={})

        result = await self.connector._set_trading_pair_leverage(self.trading_pair, 5)

        self.assertEqual((True, ""), result)
        self.assertEqual(5, self.connector._perpetual_trading.get_leverage(self.trading_pair))

    async def test_set_trading_pair_leverage_error(self):
        self.connector._instrument_ids[self.trading_pair] = 100
        self.connector._api_post = AsyncMock(side_effect=Exception("boom"))

        result = await self.connector._set_trading_pair_leverage(self.trading_pair, 5)

        self.assertEqual((False, "Error setting leverage: boom"), result)

    @patch("hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative.safe_ensure_future")
    async def test_on_order_failure_ignores_reduce_only_rejection_for_close_orders(self, safe_ensure_future_mock):
        self.connector._order_tracker.process_order_update = MagicMock()
        self.connector._update_positions = AsyncMock()
        safe_ensure_future_mock.side_effect = lambda coro: coro.close()
        exception = IOError(
            "Error executing request POST https://api.aevo.xyz/orders. HTTP status is 400. "
            "Error: {\"error\":\"NO_POSITION_REDUCE_ONLY\"}"
        )

        self.connector._on_order_failure(
            order_id="order-9",
            trading_pair=self.trading_pair,
            amount=Decimal("0.2"),
            trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("100"),
            exception=exception,
            position_action=PositionAction.CLOSE,
        )

        self.connector._order_tracker.process_order_update.assert_called_once()
        order_update = self.connector._order_tracker.process_order_update.call_args.args[0]
        self.assertEqual(OrderState.CANCELED, order_update.new_state)
        self.assertEqual("order-9", order_update.client_order_id)
        self.assertEqual(self.trading_pair, order_update.trading_pair)
        self.assertEqual(exception.__class__.__name__, order_update.misc_updates["error_type"])
        safe_ensure_future_mock.assert_called_once()
        self.assertTrue(
            any(
                "Ignoring rejected reduce-only close order order-9" in record.getMessage()
                for record in self.log_records
            )
        )

    @patch("hummingbot.connector.exchange_py_base.ExchangePyBase._on_order_failure")
    async def test_on_order_failure_delegates_to_base_for_non_reduce_only_rejections(self, base_on_order_failure_mock):
        exception = IOError("some other error")

        self.connector._on_order_failure(
            order_id="order-10",
            trading_pair=self.trading_pair,
            amount=Decimal("0.2"),
            trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("100"),
            exception=exception,
            position_action=PositionAction.CLOSE,
        )

        base_on_order_failure_mock.assert_called_once()

    async def test_process_order_message_updates_tracker(self):
        tracked_order = InFlightOrder(
            client_order_id="order-7",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            creation_timestamp=1,
            exchange_order_id="400",
        )
        self.connector._order_tracker.start_tracking_order(tracked_order)
        self.connector._order_tracker.process_order_update = MagicMock()

        self.connector._process_order_message({
            "order_id": "400",
            "order_status": "filled",
            "created_timestamp": "1000000000",
        })

        self.connector._order_tracker.process_order_update.assert_called_once()
        update = self.connector._order_tracker.process_order_update.call_args.kwargs["order_update"]
        self.assertEqual(OrderState.FILLED, update.new_state)

    async def test_process_trade_message_updates_tracker(self):
        tracked_order = InFlightOrder(
            client_order_id="order-8",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            creation_timestamp=1,
            exchange_order_id="500",
            position=PositionAction.OPEN,
        )
        self.connector._order_tracker.start_tracking_order(tracked_order)
        self.connector._order_tracker.process_trade_update = MagicMock()

        await self.connector._process_trade_message({
            "order_id": "500",
            "trade_id": "t3",
            "created_timestamp": "2000000000",
            "price": "10",
            "filled": "3",
            "fees": "0.1",
        })

        self.connector._order_tracker.process_trade_update.assert_called_once()
        update = self.connector._order_tracker.process_trade_update.call_args.args[0]
        self.assertEqual("t3", update.trade_id)
        self.assertEqual(Decimal("3"), update.fill_base_amount)
        self.assertEqual(TokenAmount(amount=Decimal("0.1"), token=self.quote_asset), update.fee.flat_fees[0])

    async def test_process_position_message_sets_position(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        pos_key = self.connector._perpetual_trading.position_key(self.trading_pair, PositionSide.LONG)

        await self.connector._process_position_message({
            "instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE,
            "instrument_name": self.ex_trading_pair,
            "side": "buy",
            "amount": "2",
            "avg_entry_price": "100",
            "unrealized_pnl": "1",
            "leverage": "3",
        })

        position: Position = self.connector.account_positions[pos_key]
        self.assertEqual(Decimal("2"), position.amount)

    async def test_process_position_message_sets_short_position_with_negative_amount(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        pos_key = self.connector._perpetual_trading.position_key(self.trading_pair, PositionSide.SHORT)

        await self.connector._process_position_message({
            "instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE,
            "instrument_name": self.ex_trading_pair,
            "side": "sell",
            "amount": "2",
            "avg_entry_price": "100",
            "unrealized_pnl": "1",
            "leverage": "3",
        })

        position: Position = self.connector.account_positions[pos_key]
        self.assertEqual(PositionSide.SHORT, position.position_side)
        self.assertEqual(Decimal("-2"), position.amount)

    async def test_user_stream_event_listener_routes_messages(self):
        self.connector._process_order_message = MagicMock()
        self.connector._process_trade_message = AsyncMock()
        self.connector._process_position_message = AsyncMock()

        async def message_generator():
            yield {
                "channel": CONSTANTS.WS_ORDERS_CHANNEL,
                "data": {"orders": [{"order_id": "1"}]},
            }
            yield {
                "channel": CONSTANTS.WS_FILLS_CHANNEL,
                "data": {"fill": {"order_id": "2"}},
            }
            yield {
                "channel": CONSTANTS.WS_POSITIONS_CHANNEL,
                "data": {"positions": [{"instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE}]},
            }

        self.connector._iter_user_event_queue = message_generator

        await self.connector._user_stream_event_listener()

        self.connector._process_order_message.assert_called_once()
        self.connector._process_trade_message.assert_awaited_once()
        self.connector._process_position_message.assert_awaited_once()

    async def test_user_stream_event_listener_logs_unexpected_channel(self):
        async def message_generator():
            yield {"channel": "unknown", "data": {}}

        self.connector._iter_user_event_queue = message_generator

        await self.connector._user_stream_event_listener()

        self.assertTrue(self._is_logged("ERROR", "Unexpected message in user stream: {'channel': 'unknown', 'data': {}}."))

    async def test_get_last_traded_price_uses_mark_price(self):
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.connector._api_get = AsyncMock(return_value={"mark_price": "10", "index_price": "9"})

        price = await self.connector._get_last_traded_price(self.trading_pair)

        self.assertEqual(10.0, price)
