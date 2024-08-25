import asyncio
from typing import Any, Dict, List, Union
from unittest.mock import patch

from _decimal import Decimal

from hummingbot.connector.gateway.clob_spot.data_sources.rubicon.rubicon_api_data_source import RubiconAPIDataSource
from hummingbot.connector.gateway.clob_spot.data_sources.rubicon.rubicon_types import (
    OrderSide as RubiconOrderSide,
    OrderStatus as RubiconOrderStatus,
    OrderType as RubiconOrderType,
)
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.test_support.gateway_clob_api_data_source_test import AbstractGatewayCLOBAPIDataSourceTests
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TradeFeeBase


class RubiconAPIDataSourceTest(AbstractGatewayCLOBAPIDataSourceTests.GatewayCLOBAPIDataSourceTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.chain = "ethereum"  # noqa: mock
        cls.network = "mainnet"
        cls.base = "WETH"  # noqa: mock
        cls.quote = "USDC"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.base, quote=cls.quote)

    def setUp(self) -> None:
        super().setUp()

        self.configure_asyncio_sleep()
        self.data_source._gateway = self.gateway_instance_mock
        self.configure_async_functions_with_decorator()

    def tearDown(self) -> None:
        super().tearDown()

    def build_api_data_source(self, with_api_key: bool = True) -> Any:
        connector_spec = {
            "chain": self.chain,
            "network": self.network,
        }

        data_source = RubiconAPIDataSource(
            trading_pairs=[self.trading_pair],
            connector_spec=connector_spec,
            client_config_map=self.client_config_map,
        )

        return data_source

    @property
    def exchange_base(self) -> str:
        return self.base

    @property
    def exchange_quote(self) -> str:
        return self.quote

    @property
    def expected_base_decimals(self) -> int:
        return 18

    @property
    def expected_quote_decimals(self) -> int:
        return 6

    @property
    def expected_base_address(self) -> int:
        return "0x00000"

    @property
    def expected_quote_address(self) -> int:
        return "0x00001"

    @property
    def expected_transaction_hash(self) -> str:
        return ""

    @staticmethod
    def configure_asyncio_sleep():
        async def sleep(*_args, **_kwargs):
            pass

        patch.object(asyncio, "sleep", new_callable=sleep)

    def configure_async_functions_with_decorator(self):
        def wrapper(object, function):
            async def closure(*args, **kwargs):
                return await function(object, *args, **kwargs)

            return closure

        self.data_source._gateway_ping_gateway = wrapper(self.data_source, self.data_source._gateway_ping_gateway.original)
        self.data_source._gateway_get_clob_markets = wrapper(self.data_source, self.data_source._gateway_get_clob_markets.original)
        self.data_source._gateway_get_clob_ticker = wrapper(self.data_source, self.data_source._gateway_get_clob_ticker.original)
        self.data_source._gateway_get_balances = wrapper(self.data_source, self.data_source._gateway_get_balances.original)
        self.data_source._gateway_clob_place_order = wrapper(self.data_source, self.data_source._gateway_clob_place_order.original)
        self.data_source._gateway_clob_cancel_order = wrapper(self.data_source, self.data_source._gateway_clob_cancel_order.original)
        self.data_source._gateway_get_clob_order_status_updates = wrapper(self.data_source, self.data_source._gateway_get_clob_order_status_updates.original)

    def configure_place_order_response(
        self,
        timestamp: float,
        transaction_hash: str,
        exchange_order_id: str,
        trade_type: TradeType,
        price: Decimal,
        size: Decimal,
    ):
        super().configure_place_order_response(
            timestamp,
            transaction_hash,
            exchange_order_id,
            trade_type,
            price,
            size,
        )
        self.gateway_instance_mock.clob_place_order.return_value["id"] = "1"

    def configure_place_order_failure_response(self):
        super().configure_place_order_failure_response()
        self.gateway_instance_mock.clob_place_order.return_value["id"] = "1"

    def get_trading_pairs_info_response(self) -> List[Dict[str, Any]]:
        return [
            {
                "baseSymbol": self.exchange_base,
                "quoteSymbol": self.exchange_quote,
                "baseDecimals": self.expected_base_decimals,
                "quoteDecimals": self.expected_quote_decimals,
                "baseAddress": self.expected_base_address,
                "quoteAddress": self.expected_quote_address
            }
        ]

    def get_order_status_response(
        self,
        timestamp: float,
        trading_pair: str,
        exchange_order_id: str,
        client_order_id: str,
        status: OrderState
    ) -> List[Dict[str, Any]]:
        return [{
            "id": client_order_id,
            "orderHash": client_order_id,
            "clientId": client_order_id,
            "status": RubiconOrderStatus.from_hummingbot(status).name,
        }]

    def get_clob_ticker_response(
        self,
        trading_pair: str,
        last_traded_price: Decimal
    ) -> Dict[str, Any]:
        return {
            "markets": {  # noqa: mock
                "price": "0.641",
            }
        }

    def configure_account_balances_response(
        self,
        base_total_balance: Decimal,
        base_available_balance: Decimal,
        quote_total_balance: Decimal,
        quote_available_balance: Decimal
    ):
        self.gateway_instance_mock.get_balances.return_value = self.configure_gateway_get_balances_response()

    def configure_empty_order_fills_response(self):
        pass

    def configure_trade_fill_response(
        self,
        timestamp: float,
        exchange_order_id: str,
        price: Decimal,
        size: Decimal,
        fee: TradeFeeBase, trade_id: Union[str, int], is_taker: bool
    ):
        pass

    def configure_gateway_get_clob_markets_response(self):
        return {
            "network": "mainnet",
            "timestamp": 1694561843115,
            "latency": 0.001,
            "markets": {
                f"{self.exchange_base}-{self.exchange_quote}": {
                    "baseSymbol": self.exchange_base,
                    "quoteSymbol": self.exchange_quote,
                    "baseDecimals": self.expected_base_decimals,
                    "quoteDecimals": self.expected_quote_decimals,
                    "baseAddress": self.expected_base_address,
                    "quoteAddress": self.expected_quote_address
                }
            }
        }

    def configure_gateway_get_balances_response(self):
        return {
            "balances": {
                self.exchange_base: {
                    "total_balance": self.expected_base_total_balance,
                    "available_balance": self.expected_base_available_balance
                },
                self.exchange_quote: {
                    "total_balance": self.expected_quote_total_balance,
                    "available_balance": self.expected_quote_available_balance
                }
            }
        }

    def test_get_supported_order_types(self):
        order_types = self.data_source.get_supported_order_types()
        self.assertEqual(order_types.__len__, 1)
        self.assertEqual(order_types[0], OrderType.LIMIT)

    def test_get_exchange_base_quote_tokens_from_market_info(self):
        response = self.configure_gateway_get_clob_markets_response()
        market_info = self.data_source._get_exchange_base_quote_tokens_from_market_info(response.markets)
        self.assertEqual(market_info["baseSymbol"], self.exchange_base)
        self.assertEqual(market_info["quoteSymbol"], self.exchange_quote)

    def test_get_exchange_trading_pair_from_market_info(self):
        response = self.configure_gateway_get_clob_markets_response()
        pair = self.data_source._get_exchange_trading_pair_from_market_info(response.markets)
        self.assertEqual(pair, f"{self.base}/{self.quote}")

    def test_get_trading_pair_from_market_info(self):
        response = self.configure_gateway_get_clob_markets_response()
        pair = self.data_source._get_trading_pair_from_market_info(response.markets)
        self.assertEqual(pair, f"{self.exchange_base}-{self.exchange_quote}")

    def test_get_all_order_fills(self):
        asyncio.get_event_loop().run_until_complete(
            self.data_source._update_markets()
        )
        in_flight_order = GatewayInFlightOrder(
            initial_state=OrderState.PENDING_CREATE,
            client_order_id=self.expected_sell_client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=self.initial_timestamp - 10,
            price=self.expected_sell_order_price,
            amount=self.expected_sell_order_size,
            exchange_order_id=self.expected_sell_exchange_order_id,
        )
        self.data_source.gateway_order_tracker.active_orders[in_flight_order.client_order_id] = in_flight_order
        self.enqueue_order_status_response(
            timestamp=self.initial_timestamp + 1,
            trading_pair=in_flight_order.trading_pair,
            exchange_order_id=self.expected_buy_exchange_order_id,
            client_order_id=in_flight_order.client_order_id,
            status=OrderState.FILLED,
        )

        trade_updates: List[TradeUpdate] = self.async_run_with_timeout(
            coro=self.data_source.get_all_order_fills(in_flight_order=in_flight_order),
        )

        self.assertEqual(1, len(trade_updates))

        trade_update = trade_updates[0]

        self.assertIsNotNone(trade_update.trade_id)
        self.assertEqual(self.expected_sell_client_order_id, trade_update.client_order_id)
        self.assertEqual(self.expected_sell_exchange_order_id, trade_update.exchange_order_id)
        self.assertEqual(self.trading_pair, trade_update.trading_pair)
        self.assertLess(float(0), trade_update.fill_timestamp)
        self.assertEqual(self.expected_fill_price, trade_update.fill_price)
        self.assertEqual(self.expected_fill_size, trade_update.fill_base_amount)
        self.assertEqual(self.expected_fill_size * self.expected_fill_price, trade_update.fill_quote_amount)
        self.assertEqual(self.expected_fill_fee, trade_update.fee)
        self.assertTrue(trade_update.is_taker)

    def test_get_all_order_fills_no_fills(self):
        super().test_get_all_order_fills_no_fills()

    def test_get_last_traded_price(self):
        self.configure_last_traded_price(
            trading_pair=self.trading_pair, last_traded_price=self.expected_last_traded_price
        )
        last_trade_price = self.async_run_with_timeout(
            coro=self.data_source.get_last_traded_price(trading_pair=self.trading_pair)
        )

        self.assertEqual(self.expected_last_traded_price, last_trade_price)

    def test_get_order_status_update(self):
        creation_transaction_hash = "0x7cb2eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2g81d"  # noqa: mock
        in_flight_order = GatewayInFlightOrder(
            client_order_id=self.expected_buy_client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=self.initial_timestamp,
            price=self.expected_buy_order_price,
            amount=self.expected_buy_order_size,
            creation_transaction_hash=creation_transaction_hash,
            exchange_order_id=self.expected_buy_exchange_order_id,
        )
        self.data_source.gateway_order_tracker.active_orders[in_flight_order.client_order_id] = in_flight_order
        self.enqueue_order_status_response(
            timestamp=self.initial_timestamp + 1,
            trading_pair=in_flight_order.trading_pair,
            exchange_order_id=self.expected_buy_exchange_order_id,
            client_order_id=in_flight_order.client_order_id,
            status=OrderState.PENDING_CREATE,
        )

        status_update: OrderUpdate = self.async_run_with_timeout(
            coro=self.data_source.get_order_status_update(in_flight_order=in_flight_order)
        )

        self.assertEqual(self.trading_pair, status_update.trading_pair)
        self.assertLess(self.initial_timestamp, status_update.update_timestamp)
        self.assertEqual(OrderState.PENDING_CREATE, status_update.new_state)
        self.assertEqual(in_flight_order.client_order_id, status_update.client_order_id)
        self.assertEqual(self.expected_buy_exchange_order_id, status_update.exchange_order_id)

    def test_order_status_methods(self):
        for item in RubiconOrderStatus:
            if item == RubiconOrderStatus.UNKNOWN:
                continue

            hummingbot_status = RubiconOrderStatus.to_hummingbot(item)
            rubicon_status = RubiconOrderStatus.from_hummingbot(hummingbot_status)
            rubicon_status_from_name = RubiconOrderStatus.from_name(rubicon_status.name)

            self.assertEqual(item, rubicon_status)
            self.assertEqual(item, rubicon_status_from_name)

    def test_order_sides(self):
        for item in RubiconOrderSide:
            hummingbot_side = RubiconOrderSide.to_hummingbot(item)
            rubicon_side = RubiconOrderSide.from_hummingbot(hummingbot_side)
            rubicon_side_from_name = RubiconOrderSide.from_name(rubicon_side.name)

            self.assertEqual(item, rubicon_side)
            self.assertEqual(item, rubicon_side_from_name)

    def test_order_types(self):
        for item in RubiconOrderType:
            hummingbot_type = RubiconOrderType.to_hummingbot(item)
            rubicon_type = RubiconOrderType.from_hummingbot(hummingbot_type)
            rubicon_type_from_name = RubiconOrderType.from_name(rubicon_type.name)

            self.assertEqual(item, rubicon_type)
            self.assertEqual(item, rubicon_type_from_name)
