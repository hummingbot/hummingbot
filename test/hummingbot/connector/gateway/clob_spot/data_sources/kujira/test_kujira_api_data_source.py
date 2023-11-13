import asyncio
from typing import Any, Dict, List, Union
from unittest.mock import patch

from _decimal import Decimal
from bidict import bidict
from dotmap import DotMap

from hummingbot.connector.gateway.clob_spot.data_sources.kujira.kujira_api_data_source import KujiraAPIDataSource
from hummingbot.connector.gateway.clob_spot.data_sources.kujira.kujira_helpers import (
    convert_hb_trading_pair_to_market_name,
    convert_market_name_to_hb_trading_pair,
    generate_hash,
)
from hummingbot.connector.gateway.clob_spot.data_sources.kujira.kujira_types import (
    OrderSide as KujiraOrderSide,
    OrderStatus as KujiraOrderStatus,
    OrderType as KujiraOrderType,
)
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.test_support.gateway_clob_api_data_source_test import AbstractGatewayCLOBAPIDataSourceTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.trade_fee import (
    DeductedFromReturnsTradeFee,
    MakerTakerExchangeFeeRates,
    TokenAmount,
    TradeFeeBase,
)
from hummingbot.core.network_iterator import NetworkStatus


class KujiraAPIDataSourceTest(AbstractGatewayCLOBAPIDataSourceTests.GatewayCLOBAPIDataSourceTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.chain = "kujira"  # noqa: mock
        cls.network = "mainnet"
        cls.base = "KUJI"  # noqa: mock
        cls.quote = "USK"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.base, quote=cls.quote)
        cls.owner_address = "kujira1yrensec9gzl7y3t3duz44efzgwj21b2arayr1w"  # noqa: mock

    def setUp(self) -> None:
        super().setUp()

        self.configure_asyncio_sleep()
        self.data_source._gateway = self.gateway_instance_mock
        self.configure_async_functions_with_decorator()
        self.configure_get_market()

    def tearDown(self) -> None:
        super().tearDown()

    @property
    def expected_buy_client_order_id(self) -> str:
        return "03719e91d18db65ec3bf5554d678e5b4"

    @property
    def expected_sell_client_order_id(self) -> str:
        return "02719e91d18db65ec3bf5554d678e5b2"

    @property
    def expected_buy_exchange_order_id(self) -> str:
        return "1"

    @property
    def expected_sell_exchange_order_id(self) -> str:
        return "2"

    @property
    def exchange_base(self) -> str:
        return self.base

    @property
    def exchange_quote(self) -> str:
        return self.quote

    @property
    def expected_quote_decimals(self) -> int:
        return 6

    @property
    def expected_base_decimals(self) -> int:
        return 6

    @property
    def expected_maker_taker_fee_rates(self) -> MakerTakerExchangeFeeRates:
        return MakerTakerExchangeFeeRates(
            maker=Decimal("0.075"),
            taker=Decimal("0.15"),
            maker_flat_fees=[],
            taker_flat_fees=[],
        )

    @property
    def expected_min_price_increment(self):
        return Decimal("0.001")

    @property
    def expected_last_traded_price(self) -> Decimal:
        return Decimal("0.641")

    @property
    def expected_base_total_balance(self) -> Decimal:
        return Decimal("6.355439")

    @property
    def expected_base_available_balance(self) -> Decimal:
        return Decimal("6.355439")

    @property
    def expected_quote_total_balance(self) -> Decimal:
        return Decimal("3.522325")

    @property
    def expected_quote_available_balance(self) -> Decimal:
        return Decimal("3.522325")

    @property
    def expected_fill_price(self) -> Decimal:
        return Decimal("11")

    @property
    def expected_fill_size(self) -> Decimal:
        return Decimal("3")

    @property
    def expected_fill_fee_amount(self) -> Decimal:
        return Decimal("0.15")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(
            flat_fees=[TokenAmount(token=self.expected_fill_fee_token, amount=self.expected_fill_fee_amount)]
        )

    def build_api_data_source(self, with_api_key: bool = True) -> Any:
        connector_spec = {
            "chain": self.chain,
            "network": self.network,
            "wallet_address": self.owner_address,
        }

        data_source = KujiraAPIDataSource(
            trading_pairs=[self.trading_pair],
            connector_spec=connector_spec,
            client_config_map=self.client_config_map,
        )

        return data_source

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
        self.data_source._gateway_get_clob_orderbook_snapshot = wrapper(self.data_source, self.data_source._gateway_get_clob_orderbook_snapshot.original)
        self.data_source._gateway_get_clob_ticker = wrapper(self.data_source, self.data_source._gateway_get_clob_ticker.original)
        self.data_source._gateway_get_balances = wrapper(self.data_source, self.data_source._gateway_get_balances.original)
        self.data_source._gateway_clob_place_order = wrapper(self.data_source, self.data_source._gateway_clob_place_order.original)
        self.data_source._gateway_clob_cancel_order = wrapper(self.data_source, self.data_source._gateway_clob_cancel_order.original)
        self.data_source._gateway_clob_batch_order_modify = wrapper(self.data_source, self.data_source._gateway_clob_batch_order_modify.original)
        self.data_source._gateway_get_clob_order_status_updates = wrapper(self.data_source, self.data_source._gateway_get_clob_order_status_updates.original)

    @patch("hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.get_clob_markets")
    def configure_get_market(self, *_args):
        self.data_source._gateway.get_clob_markets.return_value = self.configure_gateway_get_clob_markets_response()

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

    def configure_batch_order_create_response(
        self,
        timestamp: float,
        transaction_hash: str,
        created_orders: List[GatewayInFlightOrder],
    ):
        super().configure_batch_order_create_response(
            timestamp=self.initial_timestamp,
            transaction_hash=self.expected_transaction_hash,
            created_orders=created_orders,
        )
        self.gateway_instance_mock.clob_batch_order_modify.return_value["ids"] = ["1", "2"]

    def get_trading_pairs_info_response(self) -> List[Dict[str, Any]]:
        response = self.configure_gateway_get_clob_markets_response()

        market = response.markets[list(response.markets.keys())[0]]

        market_name = convert_market_name_to_hb_trading_pair(market.name)

        return [{"market_name": market_name, "market": market}]

    def get_order_status_response(
        self,
        timestamp: float,
        trading_pair: str,
        exchange_order_id: str,
        client_order_id: str,
        status: OrderState
    ) -> List[Dict[str, Any]]:
        return [DotMap({
            "id": exchange_order_id,
            "orderHash": "",
            "marketId": "kujira193dzcmy7lwuj4eda3zpwwt9ejal00xva0vawcvhgsyyp5cfh6jyq66wfrf",  # noqa: mock
            "active": "",
            "subaccountId": "",  # noqa: mock
            "executionType": "",
            "orderType": "LIMIT",
            "price": "0.616",
            "triggerPrice": "",
            "quantity": "0.24777",
            "filledQuantity": "",
            "state": KujiraOrderStatus.from_hummingbot(status).name,
            "createdAt": timestamp,
            "updatedAt": "",
            "direction": "BUY"
        })]

    def get_clob_ticker_response(
        self,
        trading_pair: str,
        last_traded_price: Decimal
    ) -> Dict[str, Any]:
        market = (
            self.configure_gateway_get_clob_markets_response()
        ).markets[trading_pair]

        return {
            "KUJI-USK": {  # noqa: mock
                "market": market,
                "ticker": {
                    "price": "0.641"
                },
                "price": "0.641",
                "timestamp": 1694631135095
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

    @staticmethod
    def configure_gateway_get_clob_markets_response():
        return DotMap({
            "network": "mainnet",
            "timestamp": 1694561843115,
            "latency": 0.001,
            "markets": {
                "KUJI-USK": {  # noqa: mock
                    "id": "kujira193dzcmy7lwuj4eda3zpwwt9ejal00xva0vawcvhgsyyp5cfh6jyq66wfrf",  # noqa: mock
                    "name": "KUJI/USK",  # noqa: mock
                    "baseToken": {
                        "id": "ukuji",  # noqa: mock
                        "name": "KUJI",  # noqa: mock
                        "symbol": "KUJI",  # noqa: mock
                        "decimals": 6
                    },
                    "quoteToken": {
                        "id": "factory/kujira1qk00h5atutpsv900x202pxx42npjr9thg58dnqpa72f2p7m2luase444a7/uusk",
                        # noqa: mock
                        "name": "USK",
                        "symbol": "USK",
                        "decimals": 6
                    },
                    "precision": 3,
                    "minimumOrderSize": "0.001",
                    "minimumPriceIncrement": "0.001",
                    "minimumBaseAmountIncrement": "0.001",
                    "minimumQuoteAmountIncrement": "0.001",
                    "fees": {
                        "maker": "0.075",
                        "taker": "0.15",
                        "serviceProvider": "0"
                    },
                    "deprecated": False,
                    "connectorMarket": {
                        "address": "kujira193dzcmy7lwuj4eda3zpwwt9ejal00xva0vawcvhgsyyp5cfh6jyq66wfrf",  # noqa: mock
                        "denoms": [  # noqa: mock
                            {
                                "reference": "ukuji",  # noqa: mock
                                "decimals": 6,
                                "symbol": "KUJI"  # noqa: mock
                            },
                            {
                                "reference": "factory/kujira1qk00h5atutpsv900x202pxx42npjr9thg58dnqpa72f2p7m2luase444a7/uusk",
                                # noqa: mock
                                "decimals": 6,
                                "symbol": "USK"
                            }
                        ],
                        "precision": {
                            "decimal_places": 3
                        },
                        "decimalDelta": 0,
                        "multiswap": True,  # noqa: mock
                        "pool": "kujira1g9xcvvh48jlckgzw8ajl6dkvhsuqgsx2g8u3v0a6fx69h7f8hffqaqu36t",  # noqa: mock
                        "calc": "kujira1e6fjnq7q20sh9cca76wdkfg69esha5zn53jjewrtjgm4nktk824stzyysu"  # noqa: mock
                    }
                }
            }
        }, _dynamic=False)

    def configure_gateway_get_balances_response(self):
        return {
            "balances": {
                "USK": "3.522325",
                "axlUSDC": "1.999921",
                "KUJI": "6.355439"
            }
        }

    def exchange_symbol_for_tokens(
        self,
        base_token: str,
        quote_token: str
    ) -> str:
        return f"{base_token}-{quote_token}"

    @patch("hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.ping_gateway")
    def test_gateway_ping_gateway(self, *_args):
        self.data_source._gateway.ping_gateway.return_value = True

        result = self.async_run_with_timeout(
            coro=self.data_source._gateway_ping_gateway()
        )

        expected = True

        self.assertEqual(expected, result)

    @patch("hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.ping_gateway")
    def test_check_network_status_with_gateway_connected(self, *_args):
        self.data_source._gateway.ping_gateway.return_value = True

        result = self.async_run_with_timeout(
            coro=self.data_source.check_network_status()
        )

        expected = NetworkStatus.CONNECTED

        self.assertEqual(expected, result)

    @patch("hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.ping_gateway")
    def test_check_network_status_with_gateway_not_connected(self, *_args):
        self.data_source._gateway.ping_gateway.return_value = False

        result = self.async_run_with_timeout(
            coro=self.data_source.check_network_status()
        )

        expected = NetworkStatus.NOT_CONNECTED

        self.assertEqual(expected, result)

    @patch("hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.ping_gateway")
    def test_check_network_status_with_gateway_exception(self, *_args):
        self.configure_asyncio_sleep()
        self.data_source._gateway.ping_gateway.side_effect = RuntimeError("Unknown error")

        result = self.async_run_with_timeout(
            coro=self.data_source.check_network_status()
        )

        expected = NetworkStatus.NOT_CONNECTED

        self.assertEqual(expected, result)

    def test_batch_order_cancel(self):
        super().test_batch_order_cancel()

    def test_batch_order_create(self):
        super().test_batch_order_create()

    def test_cancel_order(self):
        super().test_cancel_order()

    def test_cancel_order_transaction_fails(self):
        order = GatewayInFlightOrder(
            client_order_id=self.expected_buy_client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_buy_order_price,
            amount=self.expected_buy_order_size,
            creation_timestamp=self.initial_timestamp,
            exchange_order_id=self.expected_buy_exchange_order_id,
            creation_transaction_hash="someCreationHash",
        )
        self.data_source.gateway_order_tracker.start_tracking_order(order=order)
        self.configure_cancel_order_failure_response()

        result = self.async_run_with_timeout(coro=self.data_source.cancel_order(order=order))

        self.assertEqual(False, result[0])
        self.assertEqual(DotMap({}), result[1])

    def test_check_network_status(self):
        super().test_check_network_status()

    def test_delivers_balance_events(self):
        super().test_delivers_balance_events()

    def test_delivers_order_book_snapshot_events(self):
        pass

    def test_get_account_balances(self):
        super().test_get_account_balances()

    def test_get_all_order_fills(self):
        asyncio.get_event_loop().run_until_complete(
            self.data_source._update_markets()
        )
        creation_transaction_hash = "0x7cb2eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2g81d"  # noqa: mock
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

    def test_get_order_book_snapshot(self):
        self.configure_orderbook_snapshot(
            timestamp=self.initial_timestamp, bids=[[9, 1], [8, 2]], asks=[[11, 3]]
        )
        order_book_snapshot: OrderBookMessage = self.async_run_with_timeout(
            coro=self.data_source.get_order_book_snapshot(trading_pair=self.trading_pair)
        )

        self.assertLess(float(0), order_book_snapshot.timestamp)
        self.assertEqual(2, len(order_book_snapshot.bids))
        self.assertEqual(9, order_book_snapshot.bids[0].price)
        self.assertEqual(1, order_book_snapshot.bids[0].amount)
        self.assertEqual(1, len(order_book_snapshot.asks))
        self.assertEqual(11, order_book_snapshot.asks[0].price)
        self.assertEqual(3, order_book_snapshot.asks[0].amount)

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

    def test_get_order_status_update_with_no_update(self):
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

    def test_update_order_status(self):
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

        self.async_run_with_timeout(
            coro=self.data_source._update_order_status()
        )

    def test_get_symbol_map(self):
        symbol_map = self.async_run_with_timeout(coro=self.data_source.get_symbol_map())

        self.assertIsInstance(symbol_map, bidict)
        self.assertEqual(1, len(symbol_map))
        self.assertIn(self.exchange_trading_pair, symbol_map.inverse)

    def test_get_trading_fees(self):
        super().test_get_trading_fees()

    def test_get_trading_rules(self):
        trading_rules = self.async_run_with_timeout(coro=self.data_source.get_trading_rules())

        self.assertEqual(1, len(trading_rules))
        self.assertIn(self.trading_pair, trading_rules)

        trading_rule: TradingRule = trading_rules[self.trading_pair]

        self.assertEqual(self.trading_pair, trading_rule.trading_pair)
        self.assertEqual(self.expected_min_price_increment, trading_rule.min_price_increment)

    def test_maximum_delay_between_requests_for_snapshot_events(self):
        pass

    def test_minimum_delay_between_requests_for_snapshot_events(self):
        pass

    def test_place_order(self):
        super().test_place_order()

    def test_place_order_transaction_fails(self):
        self.configure_place_order_failure_response()

        order = GatewayInFlightOrder(
            client_order_id=self.expected_buy_client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=self.initial_timestamp,
            price=self.expected_buy_order_price,
            amount=self.expected_buy_order_size,
        )

        with self.assertRaises(Exception):
            self.async_run_with_timeout(
                coro=self.data_source.place_order(order=order)
            )

    def test_generate_hash(self):
        actual = generate_hash("test")

        self.assertIsNotNone(actual)

    def test_convert_hb_trading_pair_to_market_name(self):
        expected = "KUJI/USK"

        actual = convert_hb_trading_pair_to_market_name("KUJI-USK")

        self.assertEqual(expected, actual)

    def test_order_status_methods(self):
        for item in KujiraOrderStatus:
            if item == KujiraOrderStatus.UNKNOWN:
                continue

            hummingbot_status = KujiraOrderStatus.to_hummingbot(item)
            kujira_status = KujiraOrderStatus.from_hummingbot(hummingbot_status)
            kujira_status_from_name = KujiraOrderStatus.from_name(kujira_status.name)

            self.assertEqual(item, kujira_status)
            self.assertEqual(item, kujira_status_from_name)

    def test_order_sides(self):
        for item in KujiraOrderSide:
            hummingbot_side = KujiraOrderSide.to_hummingbot(item)
            kujira_side = KujiraOrderSide.from_hummingbot(hummingbot_side)
            kujira_side_from_name = KujiraOrderSide.from_name(kujira_side.name)

            self.assertEqual(item, kujira_side)
            self.assertEqual(item, kujira_side_from_name)

    def test_order_types(self):
        for item in KujiraOrderType:
            hummingbot_type = KujiraOrderType.to_hummingbot(item)
            kujira_type = KujiraOrderType.from_hummingbot(hummingbot_type)
            kujira_type_from_name = KujiraOrderType.from_name(kujira_type.name)

            self.assertEqual(item, kujira_type)
            self.assertEqual(item, kujira_type_from_name)
