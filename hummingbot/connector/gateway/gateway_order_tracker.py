from typing import Dict, Optional

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder


class GatewayOrderTracker(ClientOrderTracker):
    @property
    def all_orders(self) -> Dict[str, GatewayInFlightOrder]:
        return super().all_orders

    @property
    def all_fillable_orders(self) -> Dict[str, GatewayInFlightOrder]:
        return super().all_fillable_orders

    @property
    def all_fillable_orders_by_hash(self) -> Dict[str, GatewayInFlightOrder]:
        """
        :return: A dictionary of hashes (both creation and cancelation) to in-flight order.
        """
        orders_by_hashes = {}
        for order in self.all_fillable_orders.values():
            if order.creation_transaction_hash is not None:
                orders_by_hashes[order.creation_transaction_hash] = order
            if order.cancel_tx_hash is not None:
                orders_by_hashes[order.cancel_tx_hash] = order
        return orders_by_hashes

    def get_fillable_order_by_hash(self, hash: str) -> Optional[GatewayInFlightOrder]:
        order = self.all_fillable_orders_by_hash.get(hash)
        return order

    def restore_tracking_states(self, tracking_states: Dict[str, any]):
        for serialized_order in tracking_states.values():
            order = GatewayInFlightOrder.from_json(serialized_order)
            if order.is_open:
                self.start_tracking_order(order)
