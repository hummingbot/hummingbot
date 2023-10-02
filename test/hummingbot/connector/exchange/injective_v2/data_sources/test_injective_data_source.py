import asyncio
import json
import re
from decimal import Decimal
from test.hummingbot.connector.exchange.injective_v2.programmable_query_executor import ProgrammableQueryExecutor
from typing import Awaitable, Optional, Union
from unittest import TestCase
from unittest.mock import patch

from pyinjective.composer import Composer
from pyinjective.core.network import Network
from pyinjective.wallet import Address, PrivateKey

from hummingbot.connector.exchange.injective_v2 import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source import (
    InjectiveGranteeDataSource,
)
from hummingbot.connector.exchange.injective_v2.data_sources.injective_vaults_data_source import (
    InjectiveVaultsDataSource,
)
from hummingbot.connector.exchange.injective_v2.injective_market import InjectiveSpotMarket
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import OrderType, TradeType


class InjectiveGranteeDataSourceTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all")
    def setUp(self, _) -> None:
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
        self.query_executor._derivative_markets_responses.put_nowait([])

        market_info = self._inj_usdt_market_info()
        inj_usdt_market: InjectiveSpotMarket = self.async_run_with_timeout(
            self.data_source.spot_market_info_for_id(market_info["marketId"])
        )
        inj_token = inj_usdt_market.base_token
        usdt_token = inj_usdt_market.quote_token

        self.assertEqual(market_info["marketId"], inj_usdt_market.market_id)
        self.assertEqual(market_info, inj_usdt_market.market_info)
        self.assertEqual(f"{inj_token.unique_symbol}-{usdt_token.unique_symbol}", inj_usdt_market.trading_pair())
        self.assertEqual(market_info["baseDenom"], inj_token.denom)
        self.assertEqual(market_info["baseTokenMeta"]["symbol"], inj_token.symbol)
        self.assertEqual(inj_token.symbol, inj_token.unique_symbol)
        self.assertEqual(market_info["baseTokenMeta"]["name"], inj_token.name)
        self.assertEqual(market_info["baseTokenMeta"]["decimals"], inj_token.decimals)
        self.assertEqual(market_info["quoteDenom"], usdt_token.denom)
        self.assertEqual(market_info["quoteTokenMeta"]["symbol"], usdt_token.symbol)
        self.assertEqual(usdt_token.symbol, usdt_token.unique_symbol)
        self.assertEqual(market_info["quoteTokenMeta"]["name"], usdt_token.name)
        self.assertEqual(market_info["quoteTokenMeta"]["decimals"], usdt_token.decimals)

        market_info = self._usdc_solana_usdc_eth_market_info()
        usdc_solana_usdc_eth_market: InjectiveSpotMarket = self.async_run_with_timeout(
            self.data_source.spot_market_info_for_id(market_info["marketId"])
        )
        usdc_solana_token = usdc_solana_usdc_eth_market.base_token
        usdc_eth_token = usdc_solana_usdc_eth_market.quote_token

        self.assertEqual(market_info["marketId"], usdc_solana_usdc_eth_market.market_id)
        self.assertEqual(market_info, usdc_solana_usdc_eth_market.market_info)
        self.assertEqual(f"{usdc_solana_token.unique_symbol}-{usdc_eth_token.unique_symbol}", usdc_solana_usdc_eth_market.trading_pair())
        self.assertEqual(market_info["baseDenom"], usdc_solana_token.denom)
        self.assertEqual(market_info["baseTokenMeta"]["symbol"], usdc_solana_token.symbol)
        self.assertEqual(market_info["ticker"].split("/")[0], usdc_solana_token.unique_symbol)
        self.assertEqual(market_info["baseTokenMeta"]["name"], usdc_solana_token.name)
        self.assertEqual(market_info["baseTokenMeta"]["decimals"], usdc_solana_token.decimals)
        self.assertEqual(market_info["quoteDenom"], usdc_eth_token.denom)
        self.assertEqual(market_info["quoteTokenMeta"]["symbol"], usdc_eth_token.symbol)
        self.assertEqual(usdc_eth_token.name, usdc_eth_token.unique_symbol)
        self.assertEqual(market_info["quoteTokenMeta"]["name"], usdc_eth_token.name)
        self.assertEqual(market_info["quoteTokenMeta"]["decimals"], usdc_eth_token.decimals)

    def test_markets_initialization_generates_unique_trading_pairs_for_tokens_with_same_symbol(self):
        spot_markets_response = self._spot_markets_response()
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._derivative_markets_responses.put_nowait([])

        inj_usdt_trading_pair = self.async_run_with_timeout(
            self.data_source.trading_pair_for_market(market_id=self._inj_usdt_market_info()["marketId"])
        )
        self.assertEqual("INJ-USDT", inj_usdt_trading_pair)
        usdt_usdc_trading_pair = self.async_run_with_timeout(
            self.data_source.trading_pair_for_market(market_id=self._usdt_usdc_market_info()["marketId"])
        )
        self.assertEqual("USDT-USDC", usdt_usdc_trading_pair)
        usdt_usdc_eth_trading_pair = self.async_run_with_timeout(
            self.data_source.trading_pair_for_market(market_id=self._usdt_usdc_eth_market_info()["marketId"])
        )
        self.assertEqual("USDT-USC Coin (Wormhole from Ethereum)", usdt_usdc_eth_trading_pair)
        usdc_solana_usdc_eth_trading_pair = self.async_run_with_timeout(
            self.data_source.trading_pair_for_market(market_id=self._usdc_solana_usdc_eth_market_info()["marketId"])
        )
        self.assertEqual("USDCso-USC Coin (Wormhole from Ethereum)", usdc_solana_usdc_eth_trading_pair)

    def test_markets_initialization_adds_different_tokens_having_same_symbol(self):
        spot_markets_response = self._spot_markets_response()
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._derivative_markets_responses.put_nowait([])

        self.async_run_with_timeout(self.data_source.update_markets())

        inj_usdt_market_info = self._inj_usdt_market_info()
        self.assertIn(inj_usdt_market_info["baseDenom"], self.data_source._tokens_map)
        self.assertEqual(
            inj_usdt_market_info["baseDenom"],
            self.data_source._token_symbol_symbol_and_denom_map[inj_usdt_market_info["baseTokenMeta"]["symbol"]]
        )
        self.assertIn(inj_usdt_market_info["quoteDenom"], self.data_source._tokens_map)
        self.assertEqual(
            inj_usdt_market_info["quoteDenom"],
            self.data_source._token_symbol_symbol_and_denom_map[inj_usdt_market_info["quoteTokenMeta"]["symbol"]]
        )

        usdt_usdc_market_info = self._usdt_usdc_market_info()
        self.assertIn(usdt_usdc_market_info["quoteDenom"], self.data_source._tokens_map)
        self.assertEqual(
            usdt_usdc_market_info["quoteDenom"],
            self.data_source._token_symbol_symbol_and_denom_map[usdt_usdc_market_info["quoteTokenMeta"]["symbol"]]
        )

        usdt_usdc_eth_market_info = self._usdt_usdc_eth_market_info()
        self.assertIn(usdt_usdc_eth_market_info["quoteDenom"], self.data_source._tokens_map)
        self.assertEqual(
            usdt_usdc_eth_market_info["quoteDenom"],
            self.data_source._token_symbol_symbol_and_denom_map[usdt_usdc_eth_market_info["quoteTokenMeta"]["name"]]
        )

        usdc_solana_usdc_eth_market_info = self._usdc_solana_usdc_eth_market_info()
        expected_usdc_solana_unique_symbol = usdc_solana_usdc_eth_market_info["ticker"].split("/")[0]
        self.assertIn(usdc_solana_usdc_eth_market_info["baseDenom"], self.data_source._tokens_map)
        self.assertEqual(
            usdc_solana_usdc_eth_market_info["baseDenom"],
            self.data_source._token_symbol_symbol_and_denom_map[expected_usdc_solana_unique_symbol]
        )

    def test_markets_initialization_creates_one_instance_per_token(self):
        spot_markets_response = self._spot_markets_response()
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._derivative_markets_responses.put_nowait([])

        inj_usdt_market: InjectiveSpotMarket = self.async_run_with_timeout(
            self.data_source.spot_market_info_for_id(self._inj_usdt_market_info()["marketId"])
        )
        usdt_usdc_market: InjectiveSpotMarket = self.async_run_with_timeout(
            self.data_source.spot_market_info_for_id(self._usdt_usdc_market_info()["marketId"])
        )
        usdt_usdc_eth_market: InjectiveSpotMarket = self.async_run_with_timeout(
            self.data_source.spot_market_info_for_id(self._usdt_usdc_eth_market_info()["marketId"])
        )
        usdc_solana_usdc_eth_market: InjectiveSpotMarket = self.async_run_with_timeout(
            self.data_source.spot_market_info_for_id(self._usdc_solana_usdc_eth_market_info()["marketId"])
        )

        self.assertEqual(inj_usdt_market.quote_token, usdt_usdc_market.base_token)
        self.assertEqual(inj_usdt_market.quote_token, usdt_usdc_eth_market.base_token)

        self.assertNotEqual(usdt_usdc_market.quote_token, usdt_usdc_eth_market.quote_token)
        self.assertNotEqual(usdt_usdc_market.quote_token, usdc_solana_usdc_eth_market.base_token)

        self.assertEqual(usdt_usdc_eth_market.quote_token, usdc_solana_usdc_eth_market.quote_token)
        self.assertNotEqual(usdt_usdc_eth_market.quote_token, usdc_solana_usdc_eth_market.base_token)

    def _spot_markets_response(self):
        return [
            self._inj_usdt_market_info(),
            self._usdt_usdc_market_info(),
            self._usdt_usdc_eth_market_info(),
            self._usdc_solana_usdc_eth_market_info()
        ]

    def _usdc_solana_usdc_eth_market_info(self):
        return {
            "marketId": "0xb825e2e4dbe369446e454e21c16e041cbc4d95d73f025c369f92210e82d2106f",  # noqa: mock
            "marketStatus": "active",
            "ticker": "USDCso/USDCet",
            "baseDenom": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj12pwnhtv7yat2s30xuf4gdk9qm85v4j3e60dgvu",  # noqa: mock
            "baseTokenMeta": {
                "name": "USD Coin (Wormhole from Solana)",
                "address": "0x0000000000000000000000000000000000000000",
                "symbol": "USDC",
                "logo": "https://static.alchemyapi.io/images/assets/3408.png",
                "decimals": 6,
                "updatedAt": "1685371052880",
            },
            "quoteDenom": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1q6zlut7gtkzknkk773jecujwsdkgq882akqksk",  # noqa: mock
            "quoteTokenMeta": {
                "name": "USC Coin (Wormhole from Ethereum)",
                "address": "0x0000000000000000000000000000000000000000",
                "symbol": "USDC",
                "logo": "https://static.alchemyapi.io/images/assets/3408.png",
                "decimals": 6,
                "updatedAt": "1685371052880",
            },
            "makerFeeRate": "-0.0001",
            "takerFeeRate": "0.001",
            "serviceProviderFee": "0.4",
            "minPriceTickSize": "0.0001",
            "minQuantityTickSize": "100",
        }

    def _usdt_usdc_eth_market_info(self):
        return {
            "marketId": "0xda0bb7a7d8361d17a9d2327ed161748f33ecbf02738b45a7dd1d812735d1531c",  # noqa: mock
            "marketStatus": "active",
            "ticker": "USDT/USDC",
            "baseDenom": "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "baseTokenMeta": {
                "name": "Tether",
                "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "symbol": "USDT",
                "logo": "https://static.alchemyapi.io/images/assets/825.png",
                "decimals": 6,
                "updatedAt": "1685371052879",
            },
            "quoteDenom": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1q6zlut7gtkzknkk773jecujwsdkgq882akqksk",  # noqa: mock
            "quoteTokenMeta": {
                "name": "USC Coin (Wormhole from Ethereum)",
                "address": "0x0000000000000000000000000000000000000000",
                "symbol": "USDC",
                "logo": "https://static.alchemyapi.io/images/assets/3408.png",
                "decimals": 6,
                "updatedAt": "1685371052880"
            },
            "makerFeeRate": "-0.0001",
            "takerFeeRate": "0.001",
            "serviceProviderFee": "0.4",
            "minPriceTickSize": "0.0001",
            "minQuantityTickSize": "100",
        }

    def _usdt_usdc_market_info(self):
        return {
            "marketId": "0x8b1a4d3e8f6b559e30e40922ee3662dd78edf7042330d4d620d188699d1a9715",  # noqa: mock
            "marketStatus": "active",
            "ticker": "USDT/USDC",
            "baseDenom": "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "baseTokenMeta": {
                "name": "Tether",
                "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "symbol": "USDT",
                "logo": "https://static.alchemyapi.io/images/assets/825.png",
                "decimals": 6,
                "updatedAt": "1685371052879"
            },
            "quoteDenom": "peggy0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "quoteTokenMeta": {
                "name": "USD Coin",
                "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "symbol": "USDC",
                "logo": "https://static.alchemyapi.io/images/assets/3408.png",
                "decimals": 6,
                "updatedAt": "1685371052879"
            },
            "makerFeeRate": "0.001",
            "takerFeeRate": "0.002",
            "serviceProviderFee": "0.4",
            "minPriceTickSize": "0.0001",
            "minQuantityTickSize": "100",
        }

    def _inj_usdt_market_info(self):
        return {
            "marketId": "0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0",  # noqa: mock
            "marketStatus": "active",
            "ticker": "INJ/USDT",
            "baseDenom": "inj",
            "baseTokenMeta": {
                "name": "Injective Protocol",
                "address": "0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",
                "symbol": "INJ",
                "logo": "https://static.alchemyapi.io/images/assets/7226.png",
                "decimals": 18,
                "updatedAt": "1685371052879"
            },
            "quoteDenom": "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "quoteTokenMeta": {
                "name": "Tether",
                "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "symbol": "USDT",
                "logo": "https://static.alchemyapi.io/images/assets/825.png",
                "decimals": 6,
                "updatedAt": "1685371052879"
            },
            "makerFeeRate": "-0.0001",
            "takerFeeRate": "0.001",
            "serviceProviderFee": "0.4",
            "minPriceTickSize": "0.000000000000001",
            "minQuantityTickSize": "1000000000000000"
        }


