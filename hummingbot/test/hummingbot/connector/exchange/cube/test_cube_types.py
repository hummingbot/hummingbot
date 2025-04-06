import unittest

from hummingbot.connector.exchange.cube.cube_ws_protobufs import market_data_pb2, trade_pb2


class CubeTypesTestCases(unittest.TestCase):

    def test_bootstrap_message(self):
        position = trade_pb2.AssetPosition(
            subaccount_id=1,
            asset_id=2,
            total=trade_pb2.RawUnits(
                word0=1000
            ),
            available=trade_pb2.RawUnits(
                word0=500
            )
        )

        positions = trade_pb2.AssetPositions(
            positions=[position]
        )

        bootstrap_message = trade_pb2.Bootstrap(
            position=positions
        ).SerializeToString()

        # Check if bootstrap_message is of type bytes
        self.assertIsInstance(bootstrap_message, bytes)
        self.assertTrue(bootstrap_message)

        # Decode the bootstrap_message and check for position field
        decoded_bootstrap_message: trade_pb2.Bootstrap = trade_pb2.Bootstrap().FromString(bootstrap_message)
        self.assertTrue(decoded_bootstrap_message.HasField("position"))

        for position in decoded_bootstrap_message.position.positions:
            self.assertEqual(position.subaccount_id, 1)
            self.assertEqual(position.asset_id, 2)
            self.assertEqual(position.total.word0, 1000)
            self.assertEqual(position.available.word0, 500)

        done = trade_pb2.Done(
            latest_transact_time=12345,
            read_only=True
        )

        done_bootstrap_message = trade_pb2.Bootstrap(
            done=done
        ).SerializeToString()

        self.assertIsInstance(done_bootstrap_message, bytes)
        self.assertTrue(done_bootstrap_message)

        decoded_done_bootstrap_message: trade_pb2.Bootstrap = trade_pb2.Bootstrap().FromString(done_bootstrap_message)
        self.assertTrue(decoded_done_bootstrap_message.HasField("done"))
        self.assertEqual(decoded_done_bootstrap_message.done.latest_transact_time, 12345)
        self.assertEqual(decoded_done_bootstrap_message.done.read_only, True)

    def test_order_response_message_new_ack(self):
        new_ack = trade_pb2.NewOrderAck(
            msg_seq_num=1,
            client_order_id=2,
            request_id=3,
            exchange_order_id=4,
            market_id=5,
            price=6,
            quantity=7,
            side=trade_pb2.Side.BID,
            time_in_force=trade_pb2.TimeInForce.GOOD_FOR_SESSION,
            order_type=trade_pb2.OrderType.LIMIT,
            transact_time=8,
            subaccount_id=9,
            cancel_on_disconnect=True
        )

        order_response_message: trade_pb2.OrderResponse = trade_pb2.OrderResponse(
            new_ack=new_ack
        ).SerializeToString()

        self.assertIsInstance(order_response_message, bytes)
        self.assertTrue(order_response_message)

        decoded_order_response_message: trade_pb2.OrderResponse = trade_pb2.OrderResponse().FromString(
            order_response_message)
        self.assertTrue(decoded_order_response_message.HasField("new_ack"))
        self.assertEqual(decoded_order_response_message.new_ack.msg_seq_num, 1)
        self.assertEqual(decoded_order_response_message.new_ack.client_order_id, 2)
        self.assertEqual(decoded_order_response_message.new_ack.request_id, 3)
        self.assertEqual(decoded_order_response_message.new_ack.exchange_order_id, 4)
        self.assertEqual(decoded_order_response_message.new_ack.market_id, 5)
        self.assertEqual(decoded_order_response_message.new_ack.price, 6)
        self.assertEqual(decoded_order_response_message.new_ack.quantity, 7)
        self.assertEqual(decoded_order_response_message.new_ack.side, trade_pb2.Side.BID)
        self.assertEqual(decoded_order_response_message.new_ack.time_in_force, trade_pb2.TimeInForce.GOOD_FOR_SESSION)
        self.assertEqual(decoded_order_response_message.new_ack.order_type, trade_pb2.OrderType.LIMIT)
        self.assertEqual(decoded_order_response_message.new_ack.transact_time, 8)
        self.assertEqual(decoded_order_response_message.new_ack.subaccount_id, 9)
        self.assertEqual(decoded_order_response_message.new_ack.cancel_on_disconnect, True)

    def test_order_response_message_cancel_ack(self):
        cancel_ack = trade_pb2.CancelOrderAck(
            msg_seq_num=1,
            client_order_id=2,
            request_id=3,
            transact_time=4,
            subaccount_id=5,
            reason=trade_pb2.CancelOrderAck.Reason.REQUESTED,
            market_id=6,
            exchange_order_id=7
        )

        order_response_message: trade_pb2.OrderResponse = trade_pb2.OrderResponse(
            cancel_ack=cancel_ack
        ).SerializeToString()

        self.assertIsInstance(order_response_message, bytes)
        self.assertTrue(order_response_message)

        decoded_order_response_message: trade_pb2.OrderResponse = trade_pb2.OrderResponse().FromString(
            order_response_message)
        self.assertTrue(decoded_order_response_message.HasField("cancel_ack"))
        self.assertEqual(decoded_order_response_message.cancel_ack.msg_seq_num, 1)
        self.assertEqual(decoded_order_response_message.cancel_ack.client_order_id, 2)
        self.assertEqual(decoded_order_response_message.cancel_ack.request_id, 3)
        self.assertEqual(decoded_order_response_message.cancel_ack.transact_time, 4)
        self.assertEqual(decoded_order_response_message.cancel_ack.subaccount_id, 5)
        self.assertEqual(decoded_order_response_message.cancel_ack.reason, trade_pb2.CancelOrderAck.Reason.REQUESTED)
        self.assertEqual(decoded_order_response_message.cancel_ack.market_id, 6)
        self.assertEqual(decoded_order_response_message.cancel_ack.exchange_order_id, 7)

    def test_order_response_new_reject(self):
        new_reject = trade_pb2.NewOrderReject(
            msg_seq_num=1,
            client_order_id=2,
            request_id=3,
            transact_time=4,
            subaccount_id=5,
            reason=trade_pb2.NewOrderReject.Reason.DUPLICATE_ORDER_ID,
            market_id=6,
            price=7,
            quantity=8,
            side=trade_pb2.Side.BID,
            time_in_force=trade_pb2.TimeInForce.GOOD_FOR_SESSION,
            order_type=trade_pb2.OrderType.LIMIT
        )

        order_response_message: trade_pb2.OrderResponse = trade_pb2.OrderResponse(
            new_reject=new_reject
        ).SerializeToString()

        self.assertIsInstance(order_response_message, bytes)
        self.assertTrue(order_response_message)

        decoded_order_response_message: trade_pb2.OrderResponse = trade_pb2.OrderResponse().FromString(
            order_response_message)
        self.assertTrue(decoded_order_response_message.HasField("new_reject"))
        self.assertEqual(decoded_order_response_message.new_reject.msg_seq_num, 1)
        self.assertEqual(decoded_order_response_message.new_reject.client_order_id, 2)
        self.assertEqual(decoded_order_response_message.new_reject.request_id, 3)
        self.assertEqual(decoded_order_response_message.new_reject.transact_time, 4)
        self.assertEqual(decoded_order_response_message.new_reject.subaccount_id, 5)
        self.assertEqual(decoded_order_response_message.new_reject.reason,
                         trade_pb2.NewOrderReject.Reason.DUPLICATE_ORDER_ID)
        self.assertEqual(decoded_order_response_message.new_reject.market_id, 6)
        self.assertEqual(decoded_order_response_message.new_reject.price, 7)
        self.assertEqual(decoded_order_response_message.new_reject.quantity, 8)
        self.assertEqual(decoded_order_response_message.new_reject.side, trade_pb2.Side.BID)
        self.assertEqual(decoded_order_response_message.new_reject.time_in_force,
                         trade_pb2.TimeInForce.GOOD_FOR_SESSION)
        self.assertEqual(decoded_order_response_message.new_reject.order_type, trade_pb2.OrderType.LIMIT)

    def test_order_response_position(self):
        position = trade_pb2.AssetPosition(
            subaccount_id=1,
            asset_id=2,
            total=trade_pb2.RawUnits(
                word0=1000
            ),
            available=trade_pb2.RawUnits(
                word0=500
            )
        )

        order_response_message: trade_pb2.OrderResponse = trade_pb2.OrderResponse(
            position=position
        ).SerializeToString()

        self.assertIsInstance(order_response_message, bytes)
        self.assertTrue(order_response_message)

        decoded_order_response_message: trade_pb2.OrderResponse = trade_pb2.OrderResponse().FromString(
            order_response_message)
        self.assertTrue(decoded_order_response_message.HasField("position"))

        self.assertEqual(decoded_order_response_message.position.subaccount_id, 1)
        self.assertEqual(decoded_order_response_message.position.asset_id, 2)
        self.assertEqual(decoded_order_response_message.position.total.word0, 1000)
        self.assertEqual(decoded_order_response_message.position.available.word0, 500)

    def test_order_response_fill(self):
        fill = trade_pb2.Fill(
            msg_seq_num=1,
            market_id=2,
            client_order_id=3,
            exchange_order_id=4,
            fill_price=5,
            fill_quantity=6,
            leaves_quantity=7,
            transact_time=8,
            subaccount_id=9,
            cumulative_quantity=10,
            side=trade_pb2.Side.BID,
            aggressor_indicator=True,
            fee_ratio=trade_pb2.FixedPointDecimal(
                mantissa=4,
                exponent=5
            ),
            trade_id=12
        )

        order_response_message: trade_pb2.OrderResponse = trade_pb2.OrderResponse(
            fill=fill
        ).SerializeToString()

        self.assertIsInstance(order_response_message, bytes)
        self.assertTrue(order_response_message)

        decoded_order_response_message: trade_pb2.OrderResponse = trade_pb2.OrderResponse().FromString(
            order_response_message)
        self.assertTrue(decoded_order_response_message.HasField("fill"))

        self.assertEqual(decoded_order_response_message.fill.msg_seq_num, 1)
        self.assertEqual(decoded_order_response_message.fill.market_id, 2)
        self.assertEqual(decoded_order_response_message.fill.client_order_id, 3)
        self.assertEqual(decoded_order_response_message.fill.exchange_order_id, 4)
        self.assertEqual(decoded_order_response_message.fill.fill_price, 5)
        self.assertEqual(decoded_order_response_message.fill.fill_quantity, 6)
        self.assertEqual(decoded_order_response_message.fill.leaves_quantity, 7)
        self.assertEqual(decoded_order_response_message.fill.transact_time, 8)
        self.assertEqual(decoded_order_response_message.fill.subaccount_id, 9)
        self.assertEqual(decoded_order_response_message.fill.cumulative_quantity, 10)
        self.assertEqual(decoded_order_response_message.fill.side, trade_pb2.Side.BID)
        self.assertEqual(decoded_order_response_message.fill.aggressor_indicator, True)
        self.assertEqual(decoded_order_response_message.fill.fee_ratio.mantissa, 4)
        self.assertEqual(decoded_order_response_message.fill.fee_ratio.exponent, 5)
        self.assertEqual(decoded_order_response_message.fill.trade_id, 12)

    def test_trade_message(self):
        trade = market_data_pb2.Trades.Trade(
            tradeId=1,
            price=2,
            aggressing_side=market_data_pb2.Side.BID,
            resting_exchange_order_id=3,
            fill_quantity=4,
            transact_time=5,
            aggressing_exchange_order_id=6
        )

        trades_message = market_data_pb2.Trades(
            trades=[trade]
        )

        market_data_message: market_data_pb2.MdMessage = market_data_pb2.MdMessage(
            trades=trades_message
        ).SerializeToString()

        self.assertIsInstance(market_data_message, bytes)
        self.assertTrue(market_data_message)

        decoded_market_data_message: market_data_pb2.MdMessage = market_data_pb2.MdMessage().FromString(market_data_message)
        field = decoded_market_data_message.WhichOneof('inner')

        self.assertEqual(field, "trades")

        trades: market_data_pb2.Trades = decoded_market_data_message.trades
        trade: market_data_pb2.Trades.Trade

        for trade in trades.trades:
            self.assertEqual(trade.tradeId, 1)
            self.assertEqual(trade.price, 2)
            self.assertEqual(trade.aggressing_side, market_data_pb2.Side.BID)
            self.assertEqual(trade.resting_exchange_order_id, 3)
            self.assertEqual(trade.fill_quantity, 4)
            self.assertEqual(trade.transact_time, 5)
            self.assertEqual(trade.aggressing_exchange_order_id, 6)

    def test_diff_message(self):
        diff = market_data_pb2.MarketByPriceDiff.Diff(
            price=3,
            quantity=4,
            side=market_data_pb2.Side.BID,
            op=market_data_pb2.MarketByPriceDiff.DiffOp.REPLACE
        )

        # diffs: _containers.RepeatedCompositeFieldContainer[MarketByPriceDiff.Diff]
        # total_bid_levels: int
        # total_ask_levels: int
        mbp_diff = market_data_pb2.MarketByPriceDiff(
            diffs=[diff],
            total_bid_levels=1,
            total_ask_levels=1
        )

        market_data_message: market_data_pb2.MdMessage = market_data_pb2.MdMessage(
            mbp_diff=mbp_diff
        ).SerializeToString()

        self.assertIsInstance(market_data_message, bytes)
        self.assertTrue(market_data_message)

        decoded_diff_message: market_data_pb2.MdMessage = market_data_pb2.MdMessage().FromString(market_data_message)
        field = decoded_diff_message.WhichOneof('inner')

        self.assertEqual(field, "mbp_diff")

        diff_msg: market_data_pb2.MarketByPriceDiff = decoded_diff_message.mbp_diff
        diff: market_data_pb2.MarketByPriceDiff.Diff

        for diff in diff_msg.diffs:
            self.assertEqual(diff.price, 3)
            self.assertEqual(diff.quantity, 4)
            self.assertEqual(diff.side, market_data_pb2.Side.BID)
            self.assertEqual(diff.op, market_data_pb2.MarketByPriceDiff.DiffOp.REPLACE)
