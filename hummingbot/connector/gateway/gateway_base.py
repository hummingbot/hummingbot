import asyncio
import copy
import itertools as it
import logging
import re
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union, cast

# GatewayConnectionSetting removed - using dynamic gateway connector detection
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeFeeBase, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
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
    _chain_info: Dict[str, Any]
    _network_transaction_fee: Optional[TokenAmount]
    _order_tracker: ClientOrderTracker
    _native_currency: str
    _amount_quantum_dict: Dict[str, Decimal]

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 connector_name: str,
                 chain: str,
                 network: str,
                 address: str = "",  # Made optional, will be fetched dynamically
                 trading_pairs: List[str] = [],
                 trading_required: bool = True
                 ):
        """
        :param connector_name: name of connector on gateway
        :param chain: refers to a block chain, e.g. solana
        :param network: refers to a network of a particular blockchain e.g. mainnet or devnet
        :param address: (deprecated) wallet address - now fetched dynamically from gateway
        :param trading_pairs: a list of trading pairs
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        self._connector_name = connector_name
        self._name = f"{connector_name}_{network}"
        super().__init__(client_config_map)
        self._chain = chain
        self._network = network
        self._trading_pairs = trading_pairs
        self._tokens = set()
        [self._tokens.update(set(trading_pair.split("_")[0].split("-"))) for trading_pair in trading_pairs]
        self._wallet_address = address  # May be empty, will be fetched dynamically
        self._wallet_cache = None  # Cache for wallet address
        self._wallet_cache_timestamp = 0
        self._wallet_cache_ttl = 300  # 5 minutes cache TTL
        self._trading_required = trading_required
        self._last_poll_timestamp = 0.0
        self._last_balance_poll_timestamp = time.time()
        self._last_est_gas_cost_reported = 0
        self._chain_info = {}
        self._status_polling_task = None
        self._get_chain_info_task = None
        self._network_transaction_fee = None
        self._poll_notifier = None
        self._native_currency = None
        self._order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self, lost_order_count_limit=10)
        self._amount_quantum_dict = {}
        safe_ensure_future(self.load_token_data())

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
        """Get wallet address, fetching from gateway if needed."""
        if self._wallet_address:
            return self._wallet_address

        # Try to get from cache first
        current_time = time.time()
        if self._wallet_cache and (current_time - self._wallet_cache_timestamp) < self._wallet_cache_ttl:
            return self._wallet_cache

        # Fetch from gateway synchronously (property can't be async)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, we can't use run_until_complete
                # Return cached value or raise error
                if self._wallet_cache:
                    return self._wallet_cache
                raise ValueError(f"No wallet found for chain {self._chain}. Please add one with 'gateway wallet add {self._chain}'")
            else:
                # Sync context, we can fetch
                wallet_address = loop.run_until_complete(self.get_wallet_for_chain())
                return wallet_address
        except Exception:
            if self._wallet_cache:
                return self._wallet_cache
            raise ValueError(f"No wallet found for chain {self._chain}. Please add one with 'gateway wallet add {self._chain}'")

    async def get_wallet_for_chain(self) -> str:
        """
        Get wallet address for this chain from gateway.
        Caches the result for performance.
        """
        # Check cache first
        current_time = time.time()
        if self._wallet_cache and (current_time - self._wallet_cache_timestamp) < self._wallet_cache_ttl:
            return self._wallet_cache

        # Fetch from gateway
        try:
            wallets = await self._get_gateway_instance().get_wallets(self._chain)
            if not wallets or not wallets[0].get("walletAddresses"):
                error_msg = f"No wallet found for chain {self._chain}. Please add one with 'gateway wallet add {self._chain}'"
                self.logger().error(error_msg)
                raise ValueError(error_msg)

            # Use first wallet (in future, could use preferences)
            wallet_address = wallets[0]["walletAddresses"][0]

            # Update cache
            self._wallet_cache = wallet_address
            self._wallet_cache_timestamp = current_time

            # Also update the instance variable for backward compatibility
            self._wallet_address = wallet_address

            return wallet_address
        except Exception as e:
            self.logger().error(f"Failed to fetch wallet for chain {self._chain}: {str(e)}")
            raise

    async def all_trading_pairs(self) -> List[str]:
        """
        Calls the tokens endpoint on Gateway.
        """
        try:
            tokens = await self._get_gateway_instance().chain_request(
                "get", self._chain, "tokens", {"network": self._network}
            )
            token_symbols = [t["symbol"] for t in tokens["tokens"]]
            trading_pairs = []
            for base, quote in it.permutations(token_symbols, 2):
                trading_pairs.append(f"{base}-{quote}")
            return trading_pairs
        except Exception:
            return []

    @property
    def gateway_orders(self) -> List[InFlightOrder]:
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

    @network_transaction_fee.setter
    def network_transaction_fee(self, new_fee: TokenAmount):
        self._network_transaction_fee = new_fee

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._order_tracker.active_orders

    @property
    def tracking_states(self) -> Dict[str, Any]:
        return {
            key: value.to_json()
            for key, value in self.in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._order_tracker._in_flight_orders.update({
            key: InFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @staticmethod
    def create_market_order_id(side: TradeType, trading_pair: str) -> str:
        return f"{side.name.lower()}-{trading_pair}-{get_tracking_nonce()}"

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
        self._get_chain_info_task = safe_ensure_future(self.get_chain_info())

        # Ensure wallet address is fetched on startup if not provided
        if not self._wallet_address:
            try:
                await self.get_wallet_for_chain()
            except Exception as e:
                self.logger().error(f"Failed to fetch wallet address on startup: {str(e)}")

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._get_chain_info_task is not None:
            self._get_chain_info_task.cancel()
            self._get_chain_info_task = None

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
        tokens = await self._get_gateway_instance().chain_request(
            "get", self.chain, "tokens", {"network": self.network}
        )
        for t in tokens.get("tokens", []):
            self._amount_quantum_dict[t["symbol"]] = Decimal(str(10 ** -t["decimals"]))

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("1e-15")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        base, quote = trading_pair.split("-")
        return max(self._amount_quantum_dict[base], self._amount_quantum_dict[quote])

    async def get_chain_info(self):
        """
        Calls the base endpoint of the connector on Gateway to know basic info about chain being used.
        """
        try:
            self._chain_info = await self._get_gateway_instance().chain_request(
                "get", self.chain, "status", {"network": self.network}
            )
            if not isinstance(self._chain_info, list):
                self._native_currency = self._chain_info.get("nativeCurrency", "SOL")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                "Error fetching chain info",
                exc_info=True,
                app_warning_msg=str(e)
            )

    @property
    def ready(self):
        return all(self.status_dict.values())

    @property
    def status_dict(self) -> Dict[str, bool]:
        status = {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "native_currency": self._native_currency is not None,
        }
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

            # Build token list from trading pairs and native currency
            token_list = list(self._tokens)
            if self._native_currency:
                token_list.append(self._native_currency)

            # Remove duplicates
            token_list = list(set(token_list))

            try:
                resp_json: Dict[str, Any] = await self._get_gateway_instance().get_balances(
                    chain=self.chain,
                    network=self.network,
                    address=self.address,
                    token_symbols=token_list
                )
            except Exception as e:
                self.logger().warning(f"Failed to update balances: {str(e)}")
                # If it's a wallet not found error, provide helpful message
                if "Internal Server Error" in str(e) or "wallet" in str(e).lower():
                    self.logger().warning(f"Please ensure you have a wallet configured for {self.chain}. Use 'gateway wallet add {self.chain}' to add one.")
                return
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
        Returns the Gateway transaction handler instance.
        """
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        return gateway_instance

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: Optional[str] = None,
                             trading_pair: str = "",
                             trade_type: TradeType = TradeType.BUY,
                             price: Decimal = s_decimal_0,
                             amount: Decimal = s_decimal_0):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary in ClientOrderTracker.
        """
        self._order_tracker.start_tracking_order(
            InFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=trade_type,
                price=price,
                amount=amount,
                creation_timestamp=self.current_timestamp,
                initial_state=OrderState.PENDING_CREATE
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

    async def update_order_status(self, tracked_orders: List[InFlightOrder]):
        """
        Calls REST API to get status update for each in-flight AMM orders.
        """
        if len(tracked_orders) < 1:
            return

        # Filter out orders without exchange_order_id (transaction hash)
        orders_with_tx_hash = [order for order in tracked_orders if order.exchange_order_id is not None]
        if not orders_with_tx_hash:
            return

        tx_hash_list: List[str] = [order.exchange_order_id for order in orders_with_tx_hash]

        self.logger().info(
            "Polling for order status updates of %d orders. Transaction hashes: %s",
            len(orders_with_tx_hash),
            tx_hash_list
        )

        update_results: List[Union[Dict[str, Any], Exception]] = await safe_gather(*[
            self._get_gateway_instance().chain_request(
                "post", self.chain, "poll",
                {"network": self.network, "signature": tx_hash}
            )
            for tx_hash in tx_hash_list
        ], return_exceptions=True)

        for tracked_order, tx_details in zip(orders_with_tx_hash, update_results):
            if isinstance(tx_details, Exception):
                self.logger().error(f"An error occurred fetching transaction status of {tracked_order.client_order_id}")
                continue

            if "signature" not in tx_details:
                self.logger().error(f"No signature field for transaction status of {tracked_order.client_order_id}: "
                                    f"{tx_details}.")
                continue

            tx_status: int = tx_details["txStatus"]

            # Parse transaction using standardized status format
            if tx_status == 1:  # CONFIRMED
                # Extract fee from transaction data using standardized schema
                fee_amount = Decimal(str(tx_details.get("data", {}).get("fee", "0")))

                self.process_transaction_confirmation_update(tracked_order=tracked_order, fee=fee_amount)

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.FILLED,
                )
                self._order_tracker.process_order_update(order_update)

            # Check if transaction is still pending
            elif tx_status == 0:  # PENDING
                pass

            # Transaction failed
            elif tx_status == -1:  # FAILED
                self.logger().network(
                    f"Error fetching transaction status for the order {tracked_order.client_order_id}: {tx_details}.",
                    app_warning_msg=f"Failed to fetch transaction status for the order {tracked_order.client_order_id}."
                )
                await self._order_tracker.process_order_not_found(tracked_order.client_order_id)

    def process_transaction_confirmation_update(self, tracked_order: InFlightOrder, fee: Decimal):
        # Fee asset defaults to native currency for Gateway transactions
        fee_asset = self._native_currency or tracked_order.trading_pair.split("-")[0]
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

    def update_order_transaction_hash(self, order_id: str, transaction_hash: str):
        """
        Updates an order with its transaction hash (exchange_order_id).
        This is called by GatewayHttpClient when a transaction is submitted.
        """
        # Get the in-flight order to retrieve trading_pair
        in_flight_order = self._order_tracker.fetch_order(order_id)
        if not in_flight_order:
            self.logger().warning(f"Could not find order {order_id} to update transaction hash")
            return

        order_update = OrderUpdate(
            client_order_id=order_id,
            trading_pair=in_flight_order.trading_pair,
            exchange_order_id=transaction_hash,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.OPEN
        )
        self._order_tracker.process_order_update(order_update)
