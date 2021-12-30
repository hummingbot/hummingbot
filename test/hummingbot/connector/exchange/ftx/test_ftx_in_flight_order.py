from datetime import datetime
from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.ftx.ftx_in_flight_order import FtxInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class FtxInFlightOrderTests(TestCase):

    def setUp(self):
        super().setUp()
        self.base_token = "BTC"
        self.quote_token = "USDT"
        self.trading_pair = f"{self.base_token}-{self.quote_token}"

    def test_creation_from_json(self):
        creation_timestamp = datetime.now().timestamp()
        order_info = {
            "client_order_id": "OID1",
            "exchange_order_id": "EOID1",
            "trading_pair": self.trading_pair,
            "order_type": OrderType.LIMIT.name,
            "trade_type": TradeType.BUY.name,
            "price": "1000",
            "amount": "1",
            "executed_amount_base": "0.5",
            "executed_amount_quote": "500",
            "fee_asset": "USDT",
            "fee_paid": "5",
            "last_state": "closed",
            "created_at": str(creation_timestamp)
        }

        order = FtxInFlightOrder.from_json(order_info)

        self.assertEqual(order_info["client_order_id"], order.client_order_id)
        self.assertEqual(order_info["exchange_order_id"], order.exchange_order_id)
        self.assertEqual(order_info["trading_pair"], order.trading_pair)
        self.assertEqual(OrderType.LIMIT, order.order_type)
        self.assertEqual(TradeType.BUY, order.trade_type)
        self.assertEqual(Decimal(order_info["price"]), order.price)
        self.assertEqual(Decimal(order_info["amount"]), order.amount)
        self.assertEqual(order_info["last_state"], order.last_state)
        self.assertEqual(Decimal(order_info["executed_amount_base"]), order.executed_amount_base)
        self.assertEqual(Decimal(order_info["executed_amount_quote"]), order.executed_amount_quote)
        self.assertEqual(Decimal(order_info["fee_paid"]), order.fee_paid)
        self.assertEqual(order_info["fee_asset"], order.fee_asset)
        self.assertEqual(order_info, order.to_json())

    def test_fee_asset_is_based_on_order_type(self):
        order = FtxInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            created_at=datetime.now().timestamp()
        )

        self.assertEqual(order.base_asset, order.fee_asset)

        order = FtxInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            created_at=datetime.now().timestamp()
        )

        self.assertEqual(order.base_asset, order.fee_asset)

        order = FtxInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            created_at=datetime.now().timestamp()
        )

        self.assertEqual(order.quote_asset, order.fee_asset)

    def test_update_with_partial_trade_event(self):
        order = FtxInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            created_at=datetime.now().timestamp()
        )

        trade_event_info = {
            "fee": 10.0,
            "feeRate": 0.0014,
            "feeCurrency": "ETH",
            "future": None,
            "id": 7828307,
            "liquidity": "taker",
            "market": "BTC-USDT",
            "orderId": 38065410,
            "tradeId": 1,
            "price": 10050.0,
            "side": "buy",
            "size": 0.1,
            "time": "2019-05-07T16:40:58.358438+00:00",
            "type": "order"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual(Decimal(str(trade_event_info["size"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["size"])) * Decimal(
            str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["feeCurrency"], order.fee_asset)

    def test_update_with_full_fill_trade_event(self):
        order = FtxInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            created_at=datetime.now().timestamp()
        )

        trade_event_info = {
            "fee": 10.0,
            "feeRate": 0.0014,
            "feeCurrency": "ETH",
            "future": None,
            "id": 7828307,
            "liquidity": "taker",
            "market": "BTC-USDT",
            "orderId": 38065410,
            "tradeId": 19129310,
            "price": 10050.0,
            "side": "buy",
            "size": 0.1,
            "time": "2019-05-07T16:40:58.358438+00:00",
            "type": "order"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual(Decimal(str(trade_event_info["size"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["size"])) * Decimal(
            str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["feeCurrency"], order.fee_asset)

        complete_event_info = {
            "fee": 50.0,
            "feeRate": 0.0014,
            "feeCurrency": "ETH",
            "future": None,
            "id": 7828307,
            "liquidity": "taker",
            "market": "BTC-USDT",
            "orderId": 38065410,
            "tradeId": 2,
            "price": 10060.0,
            "side": "buy",
            "size": 0.9,
            "time": "2019-05-07T16:40:58.358438+00:00",
            "type": "order"
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual(order.amount, order.executed_amount_base)
        expected_executed_quote_amount += Decimal(str(complete_event_info["size"])) * Decimal(
            str(complete_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["fee"]) + Decimal(complete_event_info["fee"]),
                         order.fee_paid)
        self.assertEqual(complete_event_info["feeCurrency"], order.fee_asset)

    def test_update_with_repeated_trade_id_is_ignored(self):
        order = FtxInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            created_at=datetime.now().timestamp()
        )

        trade_event_info = {
            "fee": 10.0,
            "feeRate": 0.0014,
            "feeCurrency": "ETH",
            "future": None,
            "id": 7828307,
            "liquidity": "taker",
            "market": "BTC-USDT",
            "orderId": 38065410,
            "tradeId": 1,
            "price": 10050.0,
            "side": "buy",
            "size": 0.1,
            "time": "2019-05-07T16:40:58.358438+00:00",
            "type": "order"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual(Decimal(str(trade_event_info["size"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["size"])) * Decimal(
            str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["feeCurrency"], order.fee_asset)

        complete_event_info = {
            "fee": 50.0,
            "feeRate": 0.0014,
            "feeCurrency": "ETH",
            "future": None,
            "id": 7828307,
            "liquidity": "taker",
            "market": "BTC-USDT",
            "orderId": 38065410,
            "tradeId": 1,
            "price": 10060.0,
            "side": "buy",
            "size": 0.9,
            "time": "2019-05-07T16:40:58.358438+00:00",
            "type": "order"
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertFalse(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual(Decimal(str(trade_event_info["size"])), order.executed_amount_base)
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["feeCurrency"], order.fee_asset)
