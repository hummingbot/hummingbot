import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.hitbtc.hitbtc_exchange import HitbtcExchange
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent


class HitbtcExchangeUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.exchange: ExchangeBase = HitbtcExchange(
            client_config_map=MagicMock(),
            hitbtc_api_key="test_api_key",
            hitbtc_secret_key="test_secret_key",
            trading_pairs=["ETHUSDT", "BTCUSDT"],
            trading_required=True
        )

    def run_async(self, async_fn):
        return self.ev_loop.run_until_complete(async_fn)

    def test_get_order_price_quantum(self):
        self.exchange._trading_rules = {
            "ETHUSDT": MagicMock(min_price_increment=Decimal("0.01")),
            "BTCUSDT": MagicMock(min_price_increment=Decimal("0.1"))
        }

        self.assertEqual(Decimal("0.01"), self.exchange.get_order_price_quantum("ETHUSDT", Decimal("1.23")))
        self.assertEqual(Decimal("0.1"), self.exchange.get_order_price_quantum("BTCUSDT", Decimal("4.56")))

    def test_get_order_size_quantum(self):
        self.exchange._trading_rules = {
            "ETHUSDT": MagicMock(min_base_amount_increment=Decimal("0.001")),
            "BTCUSDT": MagicMock(min_base_amount_increment=Decimal("0.01"))
        }

        self.assertEqual(Decimal("0.001"), self.exchange.get_order_size_quantum("ETHUSDT", Decimal("1.23")))
        self.assertEqual(Decimal("0.01"), self.exchange.get_order_size_quantum("BTCUSDT", Decimal("4.56")))

    def test_cancel(self):
        self.exchange._execute_cancel = MagicMock()
        self.exchange.cancel("ETHUSDT", "12345678")

        self.exchange._execute_cancel.assert_called_with("ETHUSDT", "12345678")

    def test_process_trade_message(self):
        trade_msg = {
            "id": "4345697765",
            "clientOrderId": "53b7cf917963464a811a4af426102c19",
            "symbol": "ETHBTC",
            "side": "sell",
            "status": "filled",
            "type": "limit",
            "timeInForce": "GTC",
            "quantity": "0.001",
            "price": "0.053868",
            "cumQuantity": "0.001",
            "postOnly": False,
            "createdAt": "2017-10-20T12:20:05.952Z",
            "updatedAt": "2017-10-20T12:20:38.708Z",
            "reportType": "trade",
            "tradeQuantity": "0.001",
            "tradePrice": "0.053868",
            "tradeId": 55051694,
            "tradeFee": "-0.000000005"
        }

        order = AsyncMock()
        order.exchange_order_id = "4345697765"
        order.update_with_trade_update.return_value = True

        self.exchange._in_flight_orders = {"53b7cf917963464a811a4af426102c19": order}

        event_logger = EventLogger()
        self.exchange.add_listener(MarketEvent.OrderFilled, event_logger)

        self.run_async(self.exchange._process_trade_message(trade_msg))

        self.assertEqual(1, len(event_logger.event_log))
        self.assertIsInstance(event_logger.event_log[0], OrderFilledEvent)
        # self.assertEqual("53b7cf917963464a811a4af426102c19", event_logger.event_log[0].order_id)

        order.update_with_trade_update.assert_called_with(trade_msg)


if __name__ == "__main__":
    unittest.main()
