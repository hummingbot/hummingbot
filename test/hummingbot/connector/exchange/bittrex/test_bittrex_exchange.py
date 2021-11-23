import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable, Dict

from aioresponses import aioresponses
from hummingbot.connector.exchange.bittrex.bittrex_exchange import BittrexExchange
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderType, TradeType, MarketEvent


class BittrexExchangeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.secret_key = "someSecret"
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()
        self.event_listener = EventLogger()

        self.exchange = BittrexExchange(self.api_key, self.secret_key, trading_pairs=[self.trading_pair])

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_filled_response(self) -> Dict:
        filled_resp = {
            "id": "87076200-79bc-4f97-82b1-ad8fa3e630cf",
            "marketSymbol": self.trading_pair,
            "direction": "BUY",
            "type": "LIMIT",
            "quantity": "1",
            "limit": "10",
            "timeInForce": "POST_ONLY_GOOD_TIL_CANCELLED",
            "fillQuantity": "1",
            "commission": "0.11805420",
            "proceeds": "23.61084196",
            "status": "CLOSED",
            "createdAt": "2021-09-08T10:00:34.83Z",
            "updatedAt": "2021-09-08T10:00:35.05Z",
            "closedAt": "2021-09-08T10:00:35.05Z",
        }
        return filled_resp

    @aioresponses()
    def test_execute_cancel(self, mocked_api):
        url = f"{self.exchange.BITTREX_API_ENDPOINT}/orders/"
        regex_url = re.compile(f"^{url}")
        resp = {"status": "CLOSED"}
        mocked_api.delete(regex_url, body=json.dumps(resp))

        order_id = "someId"
        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id="someExchangeId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=TradeType.BUY,
            price=Decimal("10.0"),
            amount=Decimal("1.0"),
        )
        self.exchange.add_listener(MarketEvent.OrderCancelled, self.event_listener)

        self.async_run_with_timeout(coroutine=self.exchange.execute_cancel(self.trading_pair, order_id))

        self.assertEqual(1, len(self.event_listener.event_log))

        event = self.event_listener.event_log[0]

        self.assertEqual(order_id, event.order_id)
        self.assertTrue(order_id not in self.exchange.in_flight_orders)

    @aioresponses()
    def test_execute_cancel_already_filled(self, mocked_api):
        url = f"{self.exchange.BITTREX_API_ENDPOINT}/orders/"
        regex_url = re.compile(f"^{url}")
        del_resp = {"code": "ORDER_NOT_OPEN"}
        mocked_api.delete(regex_url, status=409, body=json.dumps(del_resp))
        get_resp = self.get_filled_response()
        mocked_api.get(regex_url, body=json.dumps(get_resp))

        order_id = "someId"
        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id="someExchangeId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=TradeType.BUY,
            price=Decimal("10.0"),
            amount=Decimal("1.0"),
        )
        self.exchange.add_listener(MarketEvent.BuyOrderCompleted, self.event_listener)

        self.async_run_with_timeout(coroutine=self.exchange.execute_cancel(self.trading_pair, order_id))

        self.assertEqual(1, len(self.event_listener.event_log))

        event = self.event_listener.event_log[0]

        self.assertEqual(order_id, event.order_id)
        self.assertTrue(order_id not in self.exchange.in_flight_orders)
