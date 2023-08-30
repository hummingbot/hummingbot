import asyncio
import re
from decimal import Decimal
from test.hummingbot.connector.exchange.injective_v2.programmable_query_executor import ProgrammableQueryExecutor
from typing import Awaitable, Optional, Union
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict
from pyinjective.wallet import Address, PrivateKey

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.injective_v2.injective_v2_api_order_book_data_source import (
    InjectiveV2APIOrderBookDataSource,
)
from hummingbot.connector.exchange.injective_v2.injective_v2_exchange import InjectiveV2Exchange
from hummingbot.connector.exchange.injective_v2.injective_v2_utils import (
    InjectiveConfigMap,
    InjectiveDelegatedAccountMode,
    InjectiveTestnetNetworkMode,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class InjectiveV2APIOrderBookDataSourceTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "INJ"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.market_id = "0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe"  # noqa: mock

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all")
    def setUp(self, _) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.async_tasks = []
        asyncio.set_event_loop(self.async_loop)

        client_config_map = ClientConfigAdapter(ClientConfigMap())

        _, grantee_private_key = PrivateKey.generate()
        _, granter_private_key = PrivateKey.generate()

        network_config = InjectiveTestnetNetworkMode(testnet_node="sentry")

        account_config = InjectiveDelegatedAccountMode(
            private_key=grantee_private_key.to_hex(),
            subaccount_index=0,
            granter_address=Address(bytes.fromhex(granter_private_key.to_public_key().to_hex())).to_acc_bech32(),
            granter_subaccount_index=0,
        )

        injective_config = InjectiveConfigMap(
            network=network_config,
            account_type=account_config,
        )

        self.connector = InjectiveV2Exchange(
            client_config_map=client_config_map,
            connector_configuration=injective_config,
            trading_pairs=[self.trading_pair],
        )
        self.data_source = InjectiveV2APIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            data_source=self.connector._data_source,
        )

        self.initialize_trading_account_patch = patch(
            "hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source"
            ".InjectiveGranteeDataSource.initialize_trading_account"
        )
        self.initialize_trading_account_patch.start()

        self.query_executor = ProgrammableQueryExecutor()
        self.connector._data_source._query_executor = self.query_executor

        self.log_records = []
        self._logs_event: Optional[asyncio.Event] = None
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.data_source._data_source.logger().setLevel(1)
        self.data_source._data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.market_id: self.trading_pair}))

    def tearDown(self) -> None:
        self.async_run_with_timeout(self.data_source._data_source.stop())
        self.initialize_trading_account_patch.stop()
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

    def test_get_new_order_book_successful(self):
        spot_markets_response = self._spot_markets_response()
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._derivative_markets_responses.put_nowait([])
        base_decimals = spot_markets_response[0]["baseTokenMeta"]["decimals"]
        quote_decimals = spot_markets_response[0]["quoteTokenMeta"]["decimals"]

        order_book_snapshot = {
            "buys": [(Decimal("9487") * Decimal(f"1e{quote_decimals-base_decimals}"),
                      Decimal("336241") * Decimal(f"1e{base_decimals}"),
                      1640001112223)],
            "sells": [(Decimal("9487.5") * Decimal(f"1e{quote_decimals-base_decimals}"),
                      Decimal("522147") * Decimal(f"1e{base_decimals}"),
                      1640001112224)],
            "sequence": 512,
            "timestamp": 1650001112223,
        }

        self.query_executor._spot_order_book_responses.put_nowait(order_book_snapshot)

        order_book = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        expected_update_id = order_book_snapshot["sequence"]

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(9487, bids[0].price)
        self.assertEqual(336241, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(9487.5, asks[0].price)
        self.assertEqual(522147, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_trades(self.async_loop, msg_queue))

    def test_listen_for_trades_logs_exception(self):
        spot_markets_response = self._spot_markets_response()
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._derivative_markets_responses.put_nowait([])

        self.query_executor._public_spot_trade_updates.put_nowait({})
        trade_data = {
            "orderHash": "0x070e2eb3d361c8b26eae510f481bed513a1fb89c0869463a387cfa7995a27043",  # noqa: mock
            "subaccountId": "0x7998ca45575408f8b4fa354fe615abf3435cf1a7000000000000000000000000",  # noqa: mock
            "marketId": self.market_id,
            "tradeExecutionType": "limitMatchRestingOrder",
            "tradeDirection": "sell",
            "price": {
                "price": "0.000000000007701",
                "quantity": "324600000000000000000",
                "timestamp": "1687878089569"
            },
            "fee": "-249974.46",
            "executedAt": "1687878089569",
            "feeRecipient": "inj10xvv532h2sy03d86x487v9dt7dp4eud8fe2qv5",  # noqa: mock
            "tradeId": "37120120_60_0",
            "executionSide": "maker"
        }
        self.query_executor._public_spot_trade_updates.put_nowait(trade_data)

        self.async_run_with_timeout(self.data_source.listen_for_subscriptions(), timeout=2)

        msg_queue = asyncio.Queue()
        self.create_task(self.data_source.listen_for_trades(self.async_loop, msg_queue))
        self.async_run_with_timeout(msg_queue.get())

        self.assertTrue(
            self.is_logged(
                "WARNING", re.compile(r"^Invalid public spot trade event format \(.*")
            )
        )

    def test_listen_for_trades_successful(self):
        spot_markets_response = self._spot_markets_response()
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._derivative_markets_responses.put_nowait([])
        base_decimals = spot_markets_response[0]["baseTokenMeta"]["decimals"]
        quote_decimals = spot_markets_response[0]["quoteTokenMeta"]["decimals"]

        trade_data = {
            "orderHash": "0x070e2eb3d361c8b26eae510f481bed513a1fb89c0869463a387cfa7995a27043",  # noqa: mock
            "subaccountId": "0x7998ca45575408f8b4fa354fe615abf3435cf1a7000000000000000000000000",  # noqa: mock
            "marketId": self.market_id,
            "tradeExecutionType": "limitMatchRestingOrder",
            "tradeDirection": "sell",
            "price": {
                "price": "0.000000000007701",
                "quantity": "324600000000000000000",
                "timestamp": "1687878089569"
            },
            "fee": "-249974.46",
            "executedAt": "1687878089569",
            "feeRecipient": "inj10xvv532h2sy03d86x487v9dt7dp4eud8fe2qv5",  # noqa: mock
            "tradeId": "37120120_60_0",
            "executionSide": "maker"
        }
        self.query_executor._public_spot_trade_updates.put_nowait(trade_data)

        self.async_run_with_timeout(self.data_source.listen_for_subscriptions())

        msg_queue = asyncio.Queue()
        self.create_task(self.data_source.listen_for_trades(self.async_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(trade_data["tradeId"], msg.trade_id)
        self.assertEqual(int(trade_data["executedAt"]) * 1e-3, msg.timestamp)
        expected_price = Decimal(trade_data["price"]["price"]) * Decimal(f"1e{base_decimals-quote_decimals}")
        expected_amount = Decimal(trade_data["price"]["quantity"]) * Decimal(f"1e{-base_decimals}")
        self.assertEqual(expected_amount, msg.content["amount"])
        self.assertEqual(expected_price, msg.content["price"])
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(float(TradeType.SELL.value), msg.content["trade_type"])

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_order_book_diffs(self.async_loop, msg_queue))

    def test_listen_for_order_book_diffs_logs_exception(self):
        spot_markets_response = self._spot_markets_response()
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._derivative_markets_responses.put_nowait([])

        self.query_executor._spot_order_book_updates.put_nowait({})
        order_book_data = {
            "marketId": self.market_id,
            "sequence": "7734169",
            "buys": [
                {
                    "price": "0.000000000007684",
                    "quantity": "4578787000000000000000",
                    "isActive": True,
                    "timestamp": "1687889315683"
                },
                {
                    "price": "0.000000000007685",
                    "quantity": "4412340000000000000000",
                    "isActive": True,
                    "timestamp": "1687889316000"
                }
            ],
            "sells": [
                {
                    "price": "0.000000000007723",
                    "quantity": "3478787000000000000000",
                    "isActive": True,
                    "timestamp": "1687889315683"
                }
            ],
            "updatedAt": "1687889315683",
        }
        self.query_executor._spot_order_book_updates.put_nowait(order_book_data)

        self.async_run_with_timeout(self.data_source.listen_for_subscriptions(), timeout=5)

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.create_task(self.data_source.listen_for_order_book_diffs(self.async_loop, msg_queue))

        self.async_run_with_timeout(msg_queue.get())

        self.assertTrue(
            self.is_logged(
                "WARNING", re.compile(r"^Invalid spot order book event format \(.*")
            )
        )

    @patch("hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source.InjectiveGranteeDataSource._initialize_timeout_height")
    def test_listen_for_order_book_diffs_successful(self, _):
        spot_markets_response = self._spot_markets_response()
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._derivative_markets_responses.put_nowait([])
        base_decimals = spot_markets_response[0]["baseTokenMeta"]["decimals"]
        quote_decimals = spot_markets_response[0]["quoteTokenMeta"]["decimals"]

        order_book_data = {
            "marketId": self.market_id,
            "sequence": "7734169",
            "buys": [
                {
                    "price": "0.000000000007684",
                    "quantity": "4578787000000000000000",
                    "isActive": True,
                    "timestamp": "1687889315683"
                },
                {
                    "price": "0.000000000007685",
                    "quantity": "4412340000000000000000",
                    "isActive": True,
                    "timestamp": "1687889316000"
                }
            ],
            "sells": [
                {
                    "price": "0.000000000007723",
                    "quantity": "3478787000000000000000",
                    "isActive": True,
                    "timestamp": "1687889315683"
                }
            ],
            "updatedAt": "1687889315683",
        }
        self.query_executor._spot_order_book_updates.put_nowait(order_book_data)

        self.async_run_with_timeout(self.data_source.listen_for_subscriptions())

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.create_task(self.data_source.listen_for_order_book_diffs(self.async_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(int(order_book_data["updatedAt"]) * 1e-3, msg.timestamp)
        expected_update_id = int(order_book_data["sequence"])
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        first_bid_price = Decimal(order_book_data["buys"][0]["price"]) * Decimal(f"1e{base_decimals-quote_decimals}")
        first_bid_quantity = Decimal(order_book_data["buys"][0]["quantity"]) * Decimal(f"1e{-base_decimals}")
        self.assertEqual(float(first_bid_price), bids[0].price)
        self.assertEqual(float(first_bid_quantity), bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        first_ask_price = Decimal(order_book_data["sells"][0]["price"]) * Decimal(f"1e{base_decimals - quote_decimals}")
        first_ask_quantity = Decimal(order_book_data["sells"][0]["quantity"]) * Decimal(f"1e{-base_decimals}")
        self.assertEqual(float(first_ask_price), asks[0].price)
        self.assertEqual(float(first_ask_quantity), asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    def _spot_markets_response(self):
        return [{
            "marketId": self.market_id,
            "marketStatus": "active",
            "ticker": self.ex_trading_pair,
            "baseDenom": "inj",
            "baseTokenMeta": {
                "name": "Base Asset",
                "address": "0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",  # noqa: mock
                "symbol": self.base_asset,
                "logo": "https://static.alchemyapi.io/images/assets/7226.png",
                "decimals": 18,
                "updatedAt": "1687190809715"
            },
            "quoteDenom": "peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5",  # noqa: mock
            "quoteTokenMeta": {
                "name": "Quote Asset",
                "address": "0x0000000000000000000000000000000000000000",
                "symbol": self.quote_asset,
                "logo": "https://static.alchemyapi.io/images/assets/825.png",
                "decimals": 6,
                "updatedAt": "1687190809716"
            },
            "makerFeeRate": "-0.0001",
            "takerFeeRate": "0.001",
            "serviceProviderFee": "0.4",
            "minPriceTickSize": "0.000000000000001",
            "minQuantityTickSize": "1000000000000000"
        }]
