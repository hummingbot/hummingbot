from typing import Optional
from unittest import TestCase

from hummingbot.connector.exchange.btc_markets import btc_markets_constants as CONSTANTS
from hummingbot.connector.exchange.btc_markets.btc_markets_order_book import BtcMarketsOrderBook
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType, OrderBookRow


class TestOrderbook(TestCase):
    def test_snapshot_message_from_exchange_websocket(self):
        diff_event = {
            "snapshot": True,
            "snapshotId": 1578512833978000,
            "timestamp": '2020-01-08T19:47:13.986Z',
            "bids": [
                ['99.57', '0.55', 1],
                ['97.62', '3.20', 2],
                ['97.07', '0.9', 1],
                ['96.7', '1.9', 1],
                ['95.8', '7.0', 1]
            ],
            "asks": [
                ['100', '3.79', 3],
                ['101', '6.32', 2]
            ],
            "messageType": CONSTANTS.DIFF_EVENT_TYPE
        }

        diff_message: Optional[OrderBookMessage] = BtcMarketsOrderBook.snapshot_message_from_exchange_websocket(
            diff_event, diff_event["timestamp"], {"marketId": "BAT-AUD"}
        )

        self.assertEqual(diff_message.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(diff_message.trading_pair, "BAT-AUD")
        self.assertEqual(diff_message.update_id, diff_event["snapshotId"])
        self.assertEqual(diff_message.bids[0], OrderBookRow(float(diff_event["bids"][0][0]), float(diff_event["bids"][0][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.bids[1], OrderBookRow(float(diff_event["bids"][1][0]), float(diff_event["bids"][1][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.asks[0], OrderBookRow(float(diff_event["asks"][0][0]), float(diff_event["asks"][0][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.bids[1], OrderBookRow(float(diff_event["bids"][1][0]), float(diff_event["bids"][1][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.content["snapshotId"], diff_event["snapshotId"])

    def test_snapshot_message_from_exchange_rest(self):
        diff_event = {
            "snapshot": True,
            "snapshotId": 1578512833978000,
            "timestamp": '2020-01-08T19:47:13.986Z',
            "bids": [
                ['99.57', '0.55', 1],
                ['97.62', '3.20', 2],
                ['97.07', '0.9', 1],
                ['96.7', '1.9', 1],
                ['95.8', '7.0', 1]
            ],
            "asks": [
                ['100', '3.79', 3],
                ['101', '6.32', 2]
            ],
            "messageType": CONSTANTS.DIFF_EVENT_TYPE
        }

        diff_message: Optional[OrderBookMessage] = BtcMarketsOrderBook.snapshot_message_from_exchange_rest(
            diff_event, diff_event["timestamp"], {"marketId": "BAT-AUD"}
        )

        self.assertEqual(diff_message.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(diff_message.trading_pair, "BAT-AUD")
        self.assertEqual(diff_message.update_id, diff_event["snapshotId"])
        self.assertEqual(diff_message.bids[0], OrderBookRow(float(diff_event["bids"][0][0]), float(diff_event["bids"][0][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.bids[1], OrderBookRow(float(diff_event["bids"][1][0]), float(diff_event["bids"][1][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.asks[0], OrderBookRow(float(diff_event["asks"][0][0]), float(diff_event["asks"][0][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.bids[1], OrderBookRow(float(diff_event["bids"][1][0]), float(diff_event["bids"][1][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.content["snapshotId"], diff_event["snapshotId"])

    def test_diff_message_from_exchange(self):
        diff_event = {
            "snapshot": True,
            "snapshotId": 1578512833978000,
            "timestamp": '2020-01-08T19:47:13.986Z',
            "bids": [
                ['99.57', '0.55', 1],
                ['97.62', '3.20', 2],
                ['97.07', '0.9', 1],
                ['96.7', '1.9', 1],
                ['95.8', '7.0', 1]
            ],
            "asks": [
                ['100', '3.79', 3],
                ['101', '6.32', 2]
            ],
            "messageType": CONSTANTS.DIFF_EVENT_TYPE
        }

        diff_message: Optional[OrderBookMessage] = BtcMarketsOrderBook.diff_message_from_exchange(
            diff_event, diff_event["timestamp"], {"marketId": "BAT-AUD"}
        )

        self.assertEqual(diff_message.type, OrderBookMessageType.DIFF)
        self.assertEqual(diff_message.trading_pair, "BAT-AUD")
        self.assertEqual(diff_message.update_id, diff_event["snapshotId"])
        self.assertEqual(diff_message.bids[0], OrderBookRow(float(diff_event["bids"][0][0]), float(diff_event["bids"][0][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.bids[1], OrderBookRow(float(diff_event["bids"][1][0]), float(diff_event["bids"][1][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.asks[0], OrderBookRow(float(diff_event["asks"][0][0]), float(diff_event["asks"][0][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.bids[1], OrderBookRow(float(diff_event["bids"][1][0]), float(diff_event["bids"][1][1]), update_id=1578512833978000))
        self.assertEqual(diff_message.content["snapshotId"], diff_event["snapshotId"])

    def test_sell_trade_message_from_exchange(self):
        trade_event = {
            "marketId": "BAT-AUD",
            "timestamp": '2019-04-08T20:54:27.632Z',
            "tradeId": 3153171493,
            "price": '7370.11',
            "volume": '0.10901605',
            "side": 'Ask',
            "messageType": CONSTANTS.TRADE_EVENT_TYPE
        }

        trade_message: Optional[OrderBookMessage] = BtcMarketsOrderBook.trade_message_from_exchange(
            trade_event, trade_event["timestamp"], {"marketId": "BAT-AUD"}
        )

        self.assertEqual(trade_message.type, OrderBookMessageType.TRADE)
        self.assertEqual(trade_message.trading_pair, "BAT-AUD")
        self.assertEqual(trade_message.trade_id, 3153171493)
        self.assertEqual(trade_message.content["price"], "7370.11")
        self.assertEqual(trade_message.content["amount"], "0.10901605")
        self.assertEqual(trade_message.content["trade_type"], float(TradeType.SELL.value))

    def test_buy_trade_message_from_exchange(self):
        trade_event = {
            "marketId": "BAT-AUD",
            "timestamp": '2019-04-08T20:54:27.632Z',
            "tradeId": 3153171493,
            "price": '7370.11',
            "volume": '0.10901605',
            "side": 'Bid',
            "messageType": CONSTANTS.TRADE_EVENT_TYPE
        }

        trade_message: Optional[OrderBookMessage] = BtcMarketsOrderBook.trade_message_from_exchange(
            trade_event, trade_event["timestamp"], {"marketId": "BAT-AUD"}
        )

        self.assertEqual(trade_message.type, OrderBookMessageType.TRADE)
        self.assertEqual(trade_message.trading_pair, "BAT-AUD")
        self.assertEqual(trade_message.trade_id, 3153171493)
        self.assertEqual(trade_message.content["price"], "7370.11")
        self.assertEqual(trade_message.content["amount"], "0.10901605")
        self.assertEqual(trade_message.content["trade_type"], float(TradeType.BUY.value))
