import asyncio
import json
import re
from decimal import Decimal
from test.hummingbot.connector.exchange.injective_v2.programmable_query_executor import ProgrammableQueryExecutor
from typing import Awaitable, Optional, Union
from unittest import TestCase
from unittest.mock import patch

from pyinjective.composer import Composer
from pyinjective.core.market import SpotMarket
from pyinjective.core.network import Network
from pyinjective.core.token import Token
from pyinjective.wallet import Address, PrivateKey

from hummingbot.connector.exchange.injective_v2 import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source import (
    InjectiveGranteeDataSource,
)
from hummingbot.connector.exchange.injective_v2.data_sources.injective_read_only_data_source import (
    InjectiveReadOnlyDataSource,
)
from hummingbot.connector.exchange.injective_v2.data_sources.injective_vaults_data_source import (
    InjectiveVaultsDataSource,
)
from hummingbot.connector.exchange.injective_v2.injective_market import InjectiveSpotMarket
from hummingbot.connector.exchange.injective_v2.injective_v2_utils import (
    InjectiveMessageBasedTransactionFeeCalculatorMode,
)
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import OrderType, TradeType


class InjectiveGranteeDataSourceTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0
    usdt_usdc_market_id = "0x8b1a4d3e8f6b559e30e40922ee3662dd78edf7042330d4d620d188699d1a9715"  # noqa: mock
    inj_usdt_market_id = "0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe"  # noqa: mock

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all")
    def setUp(self, _) -> None:
        self._initialize_timeout_height_sync_task = patch(
            "hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source"
            ".AsyncClient._initialize_timeout_height_sync_task"
        )
        self._initialize_timeout_height_sync_task.start()
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.async_tasks = []
        asyncio.set_event_loop(self.async_loop)

        _, grantee_private_key = PrivateKey.generate()
        _, granter_private_key = PrivateKey.generate()

        self.data_source = InjectiveGranteeDataSource(
            private_key=grantee_private_key.to_hex(),
            subaccount_index=0,
            granter_address=Address(bytes.fromhex(granter_private_key.to_public_key().to_hex())).to_acc_bech32(),
            granter_subaccount_index=0,
            network=Network.testnet(node="sentry"),
            rate_limits=CONSTANTS.PUBLIC_NODE_RATE_LIMITS,
            fee_calculator_mode=InjectiveMessageBasedTransactionFeeCalculatorMode(),
        )

        self.query_executor = ProgrammableQueryExecutor()
        self.data_source._query_executor = self.query_executor

        self.log_records = []
        self._logs_event: Optional[asyncio.Event] = None
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.async_run_with_timeout(self.data_source.stop())
        for task in self.async_tasks:
            task.cancel()
        self.async_loop.stop()
        # self.async_loop.close()
        # Since the event loop will change we need to remove the logs event created in the old event loop
        self._logs_event = None
        asyncio.set_event_loop(self._original_async_loop)
        self._initialize_timeout_height_sync_task.stop()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def create_task(self, coroutine: Awaitable) -> asyncio.Task:
        task = self.async_loop.create_task(coroutine)
        self.async_tasks.append(task)
        return task

    def handle(self, record):
        self.log_records.append(record)
        if self._logs_event is not None:
            self._logs_event.set()

    def is_logged(self, log_level: str, message: Union[str, re.Pattern]) -> bool:
        expression = (
            re.compile(
                f"^{message}$"
                .replace(".", r"\.")
                .replace("?", r"\?")
                .replace("/", r"\/")
                .replace("(", r"\(")
                .replace(")", r"\)")
                .replace("[", r"\[")
                .replace("]", r"\]")
            )
            if isinstance(message, str)
            else message
        )
        return any(
            record.levelname == log_level and expression.match(record.getMessage()) is not None
            for record in self.log_records
        )

    def test_market_and_tokens_construction(self):
        spot_markets_response = self._spot_markets_response()
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._derivative_markets_responses.put_nowait({})
        tokens = dict()
        for market in spot_markets_response.values():
            tokens[market.base_token.denom] = market.base_token
            tokens[market.quote_token.denom] = market.quote_token
        self.query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in tokens.values()}
        )

        market_info = self._inj_usdt_market_info()
        inj_usdt_market: InjectiveSpotMarket = self.async_run_with_timeout(
            self.data_source.spot_market_info_for_id(market_info.id)
        )
        inj_token = inj_usdt_market.base_token
        usdt_token = inj_usdt_market.quote_token

        self.assertEqual(market_info.id, inj_usdt_market.market_id)
        self.assertEqual(market_info, inj_usdt_market.native_market)
        self.assertEqual(f"{inj_token.unique_symbol}-{usdt_token.unique_symbol}", inj_usdt_market.trading_pair())
        self.assertEqual(market_info.base_token.denom, inj_token.denom)
        self.assertEqual(market_info.base_token.symbol, inj_token.symbol)
        self.assertEqual(inj_token.symbol, inj_token.unique_symbol)
        self.assertEqual(market_info.base_token.name, inj_token.name)
        self.assertEqual(market_info.base_token.decimals, inj_token.decimals)
        self.assertEqual(market_info.quote_token.denom, usdt_token.denom)
        self.assertEqual(market_info.quote_token.symbol, usdt_token.symbol)
        self.assertEqual(usdt_token.symbol, usdt_token.unique_symbol)
        self.assertEqual(market_info.quote_token.name, usdt_token.name)
        self.assertEqual(market_info.quote_token.decimals, usdt_token.decimals)

    def _spot_markets_response(self):
        inj_usdt_market = self._inj_usdt_market_info()
        usdt_usdc_market = self._usdt_usdc_market_info()

        return {
            inj_usdt_market.id: inj_usdt_market,
            usdt_usdc_market.id: usdt_usdc_market,
        }

    def _usdt_usdc_market_info(self):
        base_native_token = Token(
            name="Tether",
            symbol="USDT",
            denom="peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
            address="0xdAC17F958D2ee523a2206206994597C13D831ec7",  # noqa: mock
            decimals=6,
            logo="https://static.alchemyapi.io/images/assets/825.png",
            updated=1685371052879,
        )
        quote_native_token = Token(
            name="USD Coin",
            symbol="USDC",
            denom="peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5",  # noqa: mock
            address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # noqa: mock
            decimals=6,
            logo="https://static.alchemyapi.io/images/assets/3408.png",
            updated=1687190809716,
        )

        native_market = SpotMarket(
            id=self.usdt_usdc_market_id,
            status="active",
            ticker="USDT/USDC",
            base_token=base_native_token,
            quote_token=quote_native_token,
            maker_fee_rate=Decimal("0.001"),
            taker_fee_rate=Decimal("0.002"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=Decimal("0.0001"),
            min_quantity_tick_size=Decimal("100"),
            min_notional=Decimal("1000000"),
        )

        return native_market

    def _inj_usdt_market_info(self):
        base_native_token = Token(
            name="Injective Protocol",
            symbol="INJ",
            denom="inj",
            address="0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",  # noqa: mock
            decimals=18,
            logo="https://static.alchemyapi.io/images/assets/7226.png",
            updated=1687190809715,
        )
        quote_native_token = Token(
            name="Tether",
            symbol="USDT",
            denom="peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
            address="0xdAC17F958D2ee523a2206206994597C13D831ec7",  # noqa: mock
            decimals=6,
            logo="https://static.alchemyapi.io/images/assets/825.png",
            updated=1685371052879,
        )

        native_market = SpotMarket(
            id=self.inj_usdt_market_id,
            status="active",
            ticker="INJ/USDT",
            base_token=base_native_token,
            quote_token=quote_native_token,
            maker_fee_rate=Decimal("-0.0001"),
            taker_fee_rate=Decimal("0.001"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=Decimal("0.000000000000001"),
            min_quantity_tick_size=Decimal("1000000000000000"),
            min_notional=Decimal("1000000"),
        )

        return native_market


class InjectiveVaultsDataSourceTests(TestCase):

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all")
    def setUp(self, _) -> None:
        self._initialize_timeout_height_sync_task = patch(
            "hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source"
            ".AsyncClient._initialize_timeout_height_sync_task"
        )
        self._initialize_timeout_height_sync_task.start()
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.async_tasks = []
        asyncio.set_event_loop(self.async_loop)

        _, self._grantee_private_key = PrivateKey.generate()
        self._vault_address = "inj1zlwdkv49rmsug0pnwu6fmwnl267lfr34yvhwgp"

        self.data_source = InjectiveVaultsDataSource(
            private_key=self._grantee_private_key.to_hex(),
            subaccount_index=0,
            vault_contract_address=self._vault_address,
            vault_subaccount_index=1,
            network=Network.testnet(node="sentry"),
            use_secure_connection=True,
            rate_limits=CONSTANTS.PUBLIC_NODE_RATE_LIMITS,
            fee_calculator_mode=InjectiveMessageBasedTransactionFeeCalculatorMode(),
        )

        self.query_executor = ProgrammableQueryExecutor()
        self.data_source._query_executor = self.query_executor

        self.data_source._composer = Composer(network=self.data_source.network_name)

    def tearDown(self) -> None:
        self.async_run_with_timeout(self.data_source.stop())
        for task in self.async_tasks:
            task.cancel()
        self.async_loop.stop()
        # self.async_loop.close()
        # Since the event loop will change we need to remove the logs event created in the old event loop
        self._logs_event = None
        asyncio.set_event_loop(self._original_async_loop)
        self._initialize_timeout_height_sync_task.stop()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def create_task(self, coroutine: Awaitable) -> asyncio.Task:
        task = self.async_loop.create_task(coroutine)
        self.async_tasks.append(task)
        return task

    def test_order_creation_message_generation(self):
        spot_markets_response = self._spot_markets_response()
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._derivative_markets_responses.put_nowait({})
        market = self._inj_usdt_market_info()
        self.query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )

        orders = []
        order = GatewayInFlightOrder(
            client_order_id="someOrderIDCreate",
            trading_pair="INJ-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=123123123,
            amount=Decimal("10"),
            price=Decimal("100"),
        )
        orders.append(order)

        messages = self.async_run_with_timeout(
            self.data_source._order_creation_messages(
                spot_orders_to_create=orders,
                derivative_orders_to_create=[],
            )
        )

        pub_key = self._grantee_private_key.to_public_key()
        address = pub_key.to_address()

        self.assertEqual(address.to_acc_bech32(), messages[0].sender)
        self.assertEqual(self._vault_address, messages[0].contract)

        market = self._inj_usdt_market_info()
        base_token_decimals = market.base_token.decimals
        quote_token_meta = market.quote_token.decimals
        message_data = json.loads(messages[0].msg.decode())

        message_price = (order.price * Decimal(f"1e{quote_token_meta-base_token_decimals}")).normalize()
        message_quantity = (order.amount * Decimal(f"1e{base_token_decimals}")).normalize()

        expected_data = {
            "admin_execute_message": {
                "injective_message": {
                    "custom": {
                        "route": "exchange",
                        "msg_data": {
                            "batch_update_orders": {
                                "sender": self._vault_address,
                                "spot_orders_to_create": [
                                    {
                                        "market_id": market.id,
                                        "order_info": {
                                            "fee_recipient": self._vault_address,
                                            "subaccount_id": "1",
                                            "price": f"{message_price:f}",
                                            "quantity": f"{message_quantity:f}",
                                            "cid": order.client_order_id,
                                        },
                                        "order_type": 1,
                                        "trigger_price": "0",
                                    }
                                ],
                                "spot_market_ids_to_cancel_all": [],
                                "derivative_market_ids_to_cancel_all": [],
                                "spot_orders_to_cancel": [],
                                "derivative_orders_to_cancel": [],
                                "derivative_orders_to_create": [],
                                "binary_options_market_ids_to_cancel_all": [],
                                "binary_options_orders_to_cancel": [],
                                "binary_options_orders_to_create": [],
                            }
                        }
                    }
                }
            }
        }

        self.assertEqual(expected_data, message_data)

    def test_order_cancel_message_generation(self):
        spot_markets_response = self._spot_markets_response()
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._derivative_markets_responses.put_nowait({})
        market = self._inj_usdt_market_info()
        self.query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )

        orders_data = []
        composer = asyncio.get_event_loop().run_until_complete(self.data_source.composer())
        order_data = composer.OrderData(
            market_id=market.id,
            subaccount_id="1",
            cid="client order id",
            order_hash="0xba954bc613a81cd712b9ec0a3afbfc94206cf2ff8c60d1868e031d59ea82bf27",  # noqa: mock"
            order_direction="buy",
            order_type="limit",
        )
        orders_data.append(order_data)

        message = self.async_run_with_timeout(
            self.data_source._order_cancel_message(
                spot_orders_to_cancel=orders_data,
                derivative_orders_to_cancel=[],
            )
        )

        pub_key = self._grantee_private_key.to_public_key()
        address = pub_key.to_address()

        self.assertEqual(address.to_acc_bech32(), message.sender)
        self.assertEqual(self._vault_address, message.contract)

        message_data = json.loads(message.msg.decode())

        expected_data = {
            "admin_execute_message": {
                "injective_message": {
                    "custom": {
                        "route": "exchange",
                        "msg_data": {
                            "batch_update_orders": {
                                "sender": self._vault_address,
                                "spot_orders_to_create": [],
                                "spot_market_ids_to_cancel_all": [],
                                "derivative_market_ids_to_cancel_all": [],
                                "spot_orders_to_cancel": [
                                    {
                                        "market_id": market.id,
                                        "subaccount_id": "1",
                                        "order_hash": "0xba954bc613a81cd712b9ec0a3afbfc94206cf2ff8c60d1868e031d59ea82bf27",  # noqa: mock"
                                        "cid": "client order id",
                                        "order_mask": 74,
                                    }
                                ],
                                "derivative_orders_to_cancel": [],
                                "derivative_orders_to_create": [],
                                "binary_options_market_ids_to_cancel_all": [],
                                "binary_options_orders_to_cancel": [],
                                "binary_options_orders_to_create": [],
                            }
                        }
                    }
                }
            }
        }

        self.assertEqual(expected_data, message_data)

    def _spot_markets_response(self):
        market = self._inj_usdt_market_info()
        return {market.id: market}

    def _inj_usdt_market_info(self):
        base_native_token = Token(
            name="Injective Protocol",
            symbol="INJ",
            denom="inj",
            address="0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",  # noqa: mock
            decimals=18,
            logo="https://static.alchemyapi.io/images/assets/7226.png",
            updated=1687190809715,
        )
        quote_native_token = Token(
            name="Tether",
            symbol="USDT",
            denom="peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5",  # noqa: mock
            address="0x0000000000000000000000000000000000000000",  # noqa: mock
            decimals=6,
            logo="https://static.alchemyapi.io/images/assets/825.png",
            updated=1687190809716,
        )

        native_market = SpotMarket(
            id="0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe",  # noqa: mock
            status="active",
            ticker="INJ/USDT",
            base_token=base_native_token,
            quote_token=quote_native_token,
            maker_fee_rate=Decimal("-0.0001"),
            taker_fee_rate=Decimal("0.001"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=Decimal("0.000000000000001"),
            min_quantity_tick_size=Decimal("1000000000000000"),
            min_notional=Decimal("1000000"),
        )

        return native_market


class InjectiveReadOnlyDataSourceTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0
    usdt_usdc_market_id = "0x8b1a4d3e8f6b559e30e40922ee3662dd78edf7042330d4d620d188699d1a9715"  # noqa: mock
    inj_usdt_market_id = "0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe"  # noqa: mock

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all")
    def setUp(self, _) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.async_tasks = []
        asyncio.set_event_loop(self.async_loop)

        _, grantee_private_key = PrivateKey.generate()
        _, granter_private_key = PrivateKey.generate()

        self.data_source = InjectiveReadOnlyDataSource(
            network=Network.testnet(node="sentry"),
            rate_limits=CONSTANTS.PUBLIC_NODE_RATE_LIMITS,
        )

        self.query_executor = ProgrammableQueryExecutor()
        self.data_source._query_executor = self.query_executor

        self.log_records = []
        self._logs_event: Optional[asyncio.Event] = None
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.async_run_with_timeout(self.data_source.stop())
        for task in self.async_tasks:
            task.cancel()
        self.async_loop.stop()
        # self.async_loop.close()
        # Since the event loop will change we need to remove the logs event created in the old event loop
        self._logs_event = None
        asyncio.set_event_loop(self._original_async_loop)
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def create_task(self, coroutine: Awaitable) -> asyncio.Task:
        task = self.async_loop.create_task(coroutine)
        self.async_tasks.append(task)
        return task

    def handle(self, record):
        self.log_records.append(record)
        if self._logs_event is not None:
            self._logs_event.set()

    def test_order_cancel_message_generation(self):
        self.assertTrue(self.data_source._uses_default_portfolio_subaccount())
