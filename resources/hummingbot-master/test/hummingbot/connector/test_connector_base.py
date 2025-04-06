import copy
import unittest
import unittest.mock
from decimal import Decimal
from typing import Dict, List

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.connector_base import ConnectorBase, OrderFilledEvent
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee


class InFightOrderTest(InFlightOrderBase):
    @property
    def is_done(self) -> bool:
        return False

    @property
    def is_cancelled(self) -> bool:
        return False

    @property
    def is_failure(self) -> bool:
        return False


class MockTestConnector(ConnectorBase):

    def __init__(self, client_config_map: "ClientConfigAdapter"):
        super().__init__(client_config_map)
        self._in_flight_orders = {}
        self._event_logs = []

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._in_flight_orders

    @property
    def event_logs(self) -> List:
        return self._event_logs


class ConnectorBaseUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._patcher = unittest.mock.patch("hummingbot.connector.connector_base.estimate_fee")
        cls._url_mock = cls._patcher.start()
        cls._url_mock.return_value = AddedToCostTradeFee(percent=Decimal("0"), flat_fees=[])

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patcher.stop()

    def test_in_flight_asset_balances(self):
        connector = ConnectorBase(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        connector.real_time_balance_update = True
        orders = {
            "1": InFightOrderTest("1", "A", "HBOT-USDT", OrderType.LIMIT, TradeType.BUY, 100, 1, 1640001112.0, "live"),
            "2": InFightOrderTest("2", "B", "HBOT-USDT", OrderType.LIMIT, TradeType.BUY, 100, 2, 1640001112.0, "live"),
            "3": InFightOrderTest("3", "C", "HBOT-USDT", OrderType.LIMIT, TradeType.SELL, 110,
                                  Decimal("1.5"), 1640001112.0, "live")
        }
        bals = connector.in_flight_asset_balances(orders)
        self.assertEqual(Decimal("300"), bals["USDT"])
        self.assertEqual(Decimal("1.5"), bals["HBOT"])

    def test_estimated_available_balance_with_no_order_during_snapshot_is_the_registered_available_balance(self):
        connector = MockTestConnector(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        connector.real_time_balance_update = True
        connector.in_flight_orders_snapshot = {}

        initial_balance = Decimal("1000")
        estimated_balance = connector.apply_balance_update_since_snapshot(
            currency="HBOT",
            available_balance=initial_balance)

        self.assertEqual(initial_balance, estimated_balance)

    def test_estimated_available_balance_with_unfilled_orders_during_snapshot_and_no_current_orders(self):
        # Considers the case where the balance update was done when two orders were alive
        # The orders were then cancelled and the available balance is calculated after the cancellation
        # but before the new balance update

        connector = MockTestConnector(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        connector.real_time_balance_update = True
        connector.in_flight_orders_snapshot = {}

        initial_coinalpha_balance = Decimal("10")
        initial_hbot_balance = Decimal("100000")

        initial_buy_order = InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="1234",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("900"),
            amount=Decimal("1"),
            creation_timestamp=1640000000
        )
        initial_sell_order = InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="1235",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("1100"),
            amount=Decimal("0.5"),
            creation_timestamp=1640000000
        )

        connector.in_flight_orders_snapshot = {order.client_order_id: order for order
                                               in [initial_buy_order, initial_sell_order]}
        connector.in_flight_orders_snapshot_timestamp = 1640000000

        estimated_coinalpha_balance = connector.apply_balance_update_since_snapshot(
            currency="COINALPHA",
            available_balance=initial_coinalpha_balance)
        estimated_hbot_balance = connector.apply_balance_update_since_snapshot(
            currency="HBOT",
            available_balance=initial_hbot_balance)

        self.assertEqual(initial_coinalpha_balance + initial_sell_order.amount, estimated_coinalpha_balance)
        self.assertEqual(initial_hbot_balance + (initial_buy_order.amount * initial_buy_order.price),
                         estimated_hbot_balance)

    def test_estimated_available_balance_with_no_orders_during_snapshot_and_two_current_orders(self):
        # Considers the case where the balance update was done when no orders were alive
        # At the moment of calculating the available balance there are two live orders

        connector = MockTestConnector(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        connector.real_time_balance_update = True
        connector.in_flight_orders_snapshot = {}

        initial_coinalpha_balance = Decimal("10")
        initial_hbot_balance = Decimal("100000")

        buy_order = InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="1234",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("900"),
            amount=Decimal("1"),
            creation_timestamp=1640000000
        )
        sell_order = InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="1235",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("1100"),
            amount=Decimal("0.5"),
            creation_timestamp=1640000000
        )

        connector.in_flight_orders_snapshot = {}
        connector.in_flight_orders_snapshot_timestamp = 1640000000
        connector._in_flight_orders = {order.client_order_id: order for order in [buy_order, sell_order]}

        estimated_coinalpha_balance = connector.apply_balance_update_since_snapshot(
            currency="COINALPHA",
            available_balance=initial_coinalpha_balance)
        estimated_hbot_balance = connector.apply_balance_update_since_snapshot(
            currency="HBOT",
            available_balance=initial_hbot_balance)

        self.assertEqual(initial_coinalpha_balance - sell_order.amount, estimated_coinalpha_balance)
        self.assertEqual(initial_hbot_balance - (buy_order.amount * buy_order.price),
                         estimated_hbot_balance)

    def test_estimated_available_balance_with_unfilled_orders_during_snapshot_that_are_still_alive(self):
        # Considers the case where the balance update was done when two orders were alive
        # The orders are still alive when calculating the available balance

        connector = MockTestConnector(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        connector.real_time_balance_update = True
        connector.in_flight_orders_snapshot = {}

        initial_coinalpha_balance = Decimal("10")
        initial_hbot_balance = Decimal("100000")

        initial_buy_order = InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="1234",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("900"),
            amount=Decimal("1"),
            creation_timestamp=1640000000
        )
        initial_sell_order = InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="1235",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("1100"),
            amount=Decimal("0.5"),
            creation_timestamp=1640000000
        )

        connector.in_flight_orders_snapshot = {order.client_order_id: order for order
                                               in [initial_buy_order, initial_sell_order]}
        connector.in_flight_orders_snapshot_timestamp = 1640000000
        connector._in_flight_orders = {order.client_order_id: order for order
                                       in [copy.copy(initial_buy_order), copy.copy(initial_sell_order)]}

        estimated_coinalpha_balance = connector.apply_balance_update_since_snapshot(
            currency="COINALPHA",
            available_balance=initial_coinalpha_balance)
        estimated_hbot_balance = connector.apply_balance_update_since_snapshot(
            currency="HBOT",
            available_balance=initial_hbot_balance)

        self.assertEqual(initial_coinalpha_balance, estimated_coinalpha_balance)
        self.assertEqual(initial_hbot_balance, estimated_hbot_balance)

    def test_estimated_available_balance_with_no_orders_during_snapshot_no_alive_orders_and_a_fill_event(self):
        connector = MockTestConnector(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        connector.real_time_balance_update = True
        connector.in_flight_orders_snapshot = {}

        initial_coinalpha_balance = Decimal("10")
        initial_hbot_balance = Decimal("100000")

        connector.in_flight_orders_snapshot = {}
        connector.in_flight_orders_snapshot_timestamp = 1640000000
        connector._in_flight_orders = {}

        fill_event = OrderFilledEvent(
            timestamp=1640000002,
            order_id="OID1",
            trading_pair="COINALPHA-HBOT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal(1050),
            amount=Decimal(2),
            trade_fee=AddedToCostTradeFee(),
        )
        connector._event_logs.append(fill_event)

        estimated_coinalpha_balance = connector.apply_balance_update_since_snapshot(
            currency="COINALPHA",
            available_balance=initial_coinalpha_balance)
        estimated_hbot_balance = connector.apply_balance_update_since_snapshot(
            currency="HBOT",
            available_balance=initial_hbot_balance)

        self.assertEqual(initial_coinalpha_balance + fill_event.amount, estimated_coinalpha_balance)
        self.assertEqual(initial_hbot_balance - (fill_event.amount * fill_event.price),
                         estimated_hbot_balance)

    def test_fill_event_previous_to_balance_updated_is_ignored_for_estimated_available_balance(self):
        connector = MockTestConnector(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        connector.real_time_balance_update = True
        connector.in_flight_orders_snapshot = {}

        initial_coinalpha_balance = Decimal("10")
        initial_hbot_balance = Decimal("100000")

        connector.in_flight_orders_snapshot = {}
        connector.in_flight_orders_snapshot_timestamp = 1640000000
        connector._in_flight_orders = {}

        fill_event = OrderFilledEvent(
            timestamp=1630000999,
            order_id="OID1",
            trading_pair="COINALPHA-HBOT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal(1050),
            amount=Decimal(2),
            trade_fee=AddedToCostTradeFee(),
        )
        connector._event_logs.append(fill_event)

        estimated_coinalpha_balance = connector.apply_balance_update_since_snapshot(
            currency="COINALPHA",
            available_balance=initial_coinalpha_balance)
        estimated_hbot_balance = connector.apply_balance_update_since_snapshot(
            currency="HBOT",
            available_balance=initial_hbot_balance)

        self.assertEqual(initial_coinalpha_balance, estimated_coinalpha_balance)
        self.assertEqual(initial_hbot_balance, estimated_hbot_balance)

    def test_estimated_available_balance_with_partially_filled_orders_during_snapshot_and_no_current_orders(self):
        # Considers the case where the balance update was done when two orders were alive and partially filled
        # The orders were then cancelled and the available balance is calculated after the cancellation
        # but before the new balance update

        connector = MockTestConnector(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        connector.real_time_balance_update = True
        connector.in_flight_orders_snapshot = {}

        initial_coinalpha_balance = Decimal("10")
        initial_hbot_balance = Decimal("100000")

        initial_buy_order = InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="1234",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("900"),
            amount=Decimal("1"),
            creation_timestamp=1640000000
        )
        initial_sell_order = InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="1235",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("1100"),
            amount=Decimal("0.5"),
            creation_timestamp=1640000000
        )

        connector.in_flight_orders_snapshot = {order.client_order_id: order for order
                                               in [initial_buy_order, initial_sell_order]}
        connector.in_flight_orders_snapshot_timestamp = 1640000000

        buy_fill_event = OrderFilledEvent(
            timestamp=1630000999,
            order_id=initial_buy_order.client_order_id,
            trading_pair=initial_buy_order.trading_pair,
            trade_type=initial_buy_order.trade_type,
            order_type=initial_buy_order.order_type,
            price=Decimal(950),
            amount=Decimal("0.5"),
            trade_fee=AddedToCostTradeFee(),
        )
        connector._event_logs.append(buy_fill_event)
        initial_buy_order.executed_amount_base = buy_fill_event.amount
        initial_buy_order.executed_amount_quote = buy_fill_event.amount * buy_fill_event.price

        sell_fill_event = OrderFilledEvent(
            timestamp=1630000999,
            order_id=initial_sell_order.client_order_id,
            trading_pair=initial_sell_order.trading_pair,
            trade_type=initial_sell_order.trade_type,
            order_type=initial_sell_order.order_type,
            price=Decimal(1120),
            amount=Decimal("0.1"),
            trade_fee=AddedToCostTradeFee(),
        )
        connector._event_logs.append(sell_fill_event)
        initial_sell_order.executed_amount_base = sell_fill_event.amount
        initial_sell_order.executed_amount_quote = sell_fill_event.amount * sell_fill_event.price

        estimated_coinalpha_balance = connector.apply_balance_update_since_snapshot(
            currency="COINALPHA",
            available_balance=initial_coinalpha_balance)
        estimated_hbot_balance = connector.apply_balance_update_since_snapshot(
            currency="HBOT",
            available_balance=initial_hbot_balance)

        # The partial fills prior to the balance update are already impacted in the balance
        # Only the unfilled part of the orders should be recovered once they are gone
        self.assertEqual(initial_coinalpha_balance + initial_sell_order.amount - sell_fill_event.amount,
                         estimated_coinalpha_balance)
        expected_hbot_amount = (initial_hbot_balance
                                + (initial_buy_order.amount - initial_buy_order.executed_amount_base) * initial_buy_order.price)
        self.assertEqual(expected_hbot_amount, estimated_hbot_balance)

    def test_estimated_available_balance_with_partially_filled_orders_during_snapshot_that_are_still_alive(self):
        # Considers the case where the balance update was done when two orders were alive and partially filled
        # The orders are still alive with no more fills

        connector = MockTestConnector(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        connector.real_time_balance_update = True
        connector.in_flight_orders_snapshot = {}

        initial_coinalpha_balance = Decimal("10")
        initial_hbot_balance = Decimal("100000")

        initial_buy_order = InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="1234",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("900"),
            amount=Decimal("1"),
            creation_timestamp=1640000000
        )
        initial_sell_order = InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="1235",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("1100"),
            amount=Decimal("0.5"),
            creation_timestamp=1640000000
        )

        connector.in_flight_orders_snapshot = {order.client_order_id: order for order
                                               in [initial_buy_order, initial_sell_order]}
        connector.in_flight_orders_snapshot_timestamp = 1640000000

        buy_fill_event = OrderFilledEvent(
            timestamp=1630000999,
            order_id=initial_buy_order.client_order_id,
            trading_pair=initial_buy_order.trading_pair,
            trade_type=initial_buy_order.trade_type,
            order_type=initial_buy_order.order_type,
            price=Decimal(950),
            amount=Decimal("0.5"),
            trade_fee=AddedToCostTradeFee(),
        )
        connector._event_logs.append(buy_fill_event)
        initial_buy_order.executed_amount_base = buy_fill_event.amount
        initial_buy_order.executed_amount_quote = buy_fill_event.amount * buy_fill_event.price

        sell_fill_event = OrderFilledEvent(
            timestamp=1630000999,
            order_id=initial_sell_order.client_order_id,
            trading_pair=initial_sell_order.trading_pair,
            trade_type=initial_sell_order.trade_type,
            order_type=initial_sell_order.order_type,
            price=Decimal(1120),
            amount=Decimal("0.1"),
            trade_fee=AddedToCostTradeFee(),
        )
        connector._event_logs.append(sell_fill_event)
        initial_sell_order.executed_amount_base = sell_fill_event.amount
        initial_sell_order.executed_amount_quote = sell_fill_event.amount * sell_fill_event.price

        connector._in_flight_orders = {order.client_order_id: order for order
                                       in [copy.copy(initial_buy_order), copy.copy(initial_sell_order)]}

        estimated_coinalpha_balance = connector.apply_balance_update_since_snapshot(
            currency="COINALPHA",
            available_balance=initial_coinalpha_balance)
        estimated_hbot_balance = connector.apply_balance_update_since_snapshot(
            currency="HBOT",
            available_balance=initial_hbot_balance)

        # The partial fills prior to the balance update are already impacted in the balance
        self.assertEqual(initial_coinalpha_balance, estimated_coinalpha_balance)
        self.assertEqual(initial_hbot_balance, estimated_hbot_balance)

    def test_estimated_available_balance_with_unfilled_orders_during_snapshot_two_current_partial_filled_and_extra_fill(self):
        # Considers the case where the balance update was done when two orders were alive
        # Currently those initial orders are gone, and there are two new partially filled orders
        # There is an extra fill event for an order no longer present

        connector = MockTestConnector(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        connector.real_time_balance_update = True
        connector.in_flight_orders_snapshot = {}

        initial_coinalpha_balance = Decimal("10")
        initial_hbot_balance = Decimal("100000")

        initial_buy_order = InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="1234",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("900"),
            amount=Decimal("1"),
            creation_timestamp=1640000000
        )
        initial_sell_order = InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="1235",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("1100"),
            amount=Decimal("0.5"),
            creation_timestamp=1640000000
        )

        connector.in_flight_orders_snapshot = {order.client_order_id: order for order
                                               in [initial_buy_order, initial_sell_order]}
        connector.in_flight_orders_snapshot_timestamp = 1640000000

        current_buy_order = InFlightOrder(
            client_order_id="OID3",
            exchange_order_id="1236",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("900"),
            amount=Decimal("1"),
            creation_timestamp=1640100000
        )
        current_sell_order = InFlightOrder(
            client_order_id="OID4",
            exchange_order_id="1237",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("1100"),
            amount=Decimal("0.5"),
            creation_timestamp=1640100000
        )

        connector._in_flight_orders = {order.client_order_id: order for order
                                       in [current_buy_order, current_sell_order]}

        buy_fill_event = OrderFilledEvent(
            timestamp=1640100999,
            order_id=current_buy_order.client_order_id,
            trading_pair=current_buy_order.trading_pair,
            trade_type=current_buy_order.trade_type,
            order_type=current_buy_order.order_type,
            price=Decimal(950),
            amount=Decimal("0.5"),
            trade_fee=AddedToCostTradeFee(),
        )
        connector._event_logs.append(buy_fill_event)
        current_buy_order.executed_amount_base = buy_fill_event.amount
        current_buy_order.executed_amount_quote = buy_fill_event.amount * buy_fill_event.price

        sell_fill_event = OrderFilledEvent(
            timestamp=1640100999,
            order_id=current_sell_order.client_order_id,
            trading_pair=current_sell_order.trading_pair,
            trade_type=current_sell_order.trade_type,
            order_type=current_sell_order.order_type,
            price=Decimal(1120),
            amount=Decimal("0.1"),
            trade_fee=AddedToCostTradeFee(),
        )
        connector._event_logs.append(sell_fill_event)
        current_sell_order.executed_amount_base = sell_fill_event.amount
        current_sell_order.executed_amount_quote = sell_fill_event.amount * sell_fill_event.price

        extra_fill_event = OrderFilledEvent(
            timestamp=1640101999,
            order_id="OID99",
            trading_pair="COINALPHA-HBOT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal(1000),
            amount=Decimal(3),
            trade_fee=AddedToCostTradeFee(),
        )
        connector._event_logs.append(extra_fill_event)

        estimated_coinalpha_balance = connector.apply_balance_update_since_snapshot(
            currency="COINALPHA",
            available_balance=initial_coinalpha_balance)
        estimated_hbot_balance = connector.apply_balance_update_since_snapshot(
            currency="HBOT",
            available_balance=initial_hbot_balance)

        expected_coinalpha_amount = (initial_coinalpha_balance
                                     + initial_sell_order.amount
                                     + current_buy_order.executed_amount_base
                                     - current_sell_order.amount
                                     + extra_fill_event.amount)
        self.assertEqual(expected_coinalpha_amount, estimated_coinalpha_balance)
        expected_hbot_amount = (initial_hbot_balance
                                + (initial_buy_order.amount * initial_buy_order.price)
                                - ((current_buy_order.amount - current_buy_order.executed_amount_base) * current_buy_order.price)
                                - (current_buy_order.executed_amount_quote)
                                + (current_sell_order.executed_amount_quote)
                                - (extra_fill_event.amount * extra_fill_event.price))
        self.assertEqual(expected_hbot_amount, estimated_hbot_balance)
