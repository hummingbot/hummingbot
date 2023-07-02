import asyncio
import json
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from aioresponses import aioresponses
from hummingbot.connector.exchange.hitbtc.hitbtc_exchange import HitbtcExchange
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent


class HitbtcExchangeUnitTest(unittest.TestCase):
    ev_loop = None

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

    def _test_cancel_all(self):
        open_order1 = MagicMock()
        open_order1.trading_pair = "ETHUSDT"
        open_order1.client_order_id = "12345678"
        open_order2 = MagicMock()
        open_order2.trading_pair = "BTCUSDT"
        open_order2.client_order_id = "87654321"

        self.exchange._in_flight_orders = {
            "12345678": open_order1,
            "87654321": open_order2
        }

        self.exchange._execute_cancel = MagicMock()

        self.run_async(self.exchange.cancel_all(timeout_seconds=10.0))

        self.exchange._execute_cancel.assert_called_with("ETHUSDT", "12345678")
        self.assertEqual(2, self.exchange._execute_cancel.call_count)

    def test_tick(self):
        self.exchange._poll_notifier.set = MagicMock()

        self.exchange.tick(100.0)

        self.exchange._poll_notifier.set.assert_called_once()

    def test_get_fee(self):
        self.exchange.estimate_fee_pct = MagicMock(return_value=0.001)
        base_currency = "ETH"
        quote_currency = "USDT"
        order_type = "LIMIT"
        order_side = "BUY"
        amount = Decimal("1.23")

        fee = self.exchange.get_fee(base_currency, quote_currency, order_type, order_side, amount)

        self.assertEqual(str(fee.percent), "0.001")

    def test_get_fee_limit_maker(self):
        self.exchange.estimate_fee_pct = MagicMock(return_value=0.0005)
        base_currency = "ETH"
        quote_currency = "USDT"
        order_type = "LIMIT_MAKER"
        order_side = "SELL"
        amount = Decimal("4.56")

        fee = self.exchange.get_fee(base_currency, quote_currency, order_type, order_side, amount)

        self.assertEqual(str(fee.percent), "0.0005")

    def _test_user_stream_event_listener(self):
        params = [MagicMock(), MagicMock()]

        self.exchange._process_order_message = AsyncMock()
        self.exchange._process_balance_message = MagicMock()

        self.run_async(self.exchange._user_stream_event_listener())

        self.exchange._process_order_message.assert_called_with(params[0])
        self.exchange._process_order_message.assert_called_with(params[1])
        self.exchange._process_balance_message.assert_not_called()

    def _test_get_open_orders(self):
        self.exchange._api_request = AsyncMock(
            return_value=[
                {
                    "clientOrderId": "12345678",
                    "symbol": "ETHUSDT",
                    "price": "123.45",
                    "quantity": "1.23",
                    "cumQuantity": "0.0",
                    "status": "new",
                    "side": "buy",
                    "type": "limit",
                    "createdAt": "2023-06-30T10:00:00.000Z",
                    "updatedAt": "2023-06-30T10:00:00.000Z",
                    "reportType": "status"
                },
                {
                    "clientOrderId": "87654321",
                    "symbol": "BTCUSDT",
                    "price": "234.56",
                    "quantity": "4.56",
                    "cumQuantity": "0.0",
                    "status": "new",
                    "side": "sell",
                    "type": "limit",
                    "createdAt": "2023-06-30T11:00:00.000Z",
                    "updatedAt": "2023-06-30T11:00:00.000Z",
                    "reportType": "status"
                }
            ]
        )

        open_orders = self.run_async(self.exchange.get_open_orders())

        self.assertEqual(2, len(open_orders))

        self.assertEqual(open_orders[0].client_order_id, "12345678")
        self.assertEqual(open_orders[0].trading_pair, "ETHUSDT")
        self.assertEqual(open_orders[0].price, Decimal("123.45"))
        self.assertEqual(open_orders[0].amount, Decimal("1.23"))
        self.assertEqual(open_orders[0].executed_amount, Decimal("0.0"))
        self.assertEqual(open_orders[0].status, "new")
        self.assertEqual(open_orders[0].order_type, "limit")
        self.assertEqual(open_orders[0].is_buy, True)
        self.assertEqual(open_orders[0].time, "2023-06-30T10:00:00.000Z")
        self.assertEqual(open_orders[0].exchange_order_id, None)

        self.assertEqual(open_orders[1].client_order_id, "87654321")
        self.assertEqual(open_orders[1].trading_pair, "BTCUSDT")
        self.assertEqual(open_orders[1].price, Decimal("234.56"))
        self.assertEqual(open_orders[1].amount, Decimal("4.56"))
        self.assertEqual(open_orders[1].executed_amount, Decimal("0.0"))
        self.assertEqual(open_orders[1].status, "new")
        self.assertEqual(open_orders[1].order_type, "limit")
        self.assertEqual(open_orders[1].is_buy, False)
        self.assertEqual(open_orders[1].time, "2023-06-30T11:00:00.000Z")
        self.assertEqual(open_orders[1].exchange_order_id, None)

    @aioresponses()
    def test_all_trading_pairs(self, mock_api):
        mock_api.get(
            "https://api.hitbtc.com/api/2/public/symbol", status=200, body=json.dumps([
                {
                    "id": "ETHUSDT",
                    "baseCurrency": "ETH",
                    "quoteCurrency": "USDT"
                },
                {
                    "id": "BTCUSDT",
                    "baseCurrency": "BTC",
                    "quoteCurrency": "USDT"

                },
                {
                    "id": "ETHBTC",
                    "baseCurrency": "ETH",
                    "quoteCurrency": "BTC"
                }
            ]))

        trading_pairs = self.run_async(self.exchange.all_trading_pairs())

        self.assertEqual(3, len(trading_pairs))
        self.assertIn("ETH-USD", trading_pairs)
        self.assertIn("BTC-USD", trading_pairs)
        self.assertIn("ETH-BTC", trading_pairs)

    @aioresponses()
    def _test_get_last_traded_prices(self, mock_api):
        mock_api.get(
            "https://api.hitbtc.com/api/2/public/ticker", status=200, body=json.dumps([
                {
                    "symbol": "ETHUSDT",
                    "last": "100.0",
                    "volume": "1000.0"
                },
                {
                    "symbol": "BTCUSDT",
                    "last": "200.0",
                    "volume": "2000.0"
                }
            ]))
        mock_api.get(
            "https://api.hitbtc.com/api/2/public/symbol", status=200, body=json.dumps([
                {
                    "id": "ETHUSDT",
                    "baseCurrency": "ETH",
                    "quoteCurrency": "USD",
                },
                {

                    "id": "BTCUSDT",
                    "baseCurrency": "BTC",
                    "quoteCurrency": "USD",
                }]))
        self.exchange.get_last_traded_price = AsyncMock(side_effect=[Decimal("100.0"), Decimal("200.0")])

        trading_pairs = ["ETH-USDT", "BTC-USDT"]

        last_traded_prices = self.run_async(self.exchange.get_last_traded_prices(trading_pairs))

        self.assertEqual(2, len(last_traded_prices))
        self.assertEqual(last_traded_prices["ETH-USDT"], Decimal("100.0"))
        self.assertEqual(last_traded_prices["BTC-USDT"], Decimal("200.0"))


if __name__ == "__main__":
    unittest.main()
