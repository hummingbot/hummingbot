from collections import OrderedDict
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder

if TYPE_CHECKING:
    from hummingbot.connector.connector_base import ConnectorBase


class GatewayOrderTracker(ClientOrderTracker):

    def __init__(self, connector: "ConnectorBase", lost_order_count_limit: int = 3) -> None:
        """
        Provides utilities for connectors to update in-flight orders and also handle order errors.
        Also it maintains cached orders to allow for additional updates to occur after the original order
        is determined to no longer be active.
        An error constitutes, but is not limited to, the following:
        (1) Order not found on exchange.
        (2) Cannot retrieve exchange_order_id of an order
        (3) Error thrown by exchange when fetching order status
        """
        super().__init__(connector=connector, lost_order_count_limit=lost_order_count_limit)
        # For some DEXes it is important to process orders in the same order they were created
        self._lost_orders: Dict[str, GatewayInFlightOrder] = OrderedDict()

    @property
    def all_fillable_orders_by_hash(self) -> Dict[str, GatewayInFlightOrder]:
        """
        :return: A dictionary of hashes (both creation and cancelation) to in-flight order.
        """
        orders_by_hashes = {}
        order: GatewayInFlightOrder
        for order in self.all_fillable_orders.values():
            if order.creation_transaction_hash is not None:
                orders_by_hashes[order.creation_transaction_hash] = order
            if order.cancel_tx_hash is not None:
                orders_by_hashes[order.cancel_tx_hash] = order
        return orders_by_hashes

    def get_fillable_order_by_hash(self, transaction_hash: str) -> Optional[GatewayInFlightOrder]:
        order = self.all_fillable_orders_by_hash.get(transaction_hash)
        return order

    @staticmethod
    def _restore_order_from_json(serialized_order: Dict) -> GatewayInFlightOrder:
        order = GatewayInFlightOrder.from_json(serialized_order)
        return order
