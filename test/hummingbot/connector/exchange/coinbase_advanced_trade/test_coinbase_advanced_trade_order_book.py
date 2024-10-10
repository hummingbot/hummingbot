from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest

from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_order_book import (
    CoinbaseAdvancedTradeOrderBook,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils import (
    get_timestamp_from_exchange_time,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class CoinbaseAdvancedTradeOrderBookTests(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
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
        self.order_book = CoinbaseAdvancedTradeOrderBook()
        self.set_loggers([self.order_book.logger()])

    async def symbol_to_pair(self, symbol: str) -> str:
        return "COINALPHA-HBOT"

    async def test_level2_order_book_snapshot_message(self):
        snapshot_message = await (CoinbaseAdvancedTradeOrderBook._level2_order_book_message(
            msg=self.snapshot_msg,
            symbol_to_pair=self.symbol_to_pair
        ))

        self.assertEqual("COINALPHA-HBOT", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(int(get_timestamp_from_exchange_time(self.snapshot_msg["timestamp"], "s")), snapshot_message.timestamp)
        self.assertEqual(int(get_timestamp_from_exchange_time(self.snapshot_msg['timestamp'], "s")), snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(2, len(snapshot_message.bids))
        self.assertEqual(21921.73, snapshot_message.bids[0].price)
        self.assertEqual(0.06317902, snapshot_message.bids[0].amount)
        self.assertEqual(int(get_timestamp_from_exchange_time(self.snapshot_msg['timestamp'], "s")), snapshot_message.bids[0].update_id)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(2192.3, snapshot_message.asks[0].price)
        self.assertEqual(0.002, snapshot_message.asks[0].amount)
        self.assertEqual(int(get_timestamp_from_exchange_time(self.snapshot_msg['timestamp'], "s")), snapshot_message.asks[0].update_id)

    async def test_level2_order_book_update_message(self):
        update_msg = self.snapshot_msg
        update_msg["sequence_num"] = 5
        update_msg["events"][0]["type"] = "update"

        update_message = await (CoinbaseAdvancedTradeOrderBook._level2_order_book_message(
            msg=update_msg,
            symbol_to_pair=self.symbol_to_pair
        ))

        self.assertEqual("COINALPHA-HBOT", update_message.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, update_message.type)
        self.assertEqual(int(get_timestamp_from_exchange_time(update_msg["timestamp"], "s")), update_message.timestamp)
        self.assertEqual(int(get_timestamp_from_exchange_time(update_msg["timestamp"], "s")), update_message.update_id)
        self.assertEqual(-1, update_message.trade_id)
        self.assertEqual(2, len(update_message.bids))
        self.assertEqual(21921.73, update_message.bids[0].price)
        self.assertEqual(0.06317902, update_message.bids[0].amount)
        self.assertEqual(update_message.update_id, update_message.bids[0].update_id)
        self.assertEqual(1, len(update_message.asks))
        self.assertEqual(2192.3, update_message.asks[0].price)
        self.assertEqual(0.002, update_message.asks[0].amount)
        self.assertEqual(update_message.update_id, update_message.asks[0].update_id)

    async def test_market_trades_order_book_snapshot_message(self):
        trade_message = await (CoinbaseAdvancedTradeOrderBook._market_trades_order_book_message(
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

    async def test_level2_or_trade_message_from_exchange_level2(self):
        snapshot_msg = self.snapshot_msg
        snapshot_msg["sequence_num"] = 1

        snapshot_message = await (CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            msg=snapshot_msg,
            symbol_to_pair=self.symbol_to_pair
        ))

        self.assertEqual(snapshot_message.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(snapshot_message.update_id, int(get_timestamp_from_exchange_time(
            snapshot_msg['timestamp'], "s")))
        self.assertEqual(snapshot_message.timestamp, int(get_timestamp_from_exchange_time(snapshot_msg["timestamp"], "s")))

    async def test_level2_or_trade_message_from_exchange_market_trades(self):
        trade_msg = self.trade_msg
        trade_msg["sequence_num"] = 1
        trade_message = await (CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            msg=trade_msg,
            symbol_to_pair=self.symbol_to_pair
        ))

        timestamp: float = get_timestamp_from_exchange_time(self.trade_msg["timestamp"], "s")

        self.assertEqual(trade_message.type, OrderBookMessageType.TRADE)
        self.assertEqual(trade_message.update_id, -1)
        self.assertEqual(12345, trade_message.content["trade_id"])
        self.assertEqual("1260.01", trade_message.content["price"])
        self.assertEqual("0.3", trade_message.content["amount"])
        self.assertEqual(int(timestamp), trade_message.content["update_id"])

    async def test_level2_or_trade_message_from_exchange_lvel2_out_of_order(self):
        snapshot_msg = self.snapshot_msg
        snapshot_msg["sequence_num"] = 50

        await (CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            msg=snapshot_msg,
            symbol_to_pair=self.symbol_to_pair
        ))

    async def test_level2_or_trade_message_from_exchange_trade_out_of_order(self):
        trade_msg = self.trade_msg
        trade_msg["sequence_num"] = 50

        await (CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            msg=trade_msg,
            symbol_to_pair=self.symbol_to_pair
        ))

    async def test_level2_or_trade_message_from_exchange_unexpected_channel(self):
        msg = self.snapshot_msg.copy()
        msg["channel"] = "unexpected_channel"
        out = await CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            msg=msg,
            symbol_to_pair=self.symbol_to_pair
        )
        self.assertIsNone(out)

    async def test_level2_or_trade_message_from_exchange_missing_events(self):
        msg = self.snapshot_msg.copy()
        del msg["events"]
        out = await CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            msg=msg,
            symbol_to_pair=self.symbol_to_pair
        )
        self.assertIsNone(out)

    async def test__level2_order_book_message_unexpected_type(self):
        msg = {"events": {}, "type": "unexpected_type", "data": {}}
        out = await CoinbaseAdvancedTradeOrderBook._level2_order_book_message(
            msg=msg,
            symbol_to_pair=self.symbol_to_pair
        )
        self.assertIsNone(out)

    async def test_level2_order_book_message_missing_events(self):
        msg = {"type": "l2_data", "data": {}}
        with self.assertRaises(KeyError):
            await CoinbaseAdvancedTradeOrderBook._level2_order_book_message(
                msg=msg,
                symbol_to_pair=self.symbol_to_pair
            )

    async def test_market_trades_order_book_message_unexpected_type(self):
        msg = {"events": {}, "type": "unexpected_type", "data": {}}
        out = await CoinbaseAdvancedTradeOrderBook._market_trades_order_book_message(
            msg=msg,
            symbol_to_pair=self.symbol_to_pair
        )
        self.assertIsNone(out)

    async def test_market_trades_order_book_message_missing_fields(self):
        msg = {"type": "market_trades", "data": {"id": 1, "time": "2022-01-01T00:00:00.000Z"}}
        # This raises because this message is missing the 'events' field
        # (which normally should be handled by the calling method)
        with self.assertRaises(KeyError):
            await CoinbaseAdvancedTradeOrderBook._market_trades_order_book_message(
                msg=msg,
                symbol_to_pair=self.symbol_to_pair
            )
