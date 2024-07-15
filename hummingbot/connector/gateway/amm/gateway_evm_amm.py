import asyncio
import copy
import itertools as it
import logging
import re
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union, cast

from async_timeout import timeout

from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_price_shim import GatewayPriceShim
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import (
    OrderType,
    TokenApprovalCancelledEvent,
    TokenApprovalEvent,
    TokenApprovalFailureEvent,
    TokenApprovalSuccessEvent,
    TradeType,
)
from hummingbot.core.gateway import check_transaction_exceptions
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")


class GatewayEVMAMM(ConnectorBase):
    """
    Defines basic functions common to connectors that interact with Gateway.
    """

    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 1.0
    UPDATE_BALANCE_INTERVAL = 30.0
    APPROVAL_ORDER_ID_PATTERN = re.compile(r"approve-(\w+)-(\w+)")

    _connector_name: str
    _name: str
    _chain: str
    _network: str
    _trading_pairs: List[str]
    _tokens: Set[str]
    _wallet_address: str
    _trading_required: bool
    _ev_loop: asyncio.AbstractEventLoop
    _last_poll_timestamp: float
    _last_balance_poll_timestamp: float
    _last_est_gas_cost_reported: float
    _allowances: Dict[str, Decimal]
    _chain_info: Dict[str, Any]
    _status_polling_task: Optional[asyncio.Task]
    _get_chain_info_task: Optional[asyncio.Task]
    _update_allowances: Optional[asyncio.Task]
    _poll_notifier: Optional[asyncio.Event]
    _native_currency: str
    _amount_quantum_dict: Dict[str, Decimal]

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 connector_name: str,
                 chain: str,
                 network: str,
                 address: str,
                 trading_pairs: List[str] = [],
                 additional_spenders: List[str] = [],  # not implemented
                 trading_required: bool = True
                 ):
        """
        :param connector_name: name of connector on gateway
        :param chain: refers to a block chain, e.g. ethereum or avalanche
        :param network: refers to a network of a particular blockchain e.g. mainnet or kovan
        :param address: the address of the eth wallet which has been added on gateway
        :param trading_pairs: a list of trading pairs
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        self._connector_name = connector_name
        self._name = "_".join([connector_name, chain, network])
        super().__init__(client_config_map)
        self._chain = chain
        self._network = network
        self._trading_pairs = trading_pairs
        self._tokens = set()
        [self._tokens.update(set(trading_pair.split("_")[0].split("-"))) for trading_pair in trading_pairs]
        self._wallet_address = address
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._last_poll_timestamp = 0.0
        self._last_balance_poll_timestamp = time.time()
        self._last_est_gas_cost_reported = 0
        self._allowances = {}
        self._chain_info = {}
        self._status_polling_task = None
        self._get_chain_info_task = None
        self._get_gas_estimate_task = None
        self._poll_notifier = None
        self._native_currency = None
        self._network_transaction_fee: Optional[TokenAmount] = None
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
        This returns the name of connector/protocol to be connected to on Gateway.
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
    def approval_orders(self) -> List[GatewayInFlightOrder]:
        return [
            approval_order
            for approval_order in self._order_tracker.active_orders.values()
            if approval_order.is_approval_request
        ]

    @property
    def amm_orders(self) -> List[GatewayInFlightOrder]:
        return [
            in_flight_order
            for in_flight_order in self._order_tracker.active_orders.values()
            if in_flight_order.is_open
        ]

    @property
    def canceling_orders(self) -> List[GatewayInFlightOrder]:
        return [
            cancel_order
            for cancel_order in self.amm_orders
            if cancel_order.is_pending_cancel_confirmation
        ]

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self.amm_orders
        ]

    @property
    def network_transaction_fee(self) -> TokenAmount:
        """
        The most recently known transaction fee (i.e. gas fees) required for making trades.
        """
        return self._network_transaction_fee

    @network_transaction_fee.setter
    def network_transaction_fee(self, new_fee: TokenAmount):
        self._network_transaction_fee = new_fee

    @property
    def in_flight_orders(self) -> Dict[str, GatewayInFlightOrder]:
        return self._order_tracker.active_orders

    @property
    def tracking_states(self) -> Dict[str, Any]:
        """
        Returns a dictionary associating current active orders client id to their JSON representation
        """
        return {
            key: value.to_json()
            for key, value in self.in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        *required
        Updates inflight order statuses from API results
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        self._order_tracker._in_flight_orders.update({
            key: GatewayInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    def create_approval_order_id(self, token_symbol: str) -> str:
        return f"approve-{self.connector_name}-{token_symbol}"

    def get_token_symbol_from_approval_order_id(self, approval_order_id: str) -> Optional[str]:
        match = self.APPROVAL_ORDER_ID_PATTERN.search(approval_order_id)
        if match:
            return match.group(2)
        return None

    @staticmethod
    def create_market_order_id(side: TradeType, trading_pair: str) -> str:
        return f"{side.name.lower()}-{trading_pair}-{get_tracking_nonce()}"

    def is_pending_approval(self, token: str) -> bool:
        for order in self.approval_orders:
            if token in order.client_order_id:
                return order.is_pending_approval
        return False

    async def load_token_data(self):
        tokens = await GatewayHttpClient.get_instance().get_tokens(self.chain, self.network)
        for t in tokens.get("tokens", []):
            self._amount_quantum_dict[t["symbol"]] = Decimal(str(10 ** -t["decimals"]))

    async def get_chain_info(self):
        """
        Calls the base endpoint of the connector on Gateway to know basic info about chain being used.
        """
        try:
            self._chain_info = await self._get_gateway_instance().get_network_status(
                chain=self.chain, network=self.network
            )
            if type(self._chain_info) is not list:
                self._native_currency = self._chain_info.get("nativeCurrency", "ETH")
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
            response: Dict[Any] = await self._get_gateway_instance().amm_estimate_gas(
                chain=self.chain, network=self.network, connector=self.connector_name
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
        process_exception: bool = True
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
            self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)
            if process_exception is True:
                gas_limit: int = int(price_response["gasLimit"])
                exceptions: List[str] = check_transaction_exceptions(
                    allowances=self._allowances,
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

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_quote_price(
            self,
            trading_pair: str,
            is_buy: bool,
            amount: Decimal,
            ignore_shim: bool = False
    ) -> Optional[Decimal]:
        """
        Retrieves a quote price.

        :param trading_pair: The market trading pair
        :param is_buy: True for an intention to buy, False for an intention to sell
        :param amount: The amount required (in base token unit)
        :param ignore_shim: Ignore the price shim, and return the real price on the network
        :return: The quote price.
        """
        pool_id = None

        try:
            trading_pair, pool_id = trading_pair.split("_")
        except Exception:
            pass
        base, quote = trading_pair.split("-")
        side: TradeType = TradeType.BUY if is_buy else TradeType.SELL

        # Get the price from gateway price shim for integration tests.
        if not ignore_shim:
            test_price: Optional[Decimal] = await GatewayPriceShim.get_instance().get_connector_price(
                self.connector_name,
                self.chain,
                self.network,
                trading_pair,
                is_buy,
                amount
            )
            if test_price is not None:
                # Grab the gas price for test net.
                try:
                    resp: Dict[str, Any] = await self._get_gateway_instance().get_price(
                        self.chain, self.network, self.connector_name, base, quote, amount, side
                    )
                    gas_price_token: str = resp["gasPriceToken"]
                    gas_cost: Decimal = Decimal(resp["gasCost"])
                    self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
                return test_price

        # Pull the price from gateway.
        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().get_price(
                self.chain, self.network, self.connector_name, base, quote, amount, side, pool_id=pool_id
            )
            return self.parse_price_response(base, quote, amount, side, price_response=resp)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting quote price for {trading_pair} {side} order for {amount} amount.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_order_price(
            self,
            trading_pair: str,
            is_buy: bool,
            amount: Decimal,
            ignore_shim: bool = False
    ) -> Decimal:

        """
        This is simply the quote price
        """
        return await self.get_quote_price(trading_pair, is_buy, amount, ignore_shim=ignore_shim)

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs) -> str:
        """
        Buys an amount of base token for a given price (or cheaper).
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param order_type: Any order type is fine, not needed for this.
        :param price: The maximum price for the order.
        :return: A newly created order id (internal).
        """
        return self.place_order(True, trading_pair, amount, price)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs) -> str:
        """
        Sells an amount of base token for a given price (or at a higher price).
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param order_type: Any order type is fine, not needed for this.
        :param price: The minimum price for the order.
        :return: A newly created order id (internal).
        """
        return self.place_order(False, trading_pair, amount, price)

    def place_order(self, is_buy: bool, trading_pair: str, amount: Decimal, price: Decimal, **request_args) -> str:
        """
        Places an order.
        :param is_buy: True for buy order
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param price: The minimum price for the order.
        :return: A newly created order id (internal).
        """
        side: TradeType = TradeType.BUY if is_buy else TradeType.SELL
        order_id: str = self.create_market_order_id(side, trading_pair)
        safe_ensure_future(self._create_order(side, order_id, trading_pair, amount, price, **request_args))
        return order_id

    async def _create_order(
            self,
            trade_type: TradeType,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            price: Decimal,
            **request_args
    ):
        """
        Calls buy or sell API end point to place an order, starts tracking the order and triggers relevant order events.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param price: The order price
        """
        pool_id = None

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        try:
            trading_pair, pool_id = trading_pair.split("_")
        except Exception:
            pass
        base, quote = trading_pair.split("-")
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  price=price,
                                  amount=amount)
        try:
            order_result: Dict[str, Any] = await self._get_gateway_instance().amm_trade(
                self.chain,
                self.network,
                self.connector_name,
                self.address,
                base,
                quote,
                trade_type,
                amount,
                price,
                pool_id=pool_id,
                **request_args
            )
            transaction_hash: Optional[str] = order_result.get("txHash")
            if transaction_hash is not None and transaction_hash != "":
                gas_cost: Decimal = Decimal(order_result.get("gasCost"))
                gas_price_token: str = order_result.get("gasPriceToken")
                self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=order_id,
                    exchange_order_id=transaction_hash,
                    trading_pair=trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.OPEN,  # Assume that the transaction has been successfully mined.
                    misc_updates={
                        "nonce": order_result.get("nonce"),
                        "gas_price": Decimal(order_result.get("gasPrice")),
                        "gas_limit": int(order_result.get("gasLimit")),
                        "gas_cost": Decimal(order_result.get("gasCost")),
                        "gas_price_token": order_result.get("gasPriceToken"),
                        "fee_asset": self._native_currency
                    }
                )
                self._order_tracker.process_order_update(order_update)
            else:
                raise ValueError

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Error submitting {trade_type.name} swap order to {self.connector_name} on {self.network} for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True
            )
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED
            )
            self._order_tracker.process_order_update(order_update)

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

    def processs_trade_fill_update(self, tracked_order: GatewayInFlightOrder, fee: Decimal):
        trade_fee: TradeFeeBase = AddedToCostTradeFee(
            flat_fees=[TokenAmount(tracked_order.fee_asset, fee)]
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
        self.logger().debug(
            "Polling for order status updates of %d orders.",
            len(tracked_orders)
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

                self.processs_trade_fill_update(tracked_order=tracked_order, fee=fee)

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

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("1e-15")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        base, quote = trading_pair.split("_")[0].split("-")
        return max(self._amount_quantum_dict[base], self._amount_quantum_dict[quote])

    @property
    def ready(self):
        return all(self.status_dict.values())

    def has_allowances(self) -> bool:
        """
        Checks if all tokens have allowance (an amount approved)
        """
        allowances_available = all(amount > s_decimal_0 for amount in self._allowances.values())
        return ((len(self._allowances.values()) == len(self._tokens)) and
                (allowances_available))

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "allowances: use trading interface to do manual approval.": self.has_allowances() if self._trading_required else True,
            "native_currency": self._native_currency is not None,
            "network_transaction_fee": self.network_transaction_fee is not None if self._trading_required else True,
        }

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

    async def check_network(self) -> NetworkStatus:
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

    async def _update_nonce(self, new_nonce: Optional[int] = None):
        """
        Call the gateway API to get the current nonce for self.address
        """
        if not new_nonce:
            resp_json: Dict[str, Any] = await self._get_gateway_instance().get_evm_nonce(self.chain, self.network, self.address)
            new_nonce: int = resp_json.get("nonce")

        self._nonce = new_nonce

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

    async def update_balances(self, on_interval: bool = False):
        """
        Calls Eth API to update total and available balances.
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

    def _get_gateway_instance(self) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        return gateway_instance
