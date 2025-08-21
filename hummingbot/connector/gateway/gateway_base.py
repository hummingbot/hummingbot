import asyncio
import copy
import itertools as it
import logging
import re
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union, cast

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.common_types import TransactionStatus
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeFeeBase, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None
s_decimal_0 = Decimal("0")


class GatewayBase(ConnectorBase):
    """
    Defines basic functions common to all Gateway connectors
    """

    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 1.0
    UPDATE_BALANCE_INTERVAL = 30.0
    APPROVAL_ORDER_ID_PATTERN = re.compile(r"approve-(\w+)-(\w+)")

    _connector_name: str
    _name: str
    _chain: str
    _network: str
    _address: str
    _trading_pairs: List[str]
    _tokens: Set[str]
    _trading_required: bool
    _last_poll_timestamp: float
    _last_balance_poll_timestamp: float
    _last_est_gas_cost_reported: float
    _poll_notifier: Optional[asyncio.Event]
    _status_polling_task: Optional[asyncio.Task]
    _get_chain_info_task: Optional[asyncio.Task]
    _get_gas_estimate_task: Optional[asyncio.Task]
    _chain_info: Dict[str, Any]
    _network_transaction_fee: Optional[TokenAmount]
    _order_tracker: ClientOrderTracker
    _native_currency: str
    _amount_quantum_dict: Dict[str, Decimal]

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 connector_name: str,
                 chain: Optional[str] = None,
                 network: Optional[str] = None,
                 address: Optional[str] = None,
                 trading_pairs: List[str] = [],
                 trading_required: bool = True
                 ):
        """
        :param connector_name: name of connector on gateway (e.g., 'uniswap/amm', 'jupiter/router')
        :param chain: refers to a block chain, e.g. solana (auto-detected if not provided)
        :param network: refers to a network of a particular blockchain e.g. mainnet or devnet (auto-detected if not provided)
        :param address: the address of the wallet which has been added on gateway (uses default wallet if not provided)
        :param trading_pairs: a list of trading pairs
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        self._connector_name = connector_name
        # Temporarily set chain/network/address - will be populated in start_network if not provided
        self._chain = chain
        self._network = network
        self._wallet_address = address
        # Use connector name as temporary name until we have chain/network info
        self._name = connector_name
        super().__init__(client_config_map)
        self._trading_pairs = trading_pairs
        self._tokens = set()
        [self._tokens.update(set(trading_pair.split("_")[0].split("-"))) for trading_pair in trading_pairs]
        self._trading_required = trading_required
        self._last_poll_timestamp = 0.0
        self._last_balance_poll_timestamp = time.time()
        self._last_est_gas_cost_reported = 0
        self._chain_info = {}
        self._status_polling_task = None
        self._get_chain_info_task = None
        self._get_gas_estimate_task = None
        self._network_transaction_fee = None
        self._poll_notifier = None
        self._native_currency = None
        self._order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self, lost_order_count_limit=10)
        self._amount_quantum_dict = {}
        self._token_data = {}  # Store complete token information
        self._allowances = {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(cls.__name__)
        return cast(HummingbotLogger, s_logger)

    @property
    def connector_name(self):
        """
        Returns the name of connector/protocol to be connected to on Gateway.
        """
        return self._connector_name

    @property
    def chain(self):
        return self._chain

    @property
    def network(self):
        return self._network

    @property
    def name(self):
        return self._name

    @property
    def address(self):
        return self._wallet_address

    @property
    def trading_pairs(self):
        """
        Returns the list of trading pairs supported by this connector.
        """
        return self._trading_pairs

    async def all_trading_pairs(self) -> List[str]:
        """
        Calls the tokens endpoint on Gateway.
        """
        try:
            tokens = await GatewayHttpClient.get_instance().get_tokens(self._chain, self._network)
            token_symbols = [t["symbol"] for t in tokens["tokens"]]
            trading_pairs = []
            for base, quote in it.permutations(token_symbols, 2):
                trading_pairs.append(f"{base}-{quote}")
            return trading_pairs
        except Exception:
            return []

    @property
    def gateway_orders(self) -> List[GatewayInFlightOrder]:
        return [
            in_flight_order
            for in_flight_order in self._order_tracker.active_orders.values()
            if in_flight_order.is_open
        ]

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self.gateway_orders
        ]

    @property
    def network_transaction_fee(self) -> TokenAmount:
        return self._network_transaction_fee

    @property
    def native_currency(self) -> Optional[str]:
        """Returns the native currency symbol for this chain."""
        return self._native_currency

    @network_transaction_fee.setter
    def network_transaction_fee(self, new_fee: TokenAmount):
        self._network_transaction_fee = new_fee

    @property
    def in_flight_orders(self) -> Dict[str, GatewayInFlightOrder]:
        return self._order_tracker.active_orders

    def get_order(self, client_order_id: str) -> Optional[GatewayInFlightOrder]:
        """Get a specific order."""
        return self._order_tracker.fetch_order(client_order_id)

    @property
    def tracking_states(self) -> Dict[str, Any]:
        return {
            key: value.to_json()
            for key, value in self.in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._order_tracker._in_flight_orders.update({
            key: GatewayInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @staticmethod
    def create_market_order_id(side: TradeType, trading_pair: str) -> str:
        return f"{side.name.lower()}-{trading_pair}-{get_tracking_nonce()}"

    async def start_network(self):
        # Auto-detect chain and network if not provided
        if not self._chain or not self._network:
            chain, network, error = await self._get_gateway_instance().get_connector_chain_network(
                self._connector_name
            )
            if error:
                raise ValueError(f"Failed to get chain/network info: {error}")
            if not self._chain:
                self._chain = chain
            if not self._network:
                self._network = network

        # Get default wallet if not provided
        if not self._wallet_address:
            wallet_address, error = await self._get_gateway_instance().get_default_wallet(
                self._chain
            )
            if error:
                raise ValueError(f"Failed to get default wallet: {error}")
            self._wallet_address = wallet_address

        # Update the name to same as the connector name
        self._name = f"{self._connector_name}"

        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._get_gas_estimate_task = safe_ensure_future(self.get_gas_estimate())
        self._get_chain_info_task = safe_ensure_future(self.get_chain_info())
        # Load token data to populate amount quantum dict
        await self.load_token_data()

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._get_chain_info_task is not None:
            self._get_chain_info_task.cancel()
            self._get_chain_info_task = None
        if self._get_gas_estimate_task is not None:
            self._get_gas_estimate_task.cancel()
            self._get_gas_estimate_task = None

    async def _status_polling_loop(self):
        await self.update_balances(on_interval=False)
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self.update_balances(on_interval=True),
                    self.update_order_status(self.gateway_orders)
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)

    async def load_token_data(self):
        tokens = await GatewayHttpClient.get_instance().get_tokens(self.chain, self.network)
        for t in tokens.get("tokens", []):
            symbol = t["symbol"]
            self._amount_quantum_dict[symbol] = Decimal(str(10 ** -t["decimals"]))
            # Store complete token data for easy access
            self._token_data[symbol] = t

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("1e-15")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        base, quote = trading_pair.split("-")
        return max(self._amount_quantum_dict[base], self._amount_quantum_dict[quote])

    def get_token_info(self, token_symbol: str) -> Optional[Dict[str, Any]]:
        """Get token information for a given symbol."""
        return self._token_data.get(token_symbol)

    def get_token_by_address(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Get token information for a given address."""
        # Search through all tokens to find matching address
        for symbol, token_data in self._token_data.items():
            if token_data.get("address", "").lower() == token_address.lower():
                return token_data
        return None

    async def get_chain_info(self):
        """
        Calls the base endpoint of the connector on Gateway to know basic info about chain being used.
        """
        try:
            self._chain_info = await self._get_gateway_instance().get_network_status(
                chain=self.chain, network=self.network
            )
            # Get native currency using the proper method from gateway_http_client
            self.logger().debug(f"Getting native currency for chain={self.chain}, network={self.network}")
            native_currency = await self._get_gateway_instance().get_native_currency_symbol(
                chain=self.chain, network=self.network
            )
            if native_currency:
                self._native_currency = native_currency
                self.logger().info(f"Set native currency to: {self._native_currency} for {self.chain}-{self.network}")
            else:
                self.logger().error(f"Failed to get native currency for {self.chain}-{self.network}, got: {native_currency}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                "Error fetching chain info",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_gas_estimate(self):
        """
        Gets the gas estimates for the connector.
        """
        try:
            response: Dict[Any] = await self._get_gateway_instance().estimate_gas(
                chain=self.chain, network=self.network
            )

            # Use the new fee and feeAsset fields from the response
            fee = response.get("fee", None)
            fee_asset = response.get("feeAsset", None)

            if fee is not None and fee_asset is not None:
                # Create a TokenAmount object for the network fee using the provided fee asset
                self.network_transaction_fee = TokenAmount(
                    token=fee_asset,
                    amount=Decimal(str(fee))
                )
                self.logger().debug(f"Set network transaction fee: {fee} {fee_asset}")
            else:
                self.logger().warning(
                    f"Incomplete gas estimate response: fee={fee}, feeAsset={fee_asset}"
                )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting gas estimates for {self.connector_name} on {self.network}.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    @property
    def ready(self):
        status = self.status_dict
        if not all(status.values()):
            # Log which items are not ready
            not_ready = [k for k, v in status.items() if not v]
            self.logger().debug(f"Connector {self.name} not ready. Missing: {not_ready}. Status: {status}")
        return all(status.values())

    @property
    def status_dict(self) -> Dict[str, bool]:
        has_balance = len(self._account_balances) > 0
        has_native_currency = self._native_currency is not None
        has_network_fee = self.network_transaction_fee is not None

        status = {
            "account_balance": has_balance if self._trading_required else True,
            "native_currency": has_native_currency,
            "network_transaction_fee": has_network_fee if self._trading_required else True,
        }

        # Debug logging
        self.logger().debug(
            f"Status check for {self.name}: "
            f"balances={len(self._account_balances)}, "
            f"native_currency={self._native_currency}, "
            f"network_fee={self.network_transaction_fee}, "
            f"trading_required={self._trading_required}"
        )

        return status

    async def check_network(self) -> NetworkStatus:
        """
        Checks if the gateway is up and running.
        """
        try:
            if await self._get_gateway_instance().ping_gateway():
                return NetworkStatus.CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.NOT_CONNECTED

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        if time.time() - self._last_poll_timestamp > self.POLL_INTERVAL:
            if self._poll_notifier is not None and not self._poll_notifier.is_set():
                self._poll_notifier.set()

    async def update_balances(self, on_interval: bool = False):
        """
        Calls Solana API to update total and available balances.
        """
        if self._native_currency is None:
            await self.get_chain_info()
        last_tick = self._last_balance_poll_timestamp
        current_tick = self.current_timestamp
        if not on_interval or (current_tick - last_tick) > self.UPDATE_BALANCE_INTERVAL:
            self._last_balance_poll_timestamp = current_tick
            local_asset_names = set(self._account_balances.keys())
            remote_asset_names = set()
            token_list = list(self._tokens)
            if self._native_currency:
                token_list.append(self._native_currency)
            resp_json: Dict[str, Any] = await self._get_gateway_instance().get_balances(
                chain=self.chain,
                network=self.network,
                address=self.address,
                token_symbols=token_list
            )
            for token, bal in resp_json["balances"].items():
                self._account_available_balances[token] = Decimal(str(bal))
                self._account_balances[token] = Decimal(str(bal))
                remote_asset_names.add(token)
            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]
            self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._order_tracker.all_orders.items()}
            self._in_flight_orders_snapshot_timestamp = self.current_timestamp

    async def _update_balances(self):
        """
        This is called by UserBalances.
        """
        await self.update_balances()

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        This is intentionally left blank, because cancellation is expensive on blockchains. It's not worth it for
        Hummingbot to force cancel all orders whenever Hummingbot quits.
        """
        return []

    def _get_gateway_instance(self) -> GatewayHttpClient:
        """
        Returns the Gateway HTTP instance.
        """
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        return gateway_instance

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: Optional[str] = None,
                             trading_pair: str = "",
                             trade_type: TradeType = TradeType.BUY,
                             price: Decimal = s_decimal_0,
                             amount: Decimal = s_decimal_0,
                             gas_price: Decimal = s_decimal_0,
                             is_approval: bool = False):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary in ClientOrderTracker.
        """
        self._order_tracker.start_tracking_order(
            GatewayInFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=OrderType.AMM_SWAP,
                trade_type=trade_type,
                price=price,
                amount=amount,
                gas_price=gas_price,
                creation_timestamp=self.current_timestamp,
                initial_state=OrderState.PENDING_APPROVAL if is_approval else OrderState.PENDING_CREATE
            )
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary in ClientOrderTracker.
        """
        self._order_tracker.stop_tracking_order(client_order_id=order_id)

    def _handle_operation_failure(self, order_id: str, trading_pair: str, operation_name: str, error: Exception):
        """
        Helper method to handle operation failures consistently across different methods.
        Logs the error and updates the order state to FAILED.

        :param order_id: The ID of the order that failed
        :param trading_pair: The trading pair for the order
        :param operation_name: A description of the operation that failed
        :param error: The exception that occurred
        """
        self.logger().error(
            f"Error {operation_name} for {trading_pair} on {self.connector_name}: {str(error)}",
            exc_info=True
        )
        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order_id,
            trading_pair=trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.FAILED
        )
        self._order_tracker.process_order_update(order_update)

    async def update_order_status(self, tracked_orders: List[GatewayInFlightOrder]):
        """
        Calls REST API to get status update for each in-flight AMM orders.
        """
        if len(tracked_orders) < 1:
            return

        tx_hash_list: List[str] = [
            tx_hash for tx_hash in await safe_gather(
                *[tracked_order.get_exchange_order_id() for tracked_order in tracked_orders],
                return_exceptions=True
            )
            if not isinstance(tx_hash, Exception)
        ]

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

            if "signature" not in tx_details:
                self.logger().error(f"No signature field for transaction status of {tracked_order.client_order_id}: "
                                    f"{tx_details}.")
                continue

            tx_status: int = tx_details["txStatus"]
            fee = tx_details.get("fee", 0)

            # Chain-specific check for transaction success
            if tx_status == TransactionStatus.CONFIRMED.value:
                self.process_transaction_confirmation_update(tracked_order=tracked_order, fee=Decimal(str(fee or 0)))

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.FILLED,
                    misc_updates={
                        "fee_asset": self._native_currency,
                    }
                )
                self._order_tracker.process_order_update(order_update)

            # Check if transaction is still pending
            elif tx_status == TransactionStatus.PENDING.value:
                pass

            # Transaction failed
            elif tx_status == TransactionStatus.FAILED.value:
                self.logger().network(
                    f"Transaction failed for order {tracked_order.client_order_id}: {tx_details}.",
                    app_warning_msg=f"Transaction failed for order {tracked_order.client_order_id}."
                )
                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.FAILED
                )
                self._order_tracker.process_order_update(order_update)

    def process_transaction_confirmation_update(self, tracked_order: GatewayInFlightOrder, fee: Decimal):
        fee_asset = tracked_order.fee_asset if tracked_order.fee_asset else self._native_currency
        trade_fee: TradeFeeBase = AddedToCostTradeFee(
            flat_fees=[TokenAmount(fee_asset, fee)]
        )

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=tracked_order.exchange_order_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=self.current_timestamp,
            fill_price=tracked_order.price,
            fill_base_amount=tracked_order.amount,
            fill_quote_amount=tracked_order.amount * tracked_order.price,
            fee=trade_fee
        )

        self._order_tracker.process_trade_update(trade_update)

    def update_order_from_hash(self, order_id: str, trading_pair: str, transaction_hash: str, transaction_result: dict):
        """
        Helper to create and process an OrderUpdate from a transaction hash and result dict.
        """
        # Extract fee from data field if present (new response format)
        # Otherwise fall back to top-level fee field (legacy format)
        fee = 0
        if "data" in transaction_result and isinstance(transaction_result["data"], dict):
            fee = transaction_result["data"].get("fee", 0)
        else:
            fee = transaction_result.get("fee", 0)

        order_update = OrderUpdate(
            client_order_id=order_id,
            exchange_order_id=transaction_hash,
            trading_pair=trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.OPEN,
            misc_updates={
                "gas_cost": Decimal(str(fee or 0)),
                "gas_price_token": self._native_currency,
            }
        )
        self._order_tracker.process_order_update(order_update)

        # Start monitoring this specific transaction immediately
        safe_ensure_future(self._monitor_transaction_status(order_id, transaction_hash))

    async def _monitor_transaction_status(self, order_id: str, transaction_hash: str, check_interval: float = 2.0):
        """
        Monitor a specific transaction status until it's confirmed or failed.
        This is useful for quick transactions that complete before the regular polling interval.
        """
        tracked_order = self._order_tracker.fetch_order(order_id)
        if not tracked_order:
            self.logger().warning(f"Order {order_id} not found in tracker, cannot monitor transaction status")
            return

        max_attempts = 30  # Maximum 60 seconds of monitoring
        attempts = 0

        while attempts < max_attempts and tracked_order.current_state not in [OrderState.FILLED, OrderState.FAILED, OrderState.CANCELED]:
            try:
                tx_details = await self._get_gateway_instance().get_transaction_status(
                    self.chain,
                    self.network,
                    transaction_hash
                )

                if "signature" not in tx_details:
                    self.logger().error(f"No signature field for transaction status of {order_id}: {tx_details}")
                    break

                tx_status = tx_details.get("txStatus", TransactionStatus.PENDING.value)
                fee = tx_details.get("fee", 0)

                # Transaction confirmed
                if tx_status == TransactionStatus.CONFIRMED.value:
                    self.process_transaction_confirmation_update(tracked_order=tracked_order, fee=Decimal(str(fee or 0)))

                    order_update = OrderUpdate(
                        client_order_id=order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.FILLED,
                    )
                    self._order_tracker.process_order_update(order_update)

                    self.logger().info(f"Transaction {transaction_hash} confirmed for order {order_id}")
                    break

                # Transaction failed
                elif tx_status == TransactionStatus.FAILED.value:
                    self.logger().error(f"Transaction {transaction_hash} failed for order {order_id}")
                    order_update = OrderUpdate(
                        client_order_id=order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.FAILED
                    )
                    self._order_tracker.process_order_update(order_update)
                    break

                # Still pending, wait and try again
                await asyncio.sleep(check_interval)
                attempts += 1

            except Exception as e:
                self.logger().error(f"Error monitoring transaction status for {order_id}: {str(e)}", exc_info=True)
                break

        if attempts >= max_attempts:
            self.logger().warning(f"Transaction monitoring timed out for order {order_id}, transaction {transaction_hash}")

    def get_balance(self, currency: str) -> Decimal:
        """
        Override the parent method to ensure we have fresh balances.
        Forces a balance update if the balance is not available.

        :param currency: The currency (token) name
        :return: A balance for the given currency (token)
        """
        # If we don't have this currency in our balances, trigger an update
        if currency not in self._account_balances:
            # Schedule an async balance update
            safe_ensure_future(self._update_single_balance(currency))
            # Return 0 for now, will be updated async
            return s_decimal_0

        return self._account_balances.get(currency, s_decimal_0)

    async def _update_single_balance(self, currency: str):
        """
        Update balance for a single currency.

        :param currency: The currency (token) to update
        """
        try:
            resp_json: Dict[str, Any] = await self._get_gateway_instance().get_balances(
                chain=self.chain,
                network=self.network,
                address=self.address,
                token_symbols=[currency]
            )

            if "balances" in resp_json and currency in resp_json["balances"]:
                balance = Decimal(str(resp_json["balances"][currency]))
                self._account_available_balances[currency] = balance
                self._account_balances[currency] = balance
                self.logger().debug(f"Updated balance for {currency}: {balance}")
        except Exception as e:
            self.logger().error(f"Error updating balance for {currency}: {str(e)}", exc_info=True)

    async def approve_token(self, token_symbol: str, spender: Optional[str] = None, amount: Optional[Decimal] = None) -> str:
        """
        Approve tokens for spending by the connector's spender contract.

        :param token_symbol: The token to approve
        :param spender: Optional custom spender address (defaults to connector's spender)
        :param amount: Optional approval amount (defaults to max uint256)
        :return: The approval transaction hash
        """
        try:
            # Create approval order ID
            order_id = f"approve-{token_symbol.lower()}-{get_tracking_nonce()}"

            # Extract base connector name if it's in format like "uniswap/amm"
            base_connector = self._connector_name.split("/")[0] if "/" in self._connector_name else self._connector_name

            # Call gateway to approve token
            approve_result = await self._get_gateway_instance().approve_token(
                network=self.network,
                address=self.address,
                token=token_symbol,
                spender=spender or base_connector,
                amount=str(amount) if amount else None
            )

            if "signature" not in approve_result:
                raise Exception(f"No transaction hash returned from approval: {approve_result}")

            transaction_hash = approve_result["signature"]

            # Start tracking the approval order
            self.start_tracking_order(
                order_id=order_id,
                exchange_order_id=transaction_hash,
                trading_pair=f"{token_symbol}-APPROVAL",
                trade_type=TradeType.BUY,  # Use BUY as a placeholder for approval
                price=s_decimal_0,
                amount=amount or s_decimal_0,
                gas_price=Decimal(str(approve_result.get("gasPrice", 0))),
                is_approval=True
            )

            # Update order with transaction hash
            self.update_order_from_hash(
                order_id=order_id,
                trading_pair=f"{token_symbol}-APPROVAL",
                transaction_hash=transaction_hash,
                transaction_result=approve_result
            )

            self.logger().info(f"Token approval submitted. Order ID: {order_id}, Transaction: {transaction_hash}")

            return order_id

        except Exception as e:
            self.logger().error(f"Error approving {token_symbol}: {str(e)}", exc_info=True)
            raise
