import asyncio
import copy
import itertools as it
import logging
import re
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union, cast

from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import TokenAmount
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
    Defines basic functions common to all Gateway AMM connectors
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
    _allowances: Dict[str, Decimal]
    _get_allowances_task: Optional[asyncio.Task]

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 connector_name: str,
                 chain: str,
                 network: str,
                 address: str,
                 trading_pairs: List[str] = [],
                 trading_required: bool = True
                 ):
        """
        :param connector_name: name of connector on gateway
        :param chain: refers to a block chain, e.g. solana
        :param network: refers to a network of a particular blockchain e.g. mainnet or devnet
        :param address: the address of the sol wallet which has been added on gateway
        :param trading_pairs: a list of trading pairs
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        self._connector_name = connector_name
        self._name = f"{connector_name}_{chain}_{network}"
        super().__init__(client_config_map)
        self._chain = chain
        self._network = network
        self._trading_pairs = trading_pairs
        self._tokens = set()
        [self._tokens.update(set(trading_pair.split("_")[0].split("-"))) for trading_pair in trading_pairs]
        self._wallet_address = address
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
        self._allowances = {}
        self._get_allowances_task: Optional[asyncio.Task] = None
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
        return self._wallet_address

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

    @network_transaction_fee.setter
    def network_transaction_fee(self, new_fee: TokenAmount):
        self._network_transaction_fee = new_fee

    @property
    def in_flight_orders(self) -> Dict[str, GatewayInFlightOrder]:
        return self._order_tracker.active_orders

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
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._get_gas_estimate_task = safe_ensure_future(self.get_gas_estimate())
            if self.chain == "ethereum":
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
            self._get_gas_estimate_task = None
        if self._get_allowances_task is not None:
            self._get_allowances_task.cancel()
            self._get_allowances_task = None

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
            self._chain_info = await self._get_gateway_instance().get_network_status(
                chain=self.chain, network=self.network
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

    async def get_gas_estimate(self):
        """
        Gets the gas estimates for the connector.
        """
        try:
            response: Dict[Any] = await self._get_gateway_instance().estimate_gas(
                chain=self.chain, network=self.network
            )
            self.network_transaction_fee = TokenAmount(
                response.get("gasPriceToken"), Decimal(response.get("gasCost"))
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting gas price estimates for {self.connector_name} on {self.network}.",
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
            "network_transaction_fee": self.network_transaction_fee is not None if self._trading_required else True,
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
        connector_tokens = GatewayConnectionSetting.get_connector_spec_from_market_name(self._name).get("tokens", "").split(",")
        last_tick = self._last_balance_poll_timestamp
        current_tick = self.current_timestamp
        if not on_interval or (current_tick - last_tick) > self.UPDATE_BALANCE_INTERVAL:
            self._last_balance_poll_timestamp = current_tick
            local_asset_names = set(self._account_balances.keys())
            remote_asset_names = set()
            token_list = list(self._tokens) + [self._native_currency] + connector_tokens
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
                order_type=OrderType.LIMIT,
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

    async def update_order_status(self, tracked_orders: List[GatewayInFlightOrder]):
        """
        Calls REST API to get status update for each in-flight AMM orders.
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

            # Call chain-specific method to get transaction receipt
            tx_receipt = self._get_transaction_receipt_from_details(tx_details)

            # Chain-specific check for transaction success
            if self._is_transaction_successful(tx_status, tx_receipt):
                # Calculate fee using chain-specific method
                fee = self._calculate_transaction_fee(tracked_order, tx_receipt)

                self.process_trade_fill_update(tracked_order=tracked_order, fee=fee)

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.FILLED,
                )
                self._order_tracker.process_order_update(order_update)

            # Check if transaction is still pending using chain-specific method
            elif self._is_transaction_pending(tx_status):
                pass

            # Transaction failed
            elif self._is_transaction_failed(tx_status, tx_receipt):
                self.logger().network(
                    f"Error fetching transaction status for the order {tracked_order.client_order_id}: {tx_details}.",
                    app_warning_msg=f"Failed to fetch transaction status for the order {tracked_order.client_order_id}."
                )
                await self._order_tracker.process_order_not_found(tracked_order.client_order_id)

    def _get_transaction_receipt_from_details(self, tx_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.chain == "ethereum":
            return tx_details.get("txReceipt")
        elif self.chain == "solana":
            return tx_details.get("txData")
        raise NotImplementedError(f"Unsupported chain: {self.chain}")

    def _is_transaction_successful(self, tx_status: int, tx_receipt: Optional[Dict[str, Any]]) -> bool:
        if self.chain == "ethereum":
            return tx_status == 1 and tx_receipt is not None and tx_receipt.get("status") == 1
        elif self.chain == "solana":
            return tx_status == 1 and tx_receipt is not None
        raise NotImplementedError(f"Unsupported chain: {self.chain}")

    def _is_transaction_pending(self, tx_status: int) -> bool:
        if self.chain == "ethereum":
            return tx_status in [0, 2, 3]
        elif self.chain == "solana":
            return tx_status == 0
        raise NotImplementedError(f"Unsupported chain: {self.chain}")

    def _is_transaction_failed(self, tx_status: int, tx_receipt: Optional[Dict[str, Any]]) -> bool:
        if self.chain == "ethereum":
            return tx_status == -1 or (tx_receipt is not None and tx_receipt.get("status") == 0)
        elif self.chain == "solana":
            return tx_status == -1
        raise NotImplementedError(f"Unsupported chain: {self.chain}")

    def _calculate_transaction_fee(self, tracked_order: GatewayInFlightOrder, tx_receipt: Dict[str, Any]) -> Decimal:
        if self.chain == "ethereum":
            gas_used: int = tx_receipt["gasUsed"]
            gas_price: Decimal = tracked_order.gas_price
            return Decimal(str(gas_used)) * gas_price / Decimal(1e9)
        elif self.chain == "solana":
            return Decimal(tx_receipt["meta"]["fee"]) / Decimal(1e9)
        raise NotImplementedError(f"Unsupported chain: {self.chain}")
