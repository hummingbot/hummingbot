from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import asyncio
import conf
import contextlib
import logging
import os
import time
from typing import (
    List,
)
import unittest

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.events import (
    OrderType,
    BuyOrderCreatedEvent,
    MarketEvent,
    RangePositionCreatedEvent,
    RangePositionRemovedEvent,
)
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.connector.uniswap_v3.uniswap_v3_connector import UniswapV3Connector
from hummingbot.client.config.global_config_map import global_config_map
from test.connector.connector.uniswap_v3.fixture import Fixture
from test.integration.humming_web_app import HummingWebApp
from unittest import mock
from decimal import Decimal

logging.basicConfig(level=METRICS_LOG_LEVEL)
global_config_map['gateway_api_host'].value = "localhost"
global_config_map['gateway_api_port'].value = "5000"
logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = True  # conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
WALLET_KEY = "XXX" if API_MOCK_ENABLED else conf.wallet_private_key
base_api_url = "localhost"
rpc_url = global_config_map["ethereum_rpc_url"].value


class UniswapV3ConnectorUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [e for e in MarketEvent]
    connector: UniswapV3Connector
    event_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL

        cls.ev_loop = asyncio.get_event_loop()

        if API_MOCK_ENABLED:
            cls.web_app = HummingWebApp.get_instance()
            cls.web_app.add_host_to_mock(base_api_url)
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local

            cls.web_app.update_response("get", base_api_url, "/api", {"status": "ok"})
            cls.web_app.update_response("get", base_api_url, "/eth/uniswap/start", {"success": True})
            cls.web_app.update_response("post", base_api_url, "/eth/balances", Fixture.BALANCES)
            cls.web_app.update_response("post", base_api_url, "/eth/allowances", Fixture.APPROVALS)
            cls._t_nonce_patcher = unittest.mock.patch(
                "hummingbot.connector.connector.uniswap.uniswap_connector.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()
        cls.current_nonce = 1000000000000000
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.connector = UniswapV3Connector(["ZRX-ETH"], WALLET_KEY, rpc_url, True)
        print("Initializing Uniswap v3 connector... this will take a few seconds.")
        # cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.connector)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()
        if API_MOCK_ENABLED:
            cls.web_app.stop()
            cls._patcher.stop()
            cls._t_nonce_patcher.stop()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.connector.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../connector_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except Exception:
            pass
        self.event_logger = EventLogger()
        for event_tag in self.events:
            self.connector.add_listener(event_tag, self.event_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.connector.remove_listener(event_tag, self.event_logger)
        self.event_logger = None

    @classmethod
    async def run_parallel_async(cls, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, task):
        return self.ev_loop.run_until_complete(self.run_parallel_async(task))

    def test_add_position(self):
        sql = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        config_path = "test_config"
        strategy_name = "test_strategy"
        recorder = MarketsRecorder(sql, [self.connector], config_path, strategy_name)
        recorder.start()
        try:
            if API_MOCK_ENABLED:
                self.web_app.update_response("post", base_api_url, "/eth/uniswap/v3/add-position", Fixture.ADD_POSITION)
                self.web_app.update_response("post", base_api_url, "/eth/poll", Fixture.ETH_POLL_LP_ORDER)
                self.web_app.update_response("post", base_api_url, "/eth/uniswap/v3/result",
                                             Fixture.ETH_RESULT_LP_ORDER)
            hb_id = self.connector.add_position("HBOT-ETH", Decimal("0.1"), Decimal("100"), Decimal("200"),
                                                Decimal("50"), Decimal("60"))
            pos_cre_evt = self.run_parallel(self.event_logger.wait_for(RangePositionCreatedEvent))
            self.run_parallel(asyncio.sleep(0.1))
            print(pos_cre_evt[0])
            self.assertEqual(pos_cre_evt[0].hb_id, hb_id)
            self.assertEqual(Fixture.ADD_POSITION["txHash"], pos_cre_evt[0].tx_hash)
            # Testing tracking market state and restoration
            tracking_state = self.connector.tracking_states
            self.assertTrue("orders" in tracking_state)
            self.assertTrue("positions" in tracking_state)
            self.connector._in_flight_positions.clear()
            self.connector.restore_tracking_states(tracking_state)
            self.assertGreater(len(self.connector._in_flight_positions), 0)
            self.assertEqual(list(self.connector._in_flight_positions.values())[0].hb_id, hb_id)
        finally:
            pass
            recorder.stop()
            os.unlink(self.db_path)

    def test_remove_position(self):
        if API_MOCK_ENABLED:
            self.web_app.update_response("post", base_api_url, "/eth/uniswap/v3/add-position", Fixture.ADD_POSITION)
            self.web_app.update_response("post", base_api_url, "/eth/poll", Fixture.ETH_POLL_LP_ORDER)
            self.web_app.update_response("post", base_api_url, "/eth/uniswap/v3/result", Fixture.ETH_RESULT_LP_ORDER)
        hb_id = self.connector.add_position("HBOT-ETH", Decimal("0.1"), Decimal("100"), Decimal("200"),
                                            Decimal("50"), Decimal("60"))
        pos_cre_evt = self.run_parallel(self.event_logger.wait_for(RangePositionCreatedEvent))
        self.assertEqual(pos_cre_evt[0].hb_id, hb_id)
        self.assertEqual(Fixture.ADD_POSITION["txHash"], pos_cre_evt[0].tx_hash)
        if API_MOCK_ENABLED:
            self.web_app.update_response("post", base_api_url, "/eth/uniswap/v3/remove-position", Fixture.REMOVE_POSITION)
            self.web_app.update_response("post", base_api_url, "/eth/uniswap/v3/result",
                                         Fixture.ETH_RESULT_LP_ORDER_REMOVE)
        self.connector.remove_position(hb_id, "123")
        evt = self.run_parallel(self.event_logger.wait_for(RangePositionRemovedEvent))
        print(evt)

    def test_buy(self):
        if API_MOCK_ENABLED:
            self.web_app.update_response("post", base_api_url, "/eth/uniswap/trade", Fixture.BUY_ORDER)
        uniswap = self.connector
        amount = Decimal("0.1")
        price = Decimal("20")
        order_id = uniswap.buy("HBOT-USDT", amount, OrderType.LIMIT, price)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCreatedEvent))
        self.assertTrue(event.order_id is not None)
        self.assertEqual(order_id, event.order_id)
        # self.assertEqual(event.base_asset_amount, amount)
        print(event.order_id)

    def test_get_position(self):
        if API_MOCK_ENABLED:
            self.web_app.update_response("post", base_api_url, "/uniswap/v3/position", Fixture.POSITION)
        pos = self.ev_loop.run_until_complete(self.connector.get_position("dummy_token_id"))
        print(pos)

    def test_collect_fees(self):
        if API_MOCK_ENABLED:
            self.web_app.update_response("post", base_api_url, "/uniswap/v3/collect-fees", Fixture.COLLECT_FEES)
        pos = self.ev_loop.run_until_complete(self.connector.collect_fees("dummy_token_id"))
        print(pos)