class InjectiveVaultsDataSourceTests(TestCase):

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all")
    def setUp(self, _) -> None:
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
        self.query_executor._derivative_markets_responses.put_nowait([])

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

        messages, spot_order_hashes, derivative_order_hashes = self.async_run_with_timeout(
            self.data_source._order_creation_messages(
                spot_orders_to_create=orders,
                derivative_orders_to_create=[],
            )
        )

        pub_key = self._grantee_private_key.to_public_key()
        address = pub_key.to_address()

        self.assertEqual(0, len(spot_order_hashes))
        self.assertEqual(address.to_acc_bech32(), messages[0].sender)
        self.assertEqual(self._vault_address, messages[0].contract)

        market = self._inj_usdt_market_info()
        base_token_decimals = market["baseTokenMeta"]["decimals"]
        quote_token_meta = market["quoteTokenMeta"]["decimals"]
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
                                        "market_id": market["marketId"],
                                        "order_info": {
                                            "fee_recipient": self._vault_address,
                                            "subaccount_id": "1",
                                            "price": f"{message_price:f}",
                                            "quantity": f"{message_quantity:f}"
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
        self.query_executor._derivative_markets_responses.put_nowait([])
        market = self._inj_usdt_market_info()

        orders_data = []
        composer = asyncio.get_event_loop().run_until_complete(self.data_source.composer())
        order_data = composer.OrderData(
            market_id=market["marketId"],
            subaccount_id="1",
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
                                        "market_id": market["marketId"],
                                        "subaccount_id": "1",
                                        "order_hash": "0xba954bc613a81cd712b9ec0a3afbfc94206cf2ff8c60d1868e031d59ea82bf27",  # noqa: mock"
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
        return [
            self._inj_usdt_market_info(),
        ]

    def _inj_usdt_market_info(self):
        return {
            "marketId": "0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe",  # noqa: mock
            "marketStatus": "active",
            "ticker": "INJ/USDT",
            "baseDenom": "inj",
            "baseTokenMeta": {
                "name": "Injective Protocol",
                "address": "0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",
                "symbol": "INJ",
                "logo": "https://static.alchemyapi.io/images/assets/7226.png",
                "decimals": 18,
                "updatedAt": "1685371052879"
            },
            "quoteDenom": "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "quoteTokenMeta": {
                "name": "Tether",
                "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "symbol": "USDT",
                "logo": "https://static.alchemyapi.io/images/assets/825.png",
                "decimals": 6,
                "updatedAt": "1685371052879"
            },
            "makerFeeRate": "-0.0001",
            "takerFeeRate": "0.001",
            "serviceProviderFee": "0.4",
            "minPriceTickSize": "0.000000000000001",
            "minQuantityTickSize": "1000000000000000"
        }
