import asyncio
<<<<<<< HEAD
<<<<<<< HEAD
import re
from test.hummingbot.connector.exchange.chainflip_lp.mock_rpc_executor import MockRPCExecutor
from typing import Awaitable, Optional, Union
from unittest import TestCase
=======
import json
=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
import re
from test.hummingbot.connector.exchange.chainflip_lp.mock_rpc_executor import MockRPCExecutor
from typing import Awaitable, Optional, Union
from unittest import TestCase
<<<<<<< HEAD
from unittest.mock import AsyncMock, MagicMock, patch
>>>>>>> 483756138 ((feat) add chainflip lp connector tests)
=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)

from bidict import bidict
from substrateinterface import Keypair

<<<<<<< HEAD
<<<<<<< HEAD
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_api_order_book_data_source import (
    ChainflipLpAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_exchange import ChainflipLpExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant

=======

from test.hummingbot.connector.exchange.chainflip_lp.mock_rpc_executor import MockRPCExecutor

=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_api_order_book_data_source import (
    ChainflipLpAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_exchange import ChainflipLpExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
<<<<<<< HEAD
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
>>>>>>> 483756138 ((feat) add chainflip lp connector tests)
=======

>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)

class TestChanflipLPAPIOrderBookDataSource(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
<<<<<<< HEAD
<<<<<<< HEAD
        cls.base_asset = {"chain": "Ethereum", "asset": "ETH"}
        cls.quote_asset = {"chain": "Ethereum", "asset": "USDC"}
        cls.trading_pair = f'{cls.base_asset["asset"]}-{cls.quote_asset["asset"]}'
        cls.ex_trading_pair = f'{cls.base_asset["asset"]}-{cls.quote_asset["asset"]}'

=======
        cls.base_asset = {"chain":"Ethereum", "asset":"ETH"}
        cls.quote_asset = {"chain": "Ethereum","asset":"USDC"}
        cls.trading_pair = f'{cls.base_asset["asset"]}-{cls.quote_asset["asset"]}'
        cls.ex_trading_pair = f'{cls.base_asset["asset"]}-{cls.quote_asset["asset"]}'
    
>>>>>>> 483756138 ((feat) add chainflip lp connector tests)
=======
        cls.base_asset = {"chain": "Ethereum", "asset": "ETH"}
        cls.quote_asset = {"chain": "Ethereum", "asset": "USDC"}
        cls.trading_pair = f'{cls.base_asset["asset"]}-{cls.quote_asset["asset"]}'
        cls.ex_trading_pair = f'{cls.base_asset["asset"]}-{cls.quote_asset["asset"]}'

>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
    def setUp(self) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.async_tasks = []
        asyncio.set_event_loop(self.async_loop)
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.address = Keypair.create_from_mnemonic(Keypair.generate_mnemonic()).ss58_address
        self.connector = ChainflipLpExchange(
            client_config_map=client_config_map,
            chainflip_lp_api_url="http://localhost:80",
<<<<<<< HEAD
<<<<<<< HEAD
            chainflip_lp_address=self.address,
=======
            chainflip_lp_address= self.address,
>>>>>>> 483756138 ((feat) add chainflip lp connector tests)
=======
            chainflip_lp_address=self.address,
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
            chainflip_eth_chain="Ethereum",
            chainflip_usdc_chain="Ethereum",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector._data_source._rpc_executor = MockRPCExecutor()

<<<<<<< HEAD
<<<<<<< HEAD
        self.data_source = ChainflipLpAPIOrderBookDataSource(
=======
        self.data_source = ChainflipLPAPIOrderBookDataSource(
>>>>>>> 483756138 ((feat) add chainflip lp connector tests)
=======
        self.data_source = ChainflipLpAPIOrderBookDataSource(
>>>>>>> cb0a3d276 ((refactor) implement review changes)
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            data_source=self.connector._data_source,
        )

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.log_records = []
        self._logs_event: Optional[asyncio.Event] = None
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        self.async_run_with_timeout(self.data_source._data_source.stop())
        for task in self.async_tasks:
            task.cancel()
        self.async_loop.stop()
        self.async_loop.close()
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
<<<<<<< HEAD
<<<<<<< HEAD
                f"^{message}$".replace(".", r"\.")
=======
                f"^{message}$"
                .replace(".", r"\.")
>>>>>>> 483756138 ((feat) add chainflip lp connector tests)
=======
                f"^{message}$".replace(".", r"\.")
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
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

<<<<<<< HEAD
    @property
    def all_asset_mock_data(self):
        asset_data = {
            "result": [
                {"chain": "Ethereum", "asset": "ETH"},
                {"chain": "Ethereum", "asset": "FLIP"},
                {"chain": "Ethereum", "asset": "USDC"},
                {"chain": "Ethereum", "asset": "USDT"},
                {"chain": "Polkadot", "asset": "DOT"},
                {"chain": "Bitcoin", "asset": "BTC"},
                {"chain": "Arbitrum", "asset": "ETH"},
                {"chain": "Arbitrum", "asset": "USDC"},
            ]
        }
        return asset_data

    def test_get_new_order_book_successful(self):
        asset_data = self.all_asset_mock_data
        data = {
            "result": {
                "bids": [
                    {"amount": "0x107c356adb931da34b3", "sqrt_price": "0xfbb120541b407b9868d9"},  # noqa: mock
                    {"amount": "0x1f479f986214e02339a6", "sqrt_price": "0x564256ea016eba867e1"},  # noqa: mock
                    {"amount": "0x3e3545abc51ed0a2e83c5", "sqrt_price": "0x2b5f8cda448aebe9f1"},  # noqa: mock
                    {"amount": "0x7bb79b1c4a08649e8741d7", "sqrt_price": "0x15cf243b1f8d7d6d8"},  # noqa: mock
                    {"amount": "0xf60b58771d06b50676d43f1", "sqrt_price": "0xaf75764f8561157"},  # noqa: mock
                    {"amount": "0x1e952f50cd75553eb44b821e6", "sqrt_price": "0x5838f60e3b0677"},  # noqa: mock
                    {"amount": "0x3cd26661993d3d1e2a3c518494", "sqrt_price": "0x2c55cea9a4bb6"},  # noqa: mock
                    {"amount": "0x78f5d94d8865e2f510e6bdaf204", "sqrt_price": "0x15c5f126b383"},  # noqa: mock
                ],
                "asks": [
                    {"amount": "0xb0b90b96b1f7b7704", "sqrt_price": "0x3095e05a90eb0c51432071"},  # noqa: mock
                    {"amount": "0x949634d34d54ee4", "sqrt_price": "0x31891e0493daf1ccf23d9ea4"},  # noqa: mock
                    {"amount": "0xa9b606d4ea48f", "sqrt_price": "0x2b5eabdc67a5d950f4f76ee5c9"},  # noqa: mock
                    {"amount": "0xc1d6aaaba38", "sqrt_price": "0x25f8b2adc2eca75997729789aec4"},  # noqa: mock
                    {"amount": "0xdd656d902", "sqrt_price": "0x213ebde612ea193310132c046f0af3"},  # noqa: mock
                    {"amount": "0xfcdf26c", "sqrt_price": "0x1d1b64375e15ea2dd31f9260ec843d78"},  # noqa: mock
                    {"amount": "0x120d26", "sqrt_price": "0x197be72c022b9bfbc519350b01526176b0"},  # noqa: mock
                    {"amount": "0x149e", "sqrt_price": "0x164feda37568c4847e63597bcec4061b3ca3"},  # noqa: mock
                    {"amount": "0x17", "sqrt_price": "0x13c435b327440aa87b5c9954de7934f9180b06"},  # noqa: mock
                ],
=======
    def test_get_new_order_book_successful(self):
        asset_data = {
            "result": [
                {"chain": "Ethereum", "asset": "ETH"},
                {"chain": "Ethereum", "asset": "FLIP"},
                {"chain": "Ethereum", "asset": "USDC"},
                {"chain": "Ethereum", "asset": "USDT"},
                {"chain": "Polkadot", "asset": "DOT"},
                {"chain": "Bitcoin", "asset": "BTC"},
                {"chain": "Arbitrum", "asset": "ETH"},
                {"chain": "Arbitrum", "asset": "USDC"},
            ]
        }
        data = {
<<<<<<< HEAD
            "result":{
                'bids': [
                    {'amount': '0x107c356adb931da34b3', 'sqrt_price': '0xfbb120541b407b9868d9'}, 
                    {'amount': '0x1f479f986214e02339a6', 'sqrt_price': '0x564256ea016eba867e1'}, 
                    {'amount': '0x3e3545abc51ed0a2e83c5', 'sqrt_price': '0x2b5f8cda448aebe9f1'}, 
                    {'amount': '0x7bb79b1c4a08649e8741d7', 'sqrt_price': '0x15cf243b1f8d7d6d8'}, 
                    {'amount': '0xf60b58771d06b50676d43f1', 'sqrt_price': '0xaf75764f8561157'}, 
                    {'amount': '0x1e952f50cd75553eb44b821e6', 'sqrt_price': '0x5838f60e3b0677'}, 
                    {'amount': '0x3cd26661993d3d1e2a3c518494', 'sqrt_price': '0x2c55cea9a4bb6'}, 
                    {'amount': '0x78f5d94d8865e2f510e6bdaf204', 'sqrt_price': '0x15c5f126b383'}
                ], 
                'asks': [
                    {'amount': '0xb0b90b96b1f7b7704', 'sqrt_price': '0x3095e05a90eb0c51432071'}, 
                    {'amount': '0x949634d34d54ee4', 'sqrt_price': '0x31891e0493daf1ccf23d9ea4'}, 
                    {'amount': '0xa9b606d4ea48f', 'sqrt_price': '0x2b5eabdc67a5d950f4f76ee5c9'}, 
                    {'amount': '0xc1d6aaaba38', 'sqrt_price': '0x25f8b2adc2eca75997729789aec4'}, 
                    {'amount': '0xdd656d902', 'sqrt_price': '0x213ebde612ea193310132c046f0af3'}, 
                    {'amount': '0xfcdf26c', 'sqrt_price': '0x1d1b64375e15ea2dd31f9260ec843d78'}, 
                    {'amount': '0x120d26', 'sqrt_price': '0x197be72c022b9bfbc519350b01526176b0'}, 
                    {'amount': '0x149e', 'sqrt_price': '0x164feda37568c4847e63597bcec4061b3ca3'}, 
                    {'amount': '0x17', 'sqrt_price': '0x13c435b327440aa87b5c9954de7934f9180b06'}
                ]
>>>>>>> 483756138 ((feat) add chainflip lp connector tests)
=======
            "result": {
                "bids": [
                    {"amount": "0x107c356adb931da34b3", "sqrt_price": "0xfbb120541b407b9868d9"},  # noqa: mock
                    {"amount": "0x1f479f986214e02339a6", "sqrt_price": "0x564256ea016eba867e1"},  # noqa: mock
                    {"amount": "0x3e3545abc51ed0a2e83c5", "sqrt_price": "0x2b5f8cda448aebe9f1"},  # noqa: mock
                    {"amount": "0x7bb79b1c4a08649e8741d7", "sqrt_price": "0x15cf243b1f8d7d6d8"},  # noqa: mock
                    {"amount": "0xf60b58771d06b50676d43f1", "sqrt_price": "0xaf75764f8561157"},  # noqa: mock
                    {"amount": "0x1e952f50cd75553eb44b821e6", "sqrt_price": "0x5838f60e3b0677"},  # noqa: mock
                    {"amount": "0x3cd26661993d3d1e2a3c518494", "sqrt_price": "0x2c55cea9a4bb6"},  # noqa: mock
                    {"amount": "0x78f5d94d8865e2f510e6bdaf204", "sqrt_price": "0x15c5f126b383"},  # noqa: mock
                ],
                "asks": [
                    {"amount": "0xb0b90b96b1f7b7704", "sqrt_price": "0x3095e05a90eb0c51432071"},  # noqa: mock
                    {"amount": "0x949634d34d54ee4", "sqrt_price": "0x31891e0493daf1ccf23d9ea4"},  # noqa: mock
                    {"amount": "0xa9b606d4ea48f", "sqrt_price": "0x2b5eabdc67a5d950f4f76ee5c9"},  # noqa: mock
                    {"amount": "0xc1d6aaaba38", "sqrt_price": "0x25f8b2adc2eca75997729789aec4"},  # noqa: mock
                    {"amount": "0xdd656d902", "sqrt_price": "0x213ebde612ea193310132c046f0af3"},  # noqa: mock
                    {"amount": "0xfcdf26c", "sqrt_price": "0x1d1b64375e15ea2dd31f9260ec843d78"},  # noqa: mock
                    {"amount": "0x120d26", "sqrt_price": "0x197be72c022b9bfbc519350b01526176b0"},  # noqa: mock
                    {"amount": "0x149e", "sqrt_price": "0x164feda37568c4847e63597bcec4061b3ca3"},  # noqa: mock
                    {"amount": "0x17", "sqrt_price": "0x13c435b327440aa87b5c9954de7934f9180b06"},  # noqa: mock
                ],
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
            }
        }
        test_data = DataFormatter.format_orderbook_response(data, self.base_asset, self.quote_asset)
        self.data_source._data_source._rpc_executor._order_book_snapshots.put_nowait(data)
<<<<<<< HEAD
<<<<<<< HEAD
        self.data_source._data_source._rpc_executor._all_assets_responses.put_nowait(asset_data)
=======
>>>>>>> 483756138 ((feat) add chainflip lp connector tests)
=======
        self.data_source._data_source._rpc_executor._all_assets_responses.put_nowait(asset_data)
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)

        order_book = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        expected_update_id = 1

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
        self.assertEqual(8, len(bids))
        self.assertEqual(9, len(asks))
        self.assertEqual(test_data["bids"][0]["amount"], bids[0].amount)
        self.assertEqual(test_data["bids"][0]["price"], bids[0].price)
        self.assertEqual(test_data["asks"][0]["price"], asks[0].price)
        self.assertEqual(test_data["asks"][0]["amount"], asks[0].amount)

<<<<<<< HEAD
    def test_get_new_order_book_raises_exception(self):
        self.data_source._data_source._rpc_executor._all_assets_responses.put_nowait(self.all_asset_mock_data)
        self.data_source._data_source._rpc_executor._order_book_snapshots.put_nowait(None)
        with self.assertRaises(Exception):
            self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

<<<<<<< HEAD
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self):
        pass

    def test_listen_for_subscriptions_raises_cancel_exception(self):
        pass

    def test_listen_for_subscriptions_logs_exception_details(self):
        pass

    def test_subscribe_channels_raises_cancel_exception(self):
        pass

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        pass
=======
        self.assertEqual(1, len(bids))
        self.assertEqual(9487, bids[0].price)
        self.assertEqual(336241, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(9487.5, asks[0].price)
        self.assertEqual(522147, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)
=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
    def test_get_new_order_book_raises_exception(self):
        pass

    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self):
        pass

    def test_listen_for_subscriptions_raises_cancel_exception(self):
        pass

    def test_listen_for_subscriptions_logs_exception_details(self):
        pass

    def test_subscribe_channels_raises_cancel_exception(self):
        pass

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        pass
<<<<<<< HEAD
    
       
    
>>>>>>> 483756138 ((feat) add chainflip lp connector tests)
=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
    def test_get_last_traded_prices(self):
        response = {
            "result": {
                "base_asset": {"chain": "Bitcoin", "asset": "BTC"},
                "quote_asset": {"chain": "Ethereum", "asset": "USDC"},
                "sell": "0x10b09273676d13f5d254e20a20",  # noqa: mock
                "buy": "0x10b09273676d13f5d254e20a20",  # noqa: mock
                "range_order": "0x10b09273676d13f5d254e20a20",  # noqa: mock
            }
        }
        self.data_source._data_source._rpc_executor._all_assets_responses.put_nowait(self.all_asset_mock_data)
        self.data_source._data_source._rpc_executor._get_market_price_responses.put_nowait(response)
        traded_prices = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices([self.trading_pair])
        )
        self.assertIsInstance(traded_prices, dict)
        self.assertEqual(len(traded_prices), 1)
        self.assertIn(self.trading_pair, traded_prices)
        self.assertIsInstance(traded_prices[self.trading_pair], float)
>>>>>>> 08d1ab638 ((refactor) add tests for chainflip lp api order book)
