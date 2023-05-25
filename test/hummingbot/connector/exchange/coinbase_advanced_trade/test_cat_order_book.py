import asyncio
from unittest import TestCase

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_order_book import CoinbaseAdvancedTradeOrderBook
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_web_utils import get_timestamp_from_exchange_time
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class CoinbaseAdvancedTradeOrderBookTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.snapshot_msg = {
            "channel": "l2_data",
            "client_id": "",
            "timestamp": "2023-02-09T20:32:50.714964855Z",
            "sequence_num": 0,
            "events": [
                {
                    "type": "snapshot",
                    "product_id": "BTC-USD",
                    "updates": [
                        {
                            "side": "bid",
                            "event_time": "1970-01-01T00:00:00Z",
                            "price_level": "21921.73",
                            "new_quantity": "0.06317902"
                        },
                        {
                            "side": "bid",
                            "event_time": "1970-01-01T00:00:00Z",
                            "price_level": "21921.3",
                            "new_quantity": "0.02"
                        },
                        {
                            "side": "ask",
                            "event_time": "1970-01-01T00:00:00Z",
                            "price_level": "2192.3",
                            "new_quantity": "0.002"
                        },
                    ]
                }
            ]
        }
        self.trade_msg = {
            "channel": "market_trades",
            "client_id": "",
            "timestamp": "2023-02-09T20:19:35.39625135Z",
            "sequence_num": 0,
            "events": [
                {
                    "type": "snapshot",
                    "trades": [
                        {
                            "trade_id": "12345",
                            "product_id": "ETH-USD",
                            "price": "1260.01",
                            "size": "0.3",
                            "side": "BUY",
                            "time": "2019-08-14T20:42:27.265Z",
                        }
                    ]
                }
            ]
        }
        self.log_records = []

        self.order_book = CoinbaseAdvancedTradeOrderBook()
        self.order_book.logger().setLevel(1)
        self.order_book.logger().addHandler(self)

    async def symbol_to_pair(self, symbol: str) -> str:
        return "COINALPHA-HBOT"

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and message in record.getMessage() for
            record in self.log_records)

    def test_level2_order_book_snapshot_message(self):
        snapshot_message = asyncio.run(CoinbaseAdvancedTradeOrderBook.level2_order_book_message(
            msg=self.snapshot_msg,
            timestamp=1640000000.0,
            symbol_to_pair=self.symbol_to_pair
        ))

        update_id = int(get_timestamp_from_exchange_time("1970-01-01T00:00:00Z", "second"))

        self.assertEqual("COINALPHA-HBOT", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1640000000.0, snapshot_message.timestamp)
        self.assertEqual(0, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(2, len(snapshot_message.bids))
        self.assertEqual(21921.73, snapshot_message.bids[0].price)
        self.assertEqual(0.06317902, snapshot_message.bids[0].amount)
        self.assertEqual(update_id, snapshot_message.bids[0].update_id)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(2192.3, snapshot_message.asks[0].price)
        self.assertEqual(0.002, snapshot_message.asks[0].amount)
        self.assertEqual(update_id, snapshot_message.asks[0].update_id)

    def test_level2_order_book_update_message(self):
        update_msg = self.snapshot_msg
        update_msg["sequence_num"] = 5
        update_msg["events"][0]["type"] = "update"

        update_message = asyncio.run(CoinbaseAdvancedTradeOrderBook.level2_order_book_message(
            msg=update_msg,
            timestamp=1640000000.0,
            symbol_to_pair=self.symbol_to_pair
        ))

        self.assertEqual("COINALPHA-HBOT", update_message.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, update_message.type)
        self.assertEqual(1640000000.0, update_message.timestamp)
        self.assertEqual(5, update_message.update_id)
        self.assertEqual(-1, update_message.trade_id)
        self.assertEqual(2, len(update_message.bids))
        self.assertEqual(21921.73, update_message.bids[0].price)
        self.assertEqual(0.06317902, update_message.bids[0].amount)
        self.assertEqual(update_message.update_id, update_message.bids[0].update_id)
        self.assertEqual(1, len(update_message.asks))
        self.assertEqual(2192.3, update_message.asks[0].price)
        self.assertEqual(0.002, update_message.asks[0].amount)
        self.assertEqual(update_message.update_id, update_message.asks[0].update_id)

    def test_market_trades_order_book_snapshot_message(self):
        trade_message = asyncio.run(CoinbaseAdvancedTradeOrderBook.market_trades_order_book_message(
            msg=self.trade_msg,
            symbol_to_pair=self.symbol_to_pair
        ))
        timestamp: float = get_timestamp_from_exchange_time(self.trade_msg["timestamp"], "s")

        self.assertEqual("COINALPHA-HBOT", trade_message.content["trading_pair"])
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)

        self.assertEqual(12345, trade_message.content["trade_id"])
        self.assertEqual("1260.01", trade_message.content["price"])
        self.assertEqual("0.3", trade_message.content["amount"])
        # Check trade type - this will depend on the 'side' value in the message
        self.assertIn(trade_message.content["trade_type"], [TradeType.SELL.value, TradeType.BUY.value])
        self.assertEqual(int(timestamp), trade_message.content["update_id"])

    def test_level2_or_trade_message_from_exchange_level2(self):
        snapshot_msg = self.snapshot_msg
        snapshot_msg["sequence_num"] = 1

        snapshot_message = asyncio.run(CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            msg=snapshot_msg,
            timestamp=1640000000.0,
            symbol_to_pair=self.symbol_to_pair
        ))

        self.assertEqual(snapshot_message.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(snapshot_message.update_id, 1)
        self.assertEqual(snapshot_message.timestamp, 1640000000.0)

    def test_level2_or_trade_message_from_exchange_market_trades(self):
        trade_msg = self.trade_msg
        trade_msg["sequence_num"] = 1
        trade_message = asyncio.run(CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            msg=trade_msg,
            timestamp=1640000000.0,
            symbol_to_pair=self.symbol_to_pair
        ))

        timestamp: float = get_timestamp_from_exchange_time(self.trade_msg["timestamp"], "s")

        self.assertEqual(trade_message.type, OrderBookMessageType.TRADE)
        self.assertEqual(trade_message.update_id, -1)
        self.assertEqual(12345, trade_message.content["trade_id"])
        self.assertEqual("1260.01", trade_message.content["price"])
        self.assertEqual("0.3", trade_message.content["amount"])
        self.assertEqual(int(timestamp), trade_message.content["update_id"])

    def test_level2_or_trade_message_from_exchange_lvel2_out_of_order(self):
        snapshot_msg = self.snapshot_msg
        snapshot_msg["sequence_num"] = 50

        asyncio.run(CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            msg=snapshot_msg,
            timestamp=1640000000.0,
            symbol_to_pair=self.symbol_to_pair
        ))

        self.assertTrue(
            self.is_logged(log_level="WARNING", message="Received out of order message from l2_data, this indicates a "
                                                        "missed message")
        )

    def test_level2_or_trade_message_from_exchange_trade_out_of_order(self):
        trade_msg = self.trade_msg
        trade_msg["sequence_num"] = 50

        asyncio.run(CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            msg=trade_msg,
            timestamp=1640000000.0,
            symbol_to_pair=self.symbol_to_pair
        ))

        self.assertTrue(
            self.is_logged(log_level="WARNING",
                           message="Received out of order message from market_trades, this indicates a "
                                   "missed message")
        )
