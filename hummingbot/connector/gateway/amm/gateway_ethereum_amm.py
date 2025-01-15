import asyncio
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Union

from async_timeout import timeout

from hummingbot.connector.gateway.amm.gateway_amm_base import GatewayAMMBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
from hummingbot.core.event.events import (
    TokenApprovalCancelledEvent,
    TokenApprovalEvent,
    TokenApprovalFailureEvent,
    TokenApprovalSuccessEvent,
    TradeType,
)
from hummingbot.core.gateway import check_transaction_exceptions
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather

s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")


class GatewayEthereumAMM(GatewayAMMBase):
    """
    Defines Ethereum-specific functions for interacting with AMM protocols via Gateway.
    """

    APPROVAL_ORDER_ID_PATTERN = re.compile(r"approve-(\w+)-(\w+)")

    _ev_loop: asyncio.AbstractEventLoop
    _allowances: Dict[str, Decimal]
    _update_allowances: Optional[asyncio.Task]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._ev_loop = asyncio.get_event_loop()
        self._allowances = {}
        self._update_allowances = None

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._update_allowances = safe_ensure_future(self.update_allowances())
            self._get_gas_estimate_task = safe_ensure_future(self.get_gas_estimate())
        self._get_chain_info_task = safe_ensure_future(self.get_chain_info())

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._update_allowances is not None:
            self._update_allowances.cancel()
            self._update_allowances = None
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
                    self.update_canceling_transactions(self.canceling_orders),
                    self.update_token_approval_status(self.approval_orders),
                    self.update_order_status(self.amm_orders)
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)

    @property
    def approval_orders(self) -> List[GatewayInFlightOrder]:
        return [
            approval_order
            for approval_order in self._order_tracker.active_orders.values()
            if approval_order.is_approval_request
        ]

    @property
    def canceling_orders(self) -> List[GatewayInFlightOrder]:
        return [
            cancel_order
            for cancel_order in self.amm_orders
            if cancel_order.is_pending_cancel_confirmation
        ]

    def create_approval_order_id(self, token_symbol: str) -> str:
        return f"approve-{self.connector_name}-{token_symbol}"

    def get_token_symbol_from_approval_order_id(self, approval_order_id: str) -> Optional[str]:
        match = self.APPROVAL_ORDER_ID_PATTERN.search(approval_order_id)
        if match:
            return match.group(2)
        return None

    def is_pending_approval(self, token: str) -> bool:
        for order in self.approval_orders:
            if token in order.client_order_id:
                return order.is_pending_approval
        return False

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
            await asyncio.sleep(120)  # sleep for 2 mins

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
                    swaps_count=len(price_response.get("swaps", [])),
                    allowances=self._allowances
                )
                for index in range(len(exceptions)):
                    self.logger().warning(
                        f"Warning! [{index + 1}/{len(exceptions)}] {side} order - {exceptions[index]}"
                    )
                if len(exceptions) > 0:
                    return None
            return Decimal(str(price))
        return None

    async def update_token_approval_status(self, tracked_approvals: List[GatewayInFlightOrder]):
        """
        Calls REST API to get status update for each in-flight token approval transaction.
        """
        if len(tracked_approvals) < 1:
            return
        tx_hash_list: List[str] = await safe_gather(*[
            tracked_approval.get_exchange_order_id() for tracked_approval in tracked_approvals
        ])
        transaction_states: List[Union[Dict[str, Any], Exception]] = await safe_gather(*[
            self._get_gateway_instance().get_transaction_status(
                self.chain,
                self.network,
                tx_hash
            )
            for tx_hash in tx_hash_list
        ], return_exceptions=True)
        for tracked_approval, transaction_status in zip(tracked_approvals, transaction_states):
            token_symbol: str = self.get_token_symbol_from_approval_order_id(tracked_approval.client_order_id)
            if isinstance(transaction_status, Exception):
                self.logger().error(f"Error while trying to approve token {token_symbol} for {self.connector_name}: "
                                    f"{transaction_status}")
                continue
            if "txHash" not in transaction_status:
                self.logger().error(f"Error while trying to approve token {token_symbol} for {self.connector_name}: "
                                    "txHash key not found in transaction status.")
                continue
            if transaction_status["txStatus"] == 1:
                if transaction_status["txReceipt"]["status"] == 1:
                    self.logger().info(f"Token approval for {tracked_approval.client_order_id} on {self.connector_name} "
                                       f"successful.")
                    tracked_approval.current_state = OrderState.APPROVED
                    self.trigger_event(
                        TokenApprovalEvent.ApprovalSuccessful,
                        TokenApprovalSuccessEvent(
                            self.current_timestamp,
                            self.connector_name,
                            token_symbol
                        )
                    )
                else:
                    self.logger().warning(
                        f"Token approval for {tracked_approval.client_order_id} on {self.connector_name} failed."
                    )
                    tracked_approval.current_state = OrderState.FAILED
                    self.trigger_event(
                        TokenApprovalEvent.ApprovalFailed,
                        TokenApprovalFailureEvent(
                            self.current_timestamp,
                            self.connector_name,
                            token_symbol
                        )
                    )
                self.stop_tracking_order(tracked_approval.client_order_id)

    async def update_canceling_transactions(self, canceled_tracked_orders: List[GatewayInFlightOrder]):
        """
        Update tracked orders that have a cancel_tx_hash.
        :param canceled_tracked_orders: Canceled tracked_orders (cancel_tx_has is not None).
        """
        if len(canceled_tracked_orders) < 1:
            return

        self.logger().debug(
            "Polling for order status updates of %d canceled orders.",
            len(canceled_tracked_orders)
        )
        update_results: List[Union[Dict[str, Any], Exception]] = await safe_gather(*[
            self._get_gateway_instance().get_transaction_status(
                self.chain,
                self.network,
                tx_hash
            )
            for tx_hash in [t.cancel_tx_hash for t in canceled_tracked_orders]
        ], return_exceptions=True)
        for tracked_order, update_result in zip(canceled_tracked_orders, update_results):
            if isinstance(update_result, Exception):
                raise update_result
            if "txHash" not in update_result:
                self.logger().error(f"No txHash field for transaction status of {tracked_order.client_order_id}: "
                                    f"{update_result}.")
                continue
            if update_result["txStatus"] == 1:
                if update_result["txReceipt"]["status"] == 1:
                    if tracked_order.current_state == OrderState.PENDING_CANCEL:
                        if not tracked_order.is_approval_request:
                            order_update: OrderUpdate = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                client_order_id=tracked_order.client_order_id,
                                update_timestamp=self.current_timestamp,
                                new_state=OrderState.CANCELED
                            )
                            self._order_tracker.process_order_update(order_update)

                        elif tracked_order.is_approval_request:
                            order_update: OrderUpdate = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                client_order_id=tracked_order.client_order_id,
                                update_timestamp=self.current_timestamp,
                                new_state=OrderState.CANCELED
                            )
                            token_symbol: str = self.get_token_symbol_from_approval_order_id(
                                tracked_order.client_order_id
                            )
                            self.trigger_event(
                                TokenApprovalEvent.ApprovalCancelled,
                                TokenApprovalCancelledEvent(
                                    self.current_timestamp,
                                    self.connector_name,
                                    token_symbol
                                )
                            )
                            self.logger().info(f"Token approval for {tracked_order.client_order_id} on "
                                               f"{self.connector_name} has been canceled.")
                            self.stop_tracking_order(tracked_order.client_order_id)

    async def update_order_status(self, tracked_orders: List[GatewayInFlightOrder]):
        """
        Calls REST API to get status update for each in-flight amm orders.
        """
        if len(tracked_orders) < 1:
            return

        # split canceled and non-canceled orders
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
            tx_receipt: Optional[Dict[str, Any]] = tx_details["txReceipt"]
            if tx_status == 1 and (tx_receipt is not None and tx_receipt.get("status") == 1):
                gas_used: int = tx_receipt["gasUsed"]
                gas_price: Decimal = tracked_order.gas_price
                fee: Decimal = Decimal(str(gas_used)) * Decimal(str(gas_price)) / Decimal(str(1e9))

                self.process_trade_fill_update(tracked_order=tracked_order, fee=fee)

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.FILLED,
                )
                self._order_tracker.process_order_update(order_update)
            elif tx_status in [0, 2, 3]:
                # 0: in the mempool but we dont have data to guess its status
                # 2: in the mempool and likely to succeed
                # 3: in the mempool and likely to fail
                pass

            elif tx_status == -1 or (tx_receipt is not None and tx_receipt.get("status") == 0):
                self.logger().network(
                    f"Error fetching transaction status for the order {tracked_order.client_order_id}: {tx_details}.",
                    app_warning_msg=f"Failed to fetch transaction status for the order {tracked_order.client_order_id}."
                )
                await self._order_tracker.process_order_not_found(tracked_order.client_order_id)

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

    async def cancel_outdated_orders(self, cancel_age: int) -> List[CancellationResult]:
        """
        Iterate through all known orders and cancel them if their age is greater than cancel_age.
        """
        incomplete_orders: List[GatewayInFlightOrder] = []

        # Incomplete Approval Requests
        incomplete_orders.extend([
            o for o in self.approval_orders
            if o.is_pending_approval
        ])
        # Incomplete Active Orders
        incomplete_orders.extend([
            o for o in self.amm_orders
            if not o.is_done
        ])

        if len(incomplete_orders) < 1:
            return []

        timeout_seconds: float = 30.0
        canceling_id_set: Set[str] = set([o.client_order_id for o in incomplete_orders])
        sent_cancellations: List[CancellationResult] = []

        try:
            async with timeout(timeout_seconds):
                for incomplete_order in incomplete_orders:
                    try:
                        canceling_order_id: Optional[str] = await self._execute_cancel(
                            incomplete_order.client_order_id,
                            cancel_age
                        )
                    except Exception:
                        continue
                    if canceling_order_id is not None:
                        canceling_id_set.remove(canceling_order_id)
                        sent_cancellations.append(CancellationResult(canceling_order_id, True))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                "Unexpected error cancelling outdated orders.",
                exc_info=True,
                app_warning_msg=f"Failed to cancel orders on {self.chain}-{self.network}."
            )

        skipped_cancellations: List[CancellationResult] = [CancellationResult(oid, False) for oid in canceling_id_set]
        return sent_cancellations + skipped_cancellations
