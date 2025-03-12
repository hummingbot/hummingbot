import asyncio
import re
from decimal import Decimal
from typing import Any, Dict, Optional

from hummingbot.connector.gateway.gateway_base import GatewayBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
from hummingbot.core.event.events import TradeType
from hummingbot.core.utils.async_utils import safe_ensure_future

s_decimal_0 = Decimal("0")


class GatewayEthereum(GatewayBase):
    """
    Defines Ethereum-specific functions for interacting with AMM protocols via Gateway.
    """

    APPROVAL_ORDER_ID_PATTERN = re.compile(r"approve-(\w+)-(\w+)")

    _allowances: Dict[str, Decimal]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._allowances = {}

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._get_gas_estimate_task = safe_ensure_future(self.get_gas_estimate())
            self._get_allowances_task = safe_ensure_future(self.update_allowances())
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
        if self._get_allowances_task is not None:
            self._get_allowances_task.cancel()
            self._get_allowances_task = None

    def get_token_symbol_from_approval_order_id(self, approval_order_id: str) -> Optional[str]:
        match = self.APPROVAL_ORDER_ID_PATTERN.search(approval_order_id)
        if match:
            return match.group(2)
        return None

    async def approve_token(self, token_symbol: str, **request_args) -> Optional[GatewayInFlightOrder]:
        """
        Approves contract as a spender for a token.
        :param token_symbol: token to approve.
        """
        approval_id: str = self.create_approval_order_id(token_symbol)

        self.logger().info(f"Initiating approval for {token_symbol}.")

        self.start_tracking_order(order_id=approval_id,
                                  trading_pair=token_symbol,
                                  is_approval=True)
        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().approve_token(
                self.chain,
                self.network,
                self.address,
                token_symbol,
                self.connector_name,
                **request_args
            )

            transaction_hash: Optional[str] = resp.get("approval", {}).get("hash")
            nonce: Optional[int] = resp.get("nonce")
            if transaction_hash is not None and nonce is not None:
                tracked_order = self._order_tracker.fetch_order(client_order_id=approval_id)
                tracked_order.update_exchange_order_id(transaction_hash)
                tracked_order.nonce = nonce
                self.logger().info(
                    f"Maximum {token_symbol} approval for {self.connector_name} contract sent, hash: {transaction_hash}."
                )
                return tracked_order
            else:
                self.stop_tracking_order(approval_id)
                self.logger().info(f"Approval for {token_symbol} on {self.connector_name} failed.")
                return None
        except Exception:
            self.stop_tracking_order(approval_id)
            self.logger().error(
                f"Error submitting approval order for {token_symbol} on {self.connector_name}-{self.network}.",
                exc_info=True
            )
            return None

    async def update_allowances(self):
        """
        Allowances updated continously.
        """
        while True:
            self._allowances = await self.get_allowances()

    async def get_allowances(self) -> Dict[str, Decimal]:
        """
        Retrieves allowances for token in trading_pairs
        :return: A dictionary of token and its allowance.
        """
        ret_val = {}
        resp: Dict[str, Any] = await self._get_gateway_instance().get_allowances(
            self.chain, self.network, self.address, list(self._tokens), self.connector_name
        )
        for token, amount in resp["approvals"].items():
            ret_val[token] = Decimal(str(amount))
        return ret_val

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
        return super().parse_price_response(
            base=base,
            quote=quote,
            amount=amount,
            side=side,
            price_response=price_response,
            process_exception=process_exception,
            allowances=self._allowances
        )

    def _get_transaction_receipt_from_details(self, tx_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction receipt from tx_details for Ethereum."""
        return tx_details.get("txReceipt")

    def _is_transaction_successful(self, tx_status: int, tx_receipt: Optional[Dict[str, Any]]) -> bool:
        """Determine if an Ethereum transaction is successful."""
        return tx_status == 1 and tx_receipt is not None and tx_receipt.get("status") == 1

    def _is_transaction_pending(self, tx_status: int) -> bool:
        """Determine if an Ethereum transaction is still pending."""
        return tx_status in [0, 2, 3]
        # 0: in the mempool but we dont have data to guess its status
        # 2: in the mempool and likely to succeed
        # 3: in the mempool and likely to fail

    def _is_transaction_failed(self, tx_status: int, tx_receipt: Optional[Dict[str, Any]]) -> bool:
        """Determine if an Ethereum transaction has failed."""
        return tx_status == -1 or (tx_receipt is not None and tx_receipt.get("status") == 0)

    def _calculate_transaction_fee(self, tracked_order: GatewayInFlightOrder, tx_receipt: Dict[str, Any]) -> Decimal:
        """Calculate the transaction fee for Ethereum."""
        gas_used: int = tx_receipt["gasUsed"]
        gas_price: Decimal = tracked_order.gas_price
        return Decimal(str(gas_used)) * Decimal(str(gas_price)) / Decimal(str(1e9))

    def has_allowances(self) -> bool:
        """
        Checks if all tokens have allowance (an amount approved)
        """
        allowances_available = all(amount > s_decimal_0 for amount in self._allowances.values())
        return ((len(self._allowances.values()) == len(self._tokens)) and
                (allowances_available))

    async def _update_nonce(self, new_nonce: Optional[int] = None):
        """
        Call the gateway API to get the current nonce for self.address
        """
        if not new_nonce:
            resp_json: Dict[str, Any] = await self._get_gateway_instance().get_evm_nonce(self.chain, self.network, self.address)
            new_nonce: int = resp_json.get("nonce")

        self._nonce = new_nonce

    async def _execute_cancel(self, order_id: str, cancel_age: int) -> Optional[str]:
        """
        Cancel an existing order if the age of the order is greater than its cancel_age,
        and if the order is not done or already in the cancelling state.
        """
        try:
            tracked_order: GatewayInFlightOrder = self._order_tracker.fetch_order(client_order_id=order_id)
            if tracked_order is None:
                self.logger().error(f"The order {order_id} is not being tracked.")
                raise ValueError(f"The order {order_id} is not being tracked.")

            if (self.current_timestamp - tracked_order.creation_timestamp) < cancel_age:
                return None

            if tracked_order.is_done:
                return None

            if tracked_order.is_pending_cancel_confirmation:
                return order_id

            self.logger().info(f"The blockchain transaction for {order_id} with nonce {tracked_order.nonce} has "
                               f"expired. Canceling the order...")
            resp: Dict[str, Any] = await self._get_gateway_instance().cancel_evm_transaction(
                self.chain,
                self.network,
                self.address,
                tracked_order.nonce
            )

            tx_hash: Optional[str] = resp.get("txHash")
            if tx_hash is not None:
                tracked_order.cancel_tx_hash = tx_hash
            else:
                raise EnvironmentError(f"Missing txHash from cancel_evm_transaction() response: {resp}.")

            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.PENDING_CANCEL
            )
            self._order_tracker.process_order_update(order_update)

            return order_id
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self.logger().error(
                f"Failed to cancel order {order_id}: {str(err)}.",
                exc_info=True
            )
