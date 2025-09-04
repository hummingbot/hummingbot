import asyncio
import re
from decimal import Decimal
from test.hummingbot.connector.exchange.injective_v2.programmable_query_executor import ProgrammableQueryExecutor
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Awaitable, Optional, Union
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict
from pyinjective import Address, PrivateKey
from pyinjective.composer_v2 import Composer
from pyinjective.core.market_v2 import DerivativeMarket, SpotMarket
from pyinjective.core.token import Token

from hummingbot.connector.derivative.injective_v2_perpetual.injective_v2_perpetual_api_order_book_data_source import (
    InjectiveV2PerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.injective_v2_perpetual.injective_v2_perpetual_derivative import (
    InjectiveV2PerpetualDerivative,
)
from hummingbot.connector.exchange.injective_v2.injective_v2_utils import (
    InjectiveConfigMap,
    InjectiveDelegatedAccountMode,
    InjectiveMessageBasedTransactionFeeCalculatorMode,
    InjectiveTestnetNetworkMode,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class InjectiveV2APIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "INJ"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.market_id = "0x17ef48032cb24375ba7c2e39f384e56433bcab20cbee9a7357e4cba2eb00abe6"  # noqa: mock

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all")
    def setUp(self, _) -> None:
        super().setUp()
        self.async_tasks = []

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
            fee_calculator=InjectiveMessageBasedTransactionFeeCalculatorMode(),
        )

        self.connector = InjectiveV2PerpetualDerivative(
            connector_configuration=injective_config,
            trading_pairs=[self.trading_pair],
        )
        self.data_source = InjectiveV2PerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            data_source=self.connector._data_source,
        )

        self.initialize_trading_account_patch = patch(
            "hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source"
            ".InjectiveGranteeDataSource.initialize_trading_account"
        )
        self.initialize_trading_account_patch.start()
        self._initialize_timeout_height_patch = patch(
            "hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source"
            ".AsyncClient.sync_timeout_height"
        )
        self._initialize_timeout_height_patch.start()

        self.query_executor = ProgrammableQueryExecutor()
        self.connector._data_source._query_executor = self.query_executor

        self.connector._data_source._composer = Composer(network=self.connector._data_source.network_name)

        self.log_records = []
        self._logs_event: Optional[asyncio.Event] = None
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.data_source._data_source.logger().setLevel(1)
        self.data_source._data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.market_id: self.trading_pair}))

    async def asyncTearDown(self) -> None:
        await self.data_source._data_source.stop()

    def tearDown(self) -> None:
        self._initialize_timeout_height_patch.stop()
        self.initialize_trading_account_patch.stop()
        for task in self.async_tasks:
            task.cancel()
        self._logs_event = None
        super().tearDown()

    def create_task(self, coroutine: Awaitable) -> asyncio.Task:
        task = asyncio.create_task(coroutine)
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

    async def test_get_new_order_book_successful(self):
        spot_markets_response = self._spot_markets_response()
        market = list(spot_markets_response.values())[0]
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        derivative_markets_response = self._derivative_markets_response()
        self.query_executor._derivative_markets_responses.put_nowait(derivative_markets_response)
        derivative_market = list(derivative_markets_response.values())[0]

        quote_decimals = derivative_market.quote_token.decimals

        order_book_snapshot = {
            "buys": [(Decimal("9487") * Decimal(f"1e{quote_decimals}"),
                      Decimal("336241"),
                      1640001112223)],
            "sells": [(Decimal("9487.5") * Decimal(f"1e{quote_decimals}"),
                       Decimal("522147"),
                       1640001112224)],
            "sequence": 512,
            "timestamp": 1650001112223,
        }

        self.query_executor._derivative_order_book_responses.put_nowait(order_book_snapshot)

        order_book = await (self.data_source.get_new_order_book(self.trading_pair))

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

    async def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await (self.data_source.listen_for_trades(asyncio.get_running_loop(), msg_queue))

    async def test_listen_for_trades_logs_exception(self):
        spot_markets_response = self._spot_markets_response()
        market = list(spot_markets_response.values())[0]
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        derivative_markets_response = self._derivative_markets_response()
        self.query_executor._derivative_markets_responses.put_nowait(derivative_markets_response)

        self.query_executor._chain_stream_events.put_nowait({"derivativeTrades": [{}]})

        order_hash = "0x070e2eb3d361c8b26eae510f481bed513a1fb89c0869463a387cfa7995a27043"  # noqa: mock

        trade_data = {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "gasPrice": "160000000.000000000000000000",
            "subaccountDeposits": [],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [],
            "bankBalances": [],
            "spotTrades": [],
            "derivativeTrades": [
                {
                    "marketId": self.market_id,
                    "isBuy": False,
                    "executionType": "LimitMatchRestingOrder",
                    "subaccountId": "0x7998ca45575408f8b4fa354fe615abf3435cf1a7000000000000000000000000",  # noqa: mock
                    "positionDelta": {
                        "isLong": True,
                        "executionQuantity": "324600000000000000000000000000000000000",
                        "executionMargin": "186681600000000000000000000",
                        "executionPrice": "7701000"
                    },
                    "payout": "207636617326923969135747808",
                    "fee": "-93340800000000000000000",
                    "orderHash": order_hash,
                    "feeRecipientAddress": "inj10xvv532h2sy03d86x487v9dt7dp4eud8fe2qv5",  # noqa: mock
                    "cid": "cid1",
                    "tradeId": "7959737_3_0",
                },
            ],
            "spotOrders": [],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [],
        }
        self.query_executor._chain_stream_events.put_nowait(trade_data)

        await asyncio.wait_for(self.data_source.listen_for_subscriptions(), timeout=2)

        msg_queue = asyncio.Queue()
        self.create_task(self.data_source.listen_for_trades(asyncio.get_running_loop(), msg_queue))
        await (msg_queue.get())

        self.assertTrue(
            self.is_logged(
                "WARNING", re.compile(r"^Invalid chain stream event format\. Event:.*")
            )
        )

    async def test_listen_for_trades_successful(self):
        spot_markets_response = self._spot_markets_response()
        market = list(spot_markets_response.values())[0]
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        derivative_markets_response = self._derivative_markets_response()
        self.query_executor._derivative_markets_responses.put_nowait(derivative_markets_response)

        order_hash = "0x070e2eb3d361c8b26eae510f481bed513a1fb89c0869463a387cfa7995a27043"  # noqa: mock

        trade_data = {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "gasPrice": "160000000.000000000000000000",
            "subaccountDeposits": [],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [],
            "bankBalances": [],
            "spotTrades": [],
            "derivativeTrades": [
                {
                    "marketId": self.market_id,
                    "isBuy": False,
                    "executionType": "LimitMatchRestingOrder",
                    "subaccountId": "0x7998ca45575408f8b4fa354fe615abf3435cf1a7000000000000000000000000",  # noqa: mock
                    "positionDelta": {
                        "isLong": True,
                        "executionQuantity": "324600000000000000000000000000000000000",
                        "executionMargin": "186681600000000000000000000",
                        "executionPrice": "7701000"
                    },
                    "payout": "207636617326923969135747808",
                    "fee": "-93340800000000000000000",
                    "orderHash": order_hash,
                    "feeRecipientAddress": "inj10xvv532h2sy03d86x487v9dt7dp4eud8fe2qv5",  # noqa: mock
                    "cid": "cid1",
                    "tradeId": "7959737_3_0",
                },
            ],
            "spotOrders": [],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [],
        }
        self.query_executor._chain_stream_events.put_nowait(trade_data)

        await asyncio.wait_for(self.data_source.listen_for_subscriptions(), timeout=2)

        msg_queue = asyncio.Queue()
        self.create_task(self.data_source.listen_for_trades(asyncio.get_running_loop(), msg_queue))

        msg: OrderBookMessage = await asyncio.wait_for(msg_queue.get(), timeout=6)

        expected_timestamp = int(trade_data["blockTime"]) * 1e-3
        expected_price = Decimal(trade_data["derivativeTrades"][0]["positionDelta"]["executionPrice"]) * Decimal("1e-18")
        expected_amount = Decimal(trade_data["derivativeTrades"][0]["positionDelta"]["executionQuantity"]) * Decimal("1e-18")
        expected_trade_id = trade_data["derivativeTrades"][0]["tradeId"]
        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(expected_trade_id, msg.trade_id)
        self.assertEqual(expected_timestamp, msg.timestamp)
        self.assertEqual(expected_amount, msg.content["amount"])
        self.assertEqual(expected_price, msg.content["price"])
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(float(TradeType.SELL.value), msg.content["trade_type"])

    async def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await (self.data_source.listen_for_order_book_diffs(asyncio.get_running_loop(), msg_queue))

    async def test_listen_for_order_book_diffs_logs_exception(self):
        spot_markets_response = self._spot_markets_response()
        market = list(spot_markets_response.values())[0]
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        derivative_markets_response = self._derivative_markets_response()
        self.query_executor._derivative_markets_responses.put_nowait(derivative_markets_response)

        self.query_executor._chain_stream_events.put_nowait({"derivativeOrderbookUpdates": [{}]})
        order_book_data = {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "gasPrice": "160000000.000000000000000000",
            "subaccountDeposits": [],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [
                {
                    "seq": "7734169",
                    "orderbook": {
                        "marketId": self.market_id,
                        "buyLevels": [
                            {
                                "p": "7684000",
                                "q": "4578787000000000000000000000000000000000"
                            },
                            {
                                "p": "7685000",
                                "q": "4412340000000000000000000000000000000000"
                            },
                        ],
                        "sellLevels": [
                            {
                                "p": "7723000",
                                "q": "3478787000000000000000000000000000000000"
                            },
                        ],
                    }
                }
            ],
            "bankBalances": [],
            "spotTrades": [],
            "derivativeTrades": [],
            "spotOrders": [],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [],
        }
        self.query_executor._chain_stream_events.put_nowait(order_book_data)

        await asyncio.wait_for(self.data_source.listen_for_subscriptions(), timeout=5)

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.create_task(self.data_source.listen_for_order_book_diffs(asyncio.get_running_loop(), msg_queue))

        await (msg_queue.get())

        self.assertTrue(
            self.is_logged(
                "WARNING", re.compile(r"^Invalid chain stream event format\. Event:.*")
            )
        )

    @patch(
        "hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source.InjectiveGranteeDataSource._initialize_timeout_height")
    async def test_listen_for_order_book_diffs_successful(self, _):
        spot_markets_response = self._spot_markets_response()
        market = list(spot_markets_response.values())[0]
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        derivative_markets_response = self._derivative_markets_response()
        self.query_executor._derivative_markets_responses.put_nowait(derivative_markets_response)

        order_book_data = {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "gasPrice": "160000000.000000000000000000",
            "subaccountDeposits": [],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [
                {
                    "seq": "7734169",
                    "orderbook": {
                        "marketId": self.market_id,
                        "buyLevels": [
                            {
                                "p": "7684000",
                                "q": "4578787000000000000000000000000000000000"
                            },
                            {
                                "p": "7685000",
                                "q": "4412340000000000000000000000000000000000"
                            },
                        ],
                        "sellLevels": [
                            {
                                "p": "7723000",
                                "q": "3478787000000000000000000000000000000000"
                            },
                        ],
                    }
                }
            ],
            "bankBalances": [],
            "spotTrades": [],
            "derivativeTrades": [],
            "spotOrders": [],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [],
        }

        self.query_executor._chain_stream_events.put_nowait(order_book_data)

        await (self.data_source.listen_for_subscriptions())

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.create_task(self.data_source.listen_for_order_book_diffs(asyncio.get_running_loop(), msg_queue))

        msg: OrderBookMessage = await asyncio.wait_for(msg_queue.get(), timeout=5)

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(int(order_book_data["blockTime"]) * 1e-3, msg.timestamp)
        expected_update_id = int(order_book_data["derivativeOrderbookUpdates"][0]["seq"])
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        first_bid_price = Decimal(
            order_book_data["derivativeOrderbookUpdates"][0]["orderbook"]["buyLevels"][1]["p"]) * Decimal("1e-18")
        first_bid_quantity = Decimal(
            order_book_data["derivativeOrderbookUpdates"][0]["orderbook"]["buyLevels"][1]["q"]) * Decimal("1e-18")
        self.assertEqual(float(first_bid_price), bids[0].price)
        self.assertEqual(float(first_bid_quantity), bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        first_ask_price = Decimal(
            order_book_data["derivativeOrderbookUpdates"][0]["orderbook"]["sellLevels"][0]["p"]) * Decimal("1e-18")
        first_ask_quantity = Decimal(
            order_book_data["derivativeOrderbookUpdates"][0]["orderbook"]["sellLevels"][0]["q"]) * Decimal("1e-18")
        self.assertEqual(float(first_ask_price), asks[0].price)
        self.assertEqual(float(first_ask_quantity), asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    async def test_listen_for_funding_info_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await (self.data_source.listen_for_funding_info(msg_queue))

    @patch(
        "hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source.InjectiveGranteeDataSource._initialize_timeout_height")
    async def test_listen_for_funding_info_logs_exception(self, _):
        spot_markets_response = self._spot_markets_response()
        market = list(spot_markets_response.values())[0]
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        derivative_markets_response = self._derivative_markets_response()
        self.query_executor._derivative_markets_responses.put_nowait(derivative_markets_response)

        funding_rate = {
            "fundingRates": [
                {
                    "marketId": self.market_id,
                },
            ],
            "paging": {
                "total": "2370"
            }
        }
        self.query_executor._funding_rates_responses.put_nowait(funding_rate)
        funding_rate = {
            "fundingRates": [
                {
                    "marketId": self.market_id,
                    "rate": "0.000004",
                    "timestamp": "1690426800493"
                },
            ],
            "paging": {
                "total": "2370"
            }
        }
        self.query_executor._funding_rates_responses.put_nowait(funding_rate)

        oracle_price = {
            "price": "29423.16356086"
        }
        self.query_executor._oracle_prices_responses.put_nowait(oracle_price)

        trades = {
            "trades": [
                {
                    "orderHash": "0xbe1db35669028d9c7f45c23d31336c20003e4f8879721bcff35fc6f984a6481a",  # noqa: mock
                    "subaccountId": "0x16aef18dbaa341952f1af1795cb49960f68dfee3000000000000000000000000",  # noqa: mock
                    "marketId": self.market_id,
                    "tradeExecutionType": "market",
                    "positionDelta": {
                        "tradeDirection": "buy",
                        "executionPrice": "9084900",
                        "executionQuantity": "3",
                        "executionMargin": "5472660"
                    },
                    "payout": "0",
                    "fee": "81764.1",
                    "executedAt": "1689423842613",
                    "feeRecipient": "inj1zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3t5qxqh",  # noqa: mock
                    "tradeId": "13659264_800_0",
                    "executionSide": "taker"
                }
            ],
            "paging": {
                "total": "1000",
                "from": 1,
                "to": 1
            }
        }
        self.query_executor._derivative_trades_responses.put_nowait(trades)

        self.query_executor._derivative_market_responses.put_nowait(
            {
                "market": {
                    "market": {
                        "ticker": f"{self.ex_trading_pair} PERP",
                        "oracleBase": "0x2d9315a88f3019f8efa88dfe9c0f0843712da0bac814461e27733f6b83eb51b3",  # noqa: mock
                        "oracleQuote": "0x1fc18861232290221461220bd4e2acd1dcdfbc89c84092c93c18bdc7756c1588",  # noqa: mock
                        "oracleType": "Pyth",
                        "quoteDenom": "peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5",  # noqa: mock
                        "marketId": self.market_id,
                        "initialMarginRatio": "83333000000000000",
                        "maintenanceMarginRatio": "60000000000000000",
                        "makerFeeRate": "-100000000000000",
                        "takerFeeRate": "500000000000000",
                        "relayerFeeShareRate": "400000000000000000",
                        "isPerpetual": True,
                        "status": "Active",
                        "minPriceTickSize": "100000000000000",
                        "minQuantityTickSize": "100000000000000",
                        "minNotional": "1000000",
                        "quoteDecimals": 6,
                        "reduceMarginRatio": "249999000000000000",
                        "oracleScaleFactor": 0,
                        "admin": "",
                        "adminPermissions": 0
                    },
                    "perpetualInfo": {
                        "marketInfo": {
                            "marketId": self.market_id,
                            "hourlyFundingRateCap": "625000000000000",
                            "hourlyInterestRate": "4166660000000",
                            "nextFundingTimestamp": "1687190809716",
                            "fundingInterval": "3600"
                        },
                        "fundingInfo": {
                            "cumulativeFunding": "334724096325598384",
                            "cumulativePrice": "0",
                            "lastTimestamp": "1751032800"
                        }
                    },
                    "markPrice": "10361671418280699651"
                }
            }
        )

        oracle_price_event = {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "gasPrice": "160000000.000000000000000000",
            "subaccountDeposits": [],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [],
            "bankBalances": [],
            "spotTrades": [],
            "derivativeTrades": [],
            "spotOrders": [],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [
                {
                    "symbol": self.base_asset,
                    "price": "1000010000000000000",
                    "type": "bandibc"
                },
                {
                    "symbol": self.quote_asset,
                    "price": "307604820000000000",
                    "type": "bandibc"
                },
            ],
        }
        self.query_executor._chain_stream_events.put_nowait(oracle_price_event)
        self.query_executor._chain_stream_events.put_nowait(oracle_price_event)

        await asyncio.wait_for(self.data_source.listen_for_subscriptions(), timeout=5)

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.create_task(self.data_source.listen_for_funding_info(msg_queue))

        await (msg_queue.get())

        self.assertTrue(
            self.is_logged(
                "WARNING", re.compile(r"^Error processing oracle price update for market INJ-USDT")
            )
        )

    @patch(
        "hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source.InjectiveGranteeDataSource._initialize_timeout_height")
    async def test_listen_for_funding_info_successful(self, _):
        spot_markets_response = self._spot_markets_response()
        market = list(spot_markets_response.values())[0]
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        derivative_markets_response = self._derivative_markets_response()
        self.query_executor._derivative_markets_responses.put_nowait(derivative_markets_response)
        derivative_market = list(derivative_markets_response.values())[0]

        quote_decimals = derivative_market.quote_token.decimals

        funding_rate = {
            "fundingRates": [
                {
                    "marketId": self.market_id,
                    "rate": "0.000004",
                    "timestamp": "1690426800493"
                },
            ],
            "paging": {
                "total": "2370"
            }
        }
        self.query_executor._funding_rates_responses.put_nowait(funding_rate)

        oracle_price = {
            "price": "29423.16356086"
        }
        self.query_executor._oracle_prices_responses.put_nowait(oracle_price)

        trades = {
            "trades": [
                {
                    "orderHash": "0xbe1db35669028d9c7f45c23d31336c20003e4f8879721bcff35fc6f984a6481a",  # noqa: mock
                    "subaccountId": "0x16aef18dbaa341952f1af1795cb49960f68dfee3000000000000000000000000",  # noqa: mock
                    "marketId": self.market_id,
                    "tradeExecutionType": "market",
                    "positionDelta": {
                        "tradeDirection": "buy",
                        "executionPrice": "9084900",
                        "executionQuantity": "3",
                        "executionMargin": "5472660"
                    },
                    "payout": "0",
                    "fee": "81764.1",
                    "executedAt": "1689423842613",
                    "feeRecipient": "inj1zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3t5qxqh",  # noqa: mock
                    "tradeId": "13659264_800_0",
                    "executionSide": "taker"
                }
            ],
            "paging": {
                "total": "1000",
                "from": 1,
                "to": 1
            }
        }
        self.query_executor._derivative_trades_responses.put_nowait(trades)

        derivative_market_info = {
            "market": {
                "market": {
                    "ticker": f"{self.base_asset}/{self.quote_asset} PERP",
                    "oracleBase": "0x2d9315a88f3019f8efa88dfe9c0f0843712da0bac814461e27733f6b83eb51b3",  # noqa: mock
                    "oracleQuote": "0x1fc18861232290221461220bd4e2acd1dcdfbc89c84092c93c18bdc7756c1588",  # noqa: mock
                    "oracleType": "Pyth",
                    "quoteDenom": "peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5",  # noqa: mock
                    "marketId": self.market_id,
                    "initialMarginRatio": "83333000000000000",
                    "maintenanceMarginRatio": "60000000000000000",
                    "makerFeeRate": "-100000000000000",
                    "takerFeeRate": "500000000000000",
                    "relayerFeeShareRate": "400000000000000000",
                    "isPerpetual": True,
                    "status": "Active",
                    "minPriceTickSize": "100000000000000",
                    "minQuantityTickSize": "100000000000000",
                    "minNotional": "1000000",
                    "quoteDecimals": 6,
                    "reduceMarginRatio": "249999000000000000",
                    "oracleScaleFactor": 0,
                    "admin": "",
                    "adminPermissions": 0
                },
                "perpetualInfo": {
                    "marketInfo": {
                        "marketId": self.market_id,
                        "hourlyFundingRateCap": "625000000000000",
                        "hourlyInterestRate": "4166660000000",
                        "nextFundingTimestamp": "1687190809716",
                        "fundingInterval": "3600"
                    },
                    "fundingInfo": {
                        "cumulativeFunding": "334724096325598384",
                        "cumulativePrice": "0",
                        "lastTimestamp": "1751032800"
                    }
                },
                "markPrice": "10361671418280699651"
            }
        }
        self.query_executor._derivative_market_responses.put_nowait(derivative_market_info)

        oracle_price_event = {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "gasPrice": "160000000.000000000000000000",
            "subaccountDeposits": [],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [],
            "bankBalances": [],
            "spotTrades": [],
            "derivativeTrades": [],
            "spotOrders": [],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [
                {
                    "symbol": self.base_asset,
                    "price": "1000010000000000000",
                    "type": "bandibc"
                },
                {
                    "symbol": self.quote_asset,
                    "price": "307604820000000000",
                    "type": "bandibc"
                },
            ],
        }
        self.query_executor._chain_stream_events.put_nowait(oracle_price_event)

        await (self.data_source.listen_for_subscriptions())

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.create_task(self.data_source.listen_for_funding_info(msg_queue))

        funding_info: FundingInfoUpdate = await (msg_queue.get())

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(
            Decimal(trades["trades"][0]["positionDelta"]["executionPrice"]) * Decimal(f"1e{-quote_decimals}"),
            funding_info.index_price)
        self.assertEqual(Decimal(oracle_price["price"]), funding_info.mark_price)
        self.assertEqual(
            int(derivative_market_info["market"]["perpetualInfo"]["marketInfo"]["nextFundingTimestamp"]),
            funding_info.next_funding_utc_timestamp)
        self.assertEqual(Decimal(funding_rate["fundingRates"][0]["rate"]), funding_info.rate)

    async def test_get_funding_info(self):
        spot_markets_response = self._spot_markets_response()
        market = list(spot_markets_response.values())[0]
        self.query_executor._spot_markets_responses.put_nowait(spot_markets_response)
        self.query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        derivative_markets_response = self._derivative_markets_response()
        self.query_executor._derivative_markets_responses.put_nowait(derivative_markets_response)
        derivative_market = list(derivative_markets_response.values())[0]

        quote_decimals = derivative_market.quote_token.decimals

        funding_rate = {
            "fundingRates": [
                {
                    "marketId": self.market_id,
                    "rate": "0.000004",
                    "timestamp": "1690426800493"
                },
            ],
            "paging": {
                "total": "2370"
            }
        }
        self.query_executor._funding_rates_responses.put_nowait(funding_rate)

        oracle_price = {
            "price": "29423.16356086"
        }
        self.query_executor._oracle_prices_responses.put_nowait(oracle_price)

        trades = {
            "trades": [
                {
                    "orderHash": "0xbe1db35669028d9c7f45c23d31336c20003e4f8879721bcff35fc6f984a6481a",  # noqa: mock
                    "subaccountId": "0x16aef18dbaa341952f1af1795cb49960f68dfee3000000000000000000000000",  # noqa: mock
                    "marketId": self.market_id,
                    "tradeExecutionType": "market",
                    "positionDelta": {
                        "tradeDirection": "buy",
                        "executionPrice": "9084900",
                        "executionQuantity": "3",
                        "executionMargin": "5472660"
                    },
                    "payout": "0",
                    "fee": "81764.1",
                    "executedAt": "1689423842613",
                    "feeRecipient": "inj1zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3t5qxqh",  # noqa: mock
                    "tradeId": "13659264_800_0",
                    "executionSide": "taker"
                }
            ],
            "paging": {
                "total": "1000",
                "from": 1,
                "to": 1
            }
        }
        self.query_executor._derivative_trades_responses.put_nowait(trades)

        derivative_market_info = {
            "market": {
                "market": {
                    "ticker": f"{self.ex_trading_pair} PERP",
                    "oracleBase": "0x2d9315a88f3019f8efa88dfe9c0f0843712da0bac814461e27733f6b83eb51b3",  # noqa: mock
                    "oracleQuote": "0x1fc18861232290221461220bd4e2acd1dcdfbc89c84092c93c18bdc7756c1588",  # noqa: mock
                    "oracleType": "Pyth",
                    "quoteDenom": "peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5",  # noqa: mock
                    "marketId": self.market_id,
                    "initialMarginRatio": "83333000000000000",
                    "maintenanceMarginRatio": "60000000000000000",
                    "makerFeeRate": "-100000000000000",
                    "takerFeeRate": "500000000000000",
                    "relayerFeeShareRate": "400000000000000000",
                    "isPerpetual": True,
                    "status": "Active",
                    "minPriceTickSize": "100000000000000",
                    "minQuantityTickSize": "100000000000000",
                    "minNotional": "1000000",
                    "quoteDecimals": 6,
                    "reduceMarginRatio": "249999000000000000",
                    "oracleScaleFactor": 0,
                    "admin": "",
                    "adminPermissions": 0
                },
                "perpetualInfo": {
                    "marketInfo": {
                        "marketId": self.market_id,
                        "hourlyFundingRateCap": "625000000000000",
                        "hourlyInterestRate": "4166660000000",
                        "nextFundingTimestamp": "1687190809716",
                        "fundingInterval": "3600"
                    },
                    "fundingInfo": {
                        "cumulativeFunding": "334724096325598384",
                        "cumulativePrice": "0",
                        "lastTimestamp": "1751032800"
                    }
                },
                "markPrice": "10361671418280699651"
            }
        }
        self.query_executor._derivative_market_responses.put_nowait(derivative_market_info)

        funding_info: FundingInfo = await (
            self.data_source.get_funding_info(self.trading_pair)
        )

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(
            Decimal(trades["trades"][0]["positionDelta"]["executionPrice"]) * Decimal(f"1e{-quote_decimals}"),
            funding_info.index_price)
        self.assertEqual(Decimal(oracle_price["price"]), funding_info.mark_price)
        self.assertEqual(
            int(derivative_market_info["market"]["perpetualInfo"]["marketInfo"]["nextFundingTimestamp"]),
            funding_info.next_funding_utc_timestamp)
        self.assertEqual(Decimal(funding_rate["fundingRates"][0]["rate"]), funding_info.rate)

    def _spot_markets_response(self):
        base_native_token = Token(
            name="Base Asset",
            symbol=self.base_asset,
            denom="inj",
            address="0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",  # noqa: mock
            decimals=18,
            logo="https://static.alchemyapi.io/images/assets/7226.png",
            updated=1687190809715,
            unique_symbol="",
        )
        quote_native_token = Token(
            name="Quote Asset",
            symbol=self.quote_asset,
            denom="peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5",  # noqa: mock
            address="0x0000000000000000000000000000000000000000",  # noqa: mock
            decimals=6,
            logo="https://static.alchemyapi.io/images/assets/825.png",
            updated=1687190809716,
            unique_symbol="",
        )

        native_market = SpotMarket(
            id="0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe",  # noqa: mock
            status="active",
            ticker=self.ex_trading_pair,
            base_token=base_native_token,
            quote_token=quote_native_token,
            maker_fee_rate=Decimal("-0.0001"),
            taker_fee_rate=Decimal("0.001"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=Decimal("0.0001"),
            min_quantity_tick_size=Decimal("0.001"),
            min_notional=Decimal("0.000001"),
        )

        return {native_market.id: native_market}

    def _derivative_markets_response(self):
        quote_native_token = Token(
            name="Quote Asset",
            symbol=self.quote_asset,
            denom="peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5",  # noqa: mock
            address="0x0000000000000000000000000000000000000000",  # noqa: mock
            decimals=6,
            logo="https://static.alchemyapi.io/images/assets/825.png",
            updated=1687190809716,
            unique_symbol="",
        )

        native_market = DerivativeMarket(
            id=self.market_id,
            status="active",
            ticker=f"{self.ex_trading_pair} PERP",
            oracle_base=self.base_asset,
            oracle_quote=self.quote_asset,
            oracle_type="bandibc",
            oracle_scale_factor=6,
            initial_margin_ratio=Decimal("0.195"),
            maintenance_margin_ratio=Decimal("0.05"),
            quote_token=quote_native_token,
            maker_fee_rate=Decimal("-0.0003"),
            taker_fee_rate=Decimal("0.003"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=Decimal("0.001"),
            min_quantity_tick_size=Decimal("0.0001"),
            min_notional=Decimal("0.000001"),
        )

        return {native_market.id: native_market}
