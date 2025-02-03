import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from hummingbot.connector.gateway.amm.gateway_amm_base import GatewayAMMBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
from hummingbot.core.gateway import check_transaction_exceptions
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather

s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")


class GatewaySolanaAMM(GatewayAMMBase):
    """
    Defines Solana-specific functions for interacting with AMM protocols via Gateway.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._get_gas_estimate_task = safe_ensure_future(self.get_gas_estimate())
        self._get_chain_info_task = safe_ensure_future(self.get_chain_info())

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._get_chain_info_task is not None:
            self._get_chain_info_task.cancel()
            self._get_chain_info_task = None
        if self._get_gas_estimate_task is not None:
            self._get_gas_estimate_task.cancel()
            self._get_chain_info_task = None

    async def _status_polling_loop(self):
        await self.update_balances(on_interval=False)
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self.update_balances(on_interval=True),
                    self.update_order_status(self.amm_orders)
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)

    def parse_price_response(
        self,
        base: str,
        quote: str,
        amount: Decimal,
        side: TradeType,
        price_response: Dict[str, Any],
        process_exception: bool = False
    ) -> Optional[Decimal]:
        """
        Parses price response
        :param base: The base asset
        :param quote: The quote asset
        :param amount: amount
        :param side: trade side
        :param price_response: Price response from Gateway.
        :param process_exception: Flag to trigger error on exception
        """
        required_items = ["price", "gasLimit", "gasPrice", "gasCost", "gasPriceToken"]
        if any(item not in price_response.keys() for item in required_items):
            if "info" in price_response.keys():
                self.logger().info(f"Unable to get price. {price_response['info']}")
            else:
                self.logger().info(f"Missing data from price result. Incomplete return result for ({price_response.keys()})")
        else:
            gas_price_token: str = price_response["gasPriceToken"]
            gas_cost: Decimal = Decimal(price_response["gasCost"])
            price: Decimal = Decimal(price_response["price"])
            # self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)
            if process_exception is True:
                gas_limit: int = int(price_response["gasLimit"])
                exceptions: List[str] = check_transaction_exceptions(
                    balances=self._account_balances,
                    base_asset=base,
                    quote_asset=quote,
                    amount=amount,
                    side=side,
                    gas_limit=gas_limit,
                    gas_cost=gas_cost,
                    gas_asset=gas_price_token,
                    swaps_count=len(price_response.get("swaps", []))
                )
                for index in range(len(exceptions)):
                    self.logger().warning(
                        f"Warning! [{index + 1}/{len(exceptions)}] {side} order - {exceptions[index]}"
                    )
                if len(exceptions) > 0:
                    return None
            return Decimal(str(price))
        return None

    async def update_order_status(self, tracked_orders: List[GatewayInFlightOrder]):
        """
        Calls REST API to get status update for each in-flight amm orders.
        """
        if len(tracked_orders) < 1:
            return

        tx_hash_list: List[str] = await safe_gather(
            *[tracked_order.get_exchange_order_id() for tracked_order in tracked_orders]
        )

        self.logger().info(
            "Polling for order status updates of %d orders. Transaction hashes: %s",
            len(tracked_orders),
            tx_hash_list
        )
        update_results: List[Union[Dict[str, Any], Exception]] = await safe_gather(*[
            self._get_gateway_instance().get_transaction_status(
                self.chain,
                self.network,
                tx_hash
            )
            for tx_hash in tx_hash_list
        ], return_exceptions=True)
        for tracked_order, tx_details in zip(tracked_orders, update_results):
            if isinstance(tx_details, Exception):
                self.logger().error(f"An error occurred fetching transaction status of {tracked_order.client_order_id}")
                continue
            if "txHash" not in tx_details:
                self.logger().error(f"No txHash field for transaction status of {tracked_order.client_order_id}: "
                                    f"{tx_details}.")
                continue
            tx_status: int = tx_details["txStatus"]
            tx_receipt: Optional[Dict[str, Any]] = tx_details["txData"]
            if tx_status == 1 and (tx_receipt is not None):
                # 1: confirmed
                fee: Decimal = Decimal(tx_receipt["meta"]["fee"] / 1000000000)

                self.process_trade_fill_update(tracked_order=tracked_order, fee=fee)

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.FILLED,
                )
                self._order_tracker.process_order_update(order_update)
            elif tx_status == 0:
                # 0: fulfilled but not yet confirmed
                pass
            elif tx_status == -1:
                # -1: confirmed but failed
                self.logger().network(
                    f"Error fetching transaction status for the order {tracked_order.client_order_id}: {tx_details}.",
                    app_warning_msg=f"Failed to fetch transaction status for the order {tracked_order.client_order_id}."
                )
                await self._order_tracker.process_order_not_found(tracked_order.client_order_id)
