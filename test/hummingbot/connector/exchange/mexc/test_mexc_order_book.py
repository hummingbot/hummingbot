from unittest import TestCase

from hummingbot.connector.exchange.mexc.mexc_order_book import MexcOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class MexcOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = MexcOrderBook.snapshot_message_from_exchange(
            msg={
                "lastUpdateId": 1,
                "bids": [
                    ["4.00000000", "431.00000000"]
                ],
                "asks": [
                    ["4.00000200", "12.00000000"]
                ]
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "BTC-USDC"}
        )

        self.assertEqual("BTC-USDC", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1640000000.0, snapshot_message.timestamp)
        self.assertEqual(1, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(1, len(snapshot_message.bids))
        self.assertEqual(4.0, snapshot_message.bids[0].price)
        self.assertEqual(431.0, snapshot_message.bids[0].amount)
        self.assertEqual(1, snapshot_message.bids[0].update_id)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(4.000002, snapshot_message.asks[0].price)
        self.assertEqual(12.0, snapshot_message.asks[0].amount)
        self.assertEqual(1, snapshot_message.asks[0].update_id)

    def test_diff_message_from_exchange(self):
        diff_msg = MexcOrderBook.diff_message_from_exchange(
            msg={
                "channel": "spot@public.aggre.depth.v3.api.pb@100ms@BTCUSDC",
                "symbol": "BTCUSDC",
                "sendTime": "1755973885809",
                "publicAggreDepths": {
                    "bids": [
                        {
                            "price": "114838.84",
                            "quantity": "0.000101"
                        }
                    ],
                    "asks": [
                        {
                            "price": "115198.74",
                            "quantity": "0.068865"
                        }
                    ],
                    "eventType": "spot@public.aggre.depth.v3.api.pb@100ms",
                    "fromVersion": "17521975448",
                    "toVersion": "17521975455"
                }
            },
            timestamp=float("1755973885809"),
            metadata={"trading_pair": "BTC-USDC"}
        )

        self.assertEqual("BTC-USDC", diff_msg.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_msg.type)
        self.assertEqual(1755973885809 * 1e-3, diff_msg.timestamp)
        self.assertEqual(1755973885809, diff_msg.update_id)
        self.assertEqual(-1, diff_msg.trade_id)
        self.assertEqual(1, len(diff_msg.bids))
        self.assertEqual(114838.84, diff_msg.bids[0].price)
        self.assertEqual(0.000101, diff_msg.bids[0].amount)
        self.assertEqual(1755973885809, diff_msg.bids[0].update_id)
        self.assertEqual(1, len(diff_msg.asks))
        self.assertEqual(115198.74, diff_msg.asks[0].price)
        self.assertEqual(0.068865, diff_msg.asks[0].amount)
        self.assertEqual(1755973885809, diff_msg.asks[0].update_id)

    def test_trade_message_from_exchange(self):
        trade_update = {
            "price": "115091.25",
            "quantity": "0.000059",
            "tradeType": 1,
            "time": "1755973886258"
        }

        trade_message = MexcOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "BTC-USDC"},
            timestamp=float('1755973886258')
        )

        self.assertEqual("BTC-USDC", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1755973886258 * 1e-3, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual('1755973886258', trade_message.trade_id)
