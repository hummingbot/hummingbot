import asyncio
import copy
import itertools as it
import logging
import re
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Type, Union, cast

from async_timeout import timeout

from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.amm_lp.gateway_in_flight_lp_order import GatewayInFlightLPOrder
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.events import (
    LPType,
    MarketEvent,
    OrderCancelledEvent,
    RangePositionClosedEvent,
    RangePositionFeeCollectedEvent,
    RangePositionLiquidityAddedEvent,
    RangePositionLiquidityRemovedEvent,
    RangePositionUpdateEvent,
    RangePositionUpdateFailureEvent,
    TokenApprovalCancelledEvent,
    TokenApprovalEvent,
    TokenApprovalFailureEvent,
    TokenApprovalSuccessEvent,
)
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


class GatewayEVMAMMLP(ConnectorBase):
    """
    Defines basic funtions common to LPing connectors that interract with Gateway.
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
    _all_spenders: List[str]
    _tokens: Set[str]
    _wallet_address: str
    _trading_required: bool
    _ev_loop: asyncio.AbstractEventLoop
    _last_poll_timestamp: float
    _last_balance_poll_timestamp: float
    _last_est_gas_cost_reported: float
    _in_flight_orders: Dict[str, GatewayInFlightLPOrder]
    _allowances: Dict[str, Decimal]
    _chain_info: Dict[str, Any]
    _status_polling_task: Optional[asyncio.Task]
    _get_chain_info_task: Optional[asyncio.Task]
    _auto_approve_task: Optional[asyncio.Task]
    _poll_notifier: Optional[asyncio.Event]
    _nonce: Optional[int]
    _native_currency: str
    _amount_quantum_dict: Dict[str, Decimal]

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 connector_name: str,
                 chain: str,
                 network: str,
                 address: str,
                 trading_pairs: List[str] = [],
                 additional_spenders: List[str] = [],
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
        self._all_spenders = additional_spenders
        self._all_spenders.append(self._connector_name)
        self._tokens = set()
        [self._tokens.update(set(trading_pair.split("-"))) for trading_pair in trading_pairs]
        self._wallet_address = address
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._last_poll_timestamp = 0.0
        self._last_balance_poll_timestamp = time.time()
        self._in_flight_orders = {}
        self._allowances = {}
        self._chain_info = {}
        self._status_polling_task = None
        self._get_chain_info_task = None
        self._auto_approve_task = None
        self._get_gas_estimate_task = None
        self._poll_notifier = None
        self._nonce: Optional[int] = None
        self._native_currency = None
        self._network_transaction_fee: Optional[TokenAmount] = None
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

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return []

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

    @staticmethod
    def is_approval_order(in_flight_order: GatewayInFlightLPOrder) -> bool:
        return in_flight_order.client_order_id.split("-")[0] == "approve"

    @property
    def approval_orders(self) -> List[GatewayInFlightLPOrder]:
        return [
            approval_order
            for approval_order in self._in_flight_orders.values()
            if self.is_approval_order(approval_order)
            and not approval_order.is_pending_cancel_confirmation
        ]

    @property
    def amm_lp_orders(self) -> List[GatewayInFlightLPOrder]:
        return [
            in_flight_order
            for in_flight_order in self._in_flight_orders.values()
            if not self.is_approval_order(in_flight_order)
            and not in_flight_order.is_pending_cancel_confirmation
        ]

    @property
    def canceling_orders(self) -> List[GatewayInFlightLPOrder]:
        return [
            cancel_order
            for cancel_order in self._in_flight_orders.values()
            if cancel_order.is_pending_cancel_confirmation
        ]

    @property
    def network_transaction_fee(self) -> TokenAmount:
        """
        The most recently known transaction fee (i.e. gas fees) required for making transactions.
        """
        return self._network_transaction_fee

    @network_transaction_fee.setter
    def network_transaction_fee(self, new_fee: TokenAmount):
        self._network_transaction_fee = new_fee

    def create_approval_order_id(self, spender: str, token_symbol: str) -> str:
        return f"approve-{spender}-{token_symbol}"

    def get_token_symbol_from_approval_order_id(self, approval_order_id: str) -> Optional[str]:
        match = self.APPROVAL_ORDER_ID_PATTERN.search(approval_order_id)
        if match:
            return f"{match.group(1)}_{match.group(2)}"
        return None

    @staticmethod
    def create_lp_order_id(action: LPType, trading_pair: str) -> str:
        return f"{action.name.lower()}-{trading_pair}-{get_tracking_nonce()}"

    def is_pending_approval(self, spender_token: str) -> bool:
        pending_approval_tokens: List[Optional[str]] = [
            self.get_token_symbol_from_approval_order_id(order_id)
            for order_id in self._in_flight_orders.keys()
        ]
        return True if spender_token in pending_approval_tokens else False

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
            if not isinstance(self._chain_info, list):
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

    async def auto_approve(self):
        """
        Automatically approves trading pair tokens for contract(s).
        It first checks if there are any already approved amount (allowance)
        """
        await self.update_allowances()
        for spender_token, amount in self._allowances.items():
            if amount <= s_decimal_0 and not self.is_pending_approval(spender_token):
                spender, token = spender_token.split("_")
                await self.approve_token(spender, token)

    async def approve_token(self, spender: str, token_symbol: str, **request_args) -> Optional[GatewayInFlightLPOrder]:
        """
        Approves contract as a spender for a token.
        :param spender: contract to approve for.
        :param token_symbol: token to approve.
        """
        order_id: str = self.create_approval_order_id(spender, token_symbol)
        resp: Dict[str, Any] = await self._get_gateway_instance().approve_token(
            self.chain,
            self.network,
            self.address,
            token_symbol,
            spender,
            **request_args
        )
        self.start_tracking_order(order_id, None, token_symbol)

        if "hash" in resp.get("approval", {}).keys():
            nonce: int = resp.get("nonce")
            await self._update_nonce(nonce)
            hash = resp["approval"]["hash"]
            tracked_order = self._in_flight_orders.get(order_id)
            tracked_order.update_exchange_order_id(hash)
            tracked_order.nonce = nonce
            self.logger().info(
                f"Maximum {token_symbol} approval for {spender} contract sent, hash: {hash}."
            )
            return tracked_order
        else:
            self.logger().info(f"Missing data from approval result. Incomplete return result for ({resp.keys()})")
            self.logger().info(f"Approval for {token_symbol} on {spender} failed.")
            return None

    async def update_allowances(self):
        self._allowances = await self.get_allowances()

    async def get_allowances(self) -> Dict[str, Decimal]:
        """
        Retrieves allowances for token in trading_pairs
        :return: A dictionary of token and its allowance.
        """
        ret_val = {}
        approval_lists: List[str] = await safe_gather(*[
            self._get_gateway_instance().get_allowances(
                self.chain, self.network, self.address, list(self._tokens), spender
            ) for spender in self._all_spenders
        ])

        for spender, approval_list in zip(self._all_spenders, approval_lists):
            for token, amount in approval_list["approvals"].items():
                ret_val[f"{spender}_{token}"] = Decimal(str(amount))
        return ret_val

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_price(
            self,
            trading_pair: str,
            fee: str,
            period: Optional[int] = 1,
            interval: Optional[int] = 1,
    ) -> Optional[List[Decimal]]:
        """
        Retrieves a quote price.

        :param trading_pair: The market trading pair
        :param fee: The fee tier to get price data from
        :param period: The period of time to lookup price data (in seconds)
        :param interval: The interval within the specified period of time to lookup price data (in seconds)
        :return: A list of prices.
        """

        token_0, token_1 = trading_pair.split("-")

        # Pull the current/historical price(s) from gateway.
        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().amm_lp_price(
                self.chain, self.network, self.connector_name, token_0, token_1, fee.upper(), period, interval
            )
            if "info" in resp.keys():
                self.logger().info(f"Unable to get price data. {resp['info']}")
                return ["0"]
            return [Decimal(price) for price in resp.get("prices", [])]
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting price data for {trading_pair}.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    def add_liquidity(self, trading_pair: str, amount_0: Decimal, amount_1: Decimal, lower_price: Decimal, upper_price: Decimal, fee: str, **request_args) -> str:
        """
        Add/increases liquidity.
        :param trading_pair: The market trading pair
        :param amount_0: The base amount
        :param amount_1: The quote amount
        :param lower_price: The lower-bound price for the range position order.
        :param upper_price: The upper-bound price for the range position order.
        :param fee: The fee tier to provide liquidity on.
        :return: A newly created order id (internal).
        """
        order_id: str = self.create_lp_order_id(LPType.ADD, trading_pair)
        safe_ensure_future(self._add_liquidity(order_id, trading_pair, amount_0, amount_1, lower_price, upper_price, fee, **request_args))
        return order_id

    async def _add_liquidity(
            self,
            order_id: str,
            trading_pair: str,
            amount_0: Decimal,
            amount_1: Decimal,
            lower_price: Decimal,
            upper_price: Decimal,
            fee: str,
            **request_args
    ):
        """
        Calls /liquidity/add API end point to add/increase liquidity, starts tracking the order and triggers relevant order events.
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount_0: The base amount
        :param amount_1: The quote amount
        :param lower_price: The lower-bound to add liquidity
        :param upper_price: The upper-bound to add liquidity
        :param fee: the market tier to add liquidity on
        """

        lp_type = LPType.ADD
        amount_0 = self.quantize_order_amount(trading_pair, amount_0)
        amount_1 = self.quantize_order_amount(trading_pair, amount_1)
        lower_price = self.quantize_order_price(trading_pair, lower_price)
        upper_price = self.quantize_order_price(trading_pair, upper_price)
        token_0, token_1 = trading_pair.split("-")
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  lp_type=lp_type,
                                  lower_price=lower_price,
                                  upper_price=upper_price,
                                  amount_0=amount_0,
                                  amount_1=amount_1)
        try:
            order_result: Dict[str, Any] = await self._get_gateway_instance().amm_lp_add(
                self.chain,
                self.network,
                self.connector_name,
                self.address,
                token_0,
                token_1,
                amount_0,
                amount_1,
                fee,
                lower_price,
                upper_price,
                **request_args
            )
            transaction_hash: str = order_result.get("txHash")
            nonce: int = order_result.get("nonce")
            await self._update_nonce(nonce)
            gas_price: Decimal = Decimal(order_result.get("gasPrice"))
            gas_limit: int = int(order_result.get("gasLimit"))
            gas_cost: Decimal = Decimal(order_result.get("gasCost"))
            gas_price_token: str = order_result.get("gasPriceToken")
            tracked_order: GatewayInFlightLPOrder = self._in_flight_orders.get(order_id)
            self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)

            if tracked_order is not None:
                self.logger().info(f"Created {lp_type.name} liquidity order {order_id} txHash: {transaction_hash} "
                                   f"on {self.network}. Estimated Gas Cost: {gas_cost} "
                                   f" (gas limit: {gas_limit}, gas price: {gas_price})")
                tracked_order.update_exchange_order_id(transaction_hash)
                tracked_order.gas_price = gas_price
                tracked_order.current_state = OrderState.OPEN
            if transaction_hash is not None:
                tracked_order.nonce = nonce
                tracked_order.fee_tier = fee
                tracked_order.fee_asset = self._native_currency
                event_tag: MarketEvent = MarketEvent.RangePositionUpdate
                event_class: Type[RangePositionUpdateEvent] = RangePositionUpdateEvent
                self.trigger_event(event_tag, event_class(
                    timestamp=self.current_timestamp,
                    order_id=order_id,
                    exchange_order_id=transaction_hash,
                    order_action=lp_type,
                    trading_pair=trading_pair,
                    fee_tier=fee,
                    lower_price=lower_price,
                    upper_price=upper_price,
                    amount=amount_0,
                    creation_timestamp=tracked_order.creation_timestamp,
                ))
            else:
                self.trigger_event(MarketEvent.RangePositionUpdateFailure,
                                   RangePositionUpdateFailureEvent(self.current_timestamp, order_id, lp_type))
                self.stop_tracking_order(order_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Error submitting {lp_type.name} liquidity order to {self.connector_name} on {self.network} for "
                f"{trading_pair} ",
                exc_info=True
            )
            self.trigger_event(MarketEvent.RangePositionUpdateFailure,
                               RangePositionUpdateFailureEvent(self.current_timestamp, order_id, lp_type))
            self.stop_tracking_order(order_id)

    def remove_liquidity(self, trading_pair: str, token_id: int, reduce_percent: Optional[int] = 100, **request_args) -> str:
        """
        Remove/reduce liquidity.
        :param trading_pair: The market trading pair
        :param token_id: The market trading pair
        :param reduce_percent: Percentage of liquidity to remove(as integer).
        :return: A newly created order id (internal).
        """
        order_id: str = self.create_lp_order_id(LPType.REMOVE, trading_pair)
        safe_ensure_future(self._remove_liquidity(order_id, trading_pair, token_id, reduce_percent, **request_args))
        return order_id

    async def _remove_liquidity(
            self,
            order_id: str,
            trading_pair: str,
            token_id: int,
            reduce_percent: int,
            **request_args
    ):
        """
        Calls /liquidity/remove API end point to remove/decrease liquidity, starts tracking the order and triggers relevant order events.
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param token_id: The market trading pair
        :param reduce_percent: Percentage of liquidity to remove(as integer).
        """

        lp_type = LPType.REMOVE
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  lp_type=lp_type,
                                  token_id=token_id)
        try:
            order_result: Dict[str, Any] = await self._get_gateway_instance().amm_lp_remove(
                self.chain,
                self.network,
                self.connector_name,
                self.address,
                token_id,
                reduce_percent,
                **request_args
            )
            transaction_hash: str = order_result.get("txHash")
            nonce: int = order_result.get("nonce")
            await self._update_nonce(nonce)
            gas_price: Decimal = Decimal(order_result.get("gasPrice"))
            gas_limit: int = int(order_result.get("gasLimit"))
            gas_cost: Decimal = Decimal(order_result.get("gasCost"))
            gas_price_token: str = order_result.get("gasPriceToken")
            tracked_order: GatewayInFlightLPOrder = self._in_flight_orders.get(order_id)
            self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)

            if tracked_order is not None:
                self.logger().info(f"Created {lp_type.name} liquidity order {order_id} txHash: {transaction_hash} "
                                   f"on {self.network}. Estimated Gas Cost: {gas_cost} "
                                   f" (gas limit: {gas_limit}, gas price: {gas_price})")
                tracked_order.update_exchange_order_id(transaction_hash)
                tracked_order.gas_price = gas_price
                tracked_order.current_state = OrderState.OPEN
            if transaction_hash is not None:
                tracked_order.nonce = nonce
                tracked_order.fee_asset = self._native_currency
                event_tag: MarketEvent = MarketEvent.RangePositionUpdate
                event_class: Type[RangePositionUpdateEvent] = RangePositionUpdateEvent
                self.trigger_event(event_tag, event_class(
                    timestamp=self.current_timestamp,
                    order_id=order_id,
                    exchange_order_id=transaction_hash,
                    order_action=lp_type,
                    trading_pair=trading_pair,
                    creation_timestamp=tracked_order.creation_timestamp,
                    token_id=token_id,
                ))
            else:
                self.trigger_event(MarketEvent.RangePositionUpdateFailure,
                                   RangePositionUpdateFailureEvent(self.current_timestamp, order_id, lp_type))
                self.stop_tracking_order(order_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Error submitting {lp_type.name} liquidity order to {self.connector_name} on {self.network} for "
                f"{trading_pair} ",
                exc_info=True
            )
            self.trigger_event(MarketEvent.RangePositionUpdateFailure,
                               RangePositionUpdateFailureEvent(self.current_timestamp, order_id, lp_type))
            self.stop_tracking_order(order_id)

    def collect_fees(self, trading_pair: str, token_id: int, **request_args) -> str:
        """
        Collect earned fees.
        :param trading_pair: The market trading pair
        :param token_id: The market trading pair
        :return: A newly created order id (internal).
        """
        order_id: str = self.create_lp_order_id(LPType.COLLECT, trading_pair)
        safe_ensure_future(self._collect_fees(order_id, trading_pair, token_id, **request_args))
        return order_id

    async def _collect_fees(
            self,
            order_id: str,
            trading_pair: str,
            token_id: int,
            **request_args
    ):
        """
        Calls /liquidity/collect_fees API end point to collect earned fees, starts tracking the order and triggers relevant order events.
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param token_id: The market trading pair
        """

        lp_type = LPType.COLLECT
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  lp_type=lp_type,
                                  token_id=token_id)
        try:
            order_result: Dict[str, Any] = await self._get_gateway_instance().amm_lp_collect_fees(
                self.chain,
                self.network,
                self.connector_name,
                self.address,
                token_id,
                **request_args
            )
            transaction_hash: str = order_result.get("txHash")
            nonce: int = order_result.get("nonce")
            await self._update_nonce(nonce)
            gas_price: Decimal = Decimal(order_result.get("gasPrice"))
            gas_limit: int = int(order_result.get("gasLimit"))
            gas_cost: Decimal = Decimal(order_result.get("gasCost"))
            gas_price_token: str = order_result.get("gasPriceToken")
            tracked_order: GatewayInFlightLPOrder = self._in_flight_orders.get(order_id)
            self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)

            if tracked_order is not None:
                self.logger().info(f"Submitted {lp_type.name} request {order_id} txHash: {transaction_hash} "
                                   f"on {self.network}. Estimated Gas Cost: {gas_cost} "
                                   f" (gas limit: {gas_limit}, gas price: {gas_price})")
                tracked_order.update_exchange_order_id(transaction_hash)
                tracked_order.gas_price = gas_price
                tracked_order.current_state = OrderState.OPEN
            if transaction_hash is not None:
                tracked_order.nonce = nonce
                tracked_order.fee_asset = self._native_currency
                event_tag: MarketEvent = MarketEvent.RangePositionUpdate
                event_class: Type[RangePositionUpdateEvent] = RangePositionUpdateEvent
                self.trigger_event(event_tag, event_class(
                    timestamp=self.current_timestamp,
                    order_id=order_id,
                    exchange_order_id=transaction_hash,
                    order_action=lp_type,
                    trading_pair=trading_pair,
                    creation_timestamp=tracked_order.creation_timestamp,
                    token_id=token_id,
                ))
            else:
                self.trigger_event(MarketEvent.RangePositionUpdateFailure,
                                   RangePositionUpdateFailureEvent(self.current_timestamp, order_id, lp_type))
                self.stop_tracking_order(order_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Error submitting {lp_type.name} request to {self.connector_name} on {self.network} for "
                f"{trading_pair} ",
                exc_info=True
            )
            self.trigger_event(MarketEvent.RangePositionUpdateFailure,
                               RangePositionUpdateFailureEvent(self.current_timestamp, order_id, lp_type))
            self.stop_tracking_order(order_id)

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: Optional[str] = None,
                             trading_pair: str = "",
                             lp_type: Optional[LPType] = LPType.ADD,
                             lower_price: Optional[Decimal] = s_decimal_0,
                             upper_price: Optional[Decimal] = s_decimal_0,
                             amount_0: Optional[Decimal] = s_decimal_0,
                             amount_1: Optional[Decimal] = s_decimal_0,
                             token_id: Optional[int] = 0,
                             gas_price: Decimal = s_decimal_0):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = GatewayInFlightLPOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            lp_type=lp_type,
            lower_price=lower_price,
            upper_price=upper_price,
            amount_0=amount_0,
            amount_1=amount_1,
            token_id=token_id,
            gas_price=gas_price,
            creation_timestamp=self.current_timestamp
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def update_token_approval_status(self, tracked_approvals: List[GatewayInFlightLPOrder]):
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
                    self.trigger_event(
                        TokenApprovalEvent.ApprovalSuccessful,
                        TokenApprovalSuccessEvent(
                            self.current_timestamp,
                            self.connector_name,
                            token_symbol
                        )
                    )
                    safe_ensure_future(self.update_allowances())
                else:
                    self.logger().warning(
                        f"Token approval for {tracked_approval.client_order_id} on {self.connector_name} failed."
                    )
                    self.trigger_event(
                        TokenApprovalEvent.ApprovalFailed,
                        TokenApprovalFailureEvent(
                            self.current_timestamp,
                            self.connector_name,
                            token_symbol
                        )
                    )
                self.stop_tracking_order(tracked_approval.client_order_id)

    async def update_canceling_transactions(self, canceled_tracked_orders: List[GatewayInFlightLPOrder]):
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
                        if not self.is_approval_order(tracked_order):
                            self.trigger_event(
                                MarketEvent.OrderCancelled,
                                OrderCancelledEvent(
                                    self.current_timestamp,
                                    tracked_order.client_order_id,
                                    tracked_order.exchange_order_id,
                                )
                            )
                            self.logger().info(f"The {tracked_order.lp_type.name} order "
                                               f"{tracked_order.client_order_id} has been canceled "
                                               f"according to the order status API.")
                        elif self.is_approval_order(tracked_order):
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
                        tracked_order.current_state = OrderState.CANCELED
                    self.stop_tracking_order(tracked_order.client_order_id)

    async def update_order_status(self, tracked_orders: List[GatewayInFlightLPOrder]):
        """
        Calls REST API to get status update for each in-flight amm orders.
        """
        if len(tracked_orders) < 1:
            return

        # filter non nft orders
        pending_nft_orders = [new_order for new_order in tracked_orders
                              if not new_order.is_nft or (new_order.is_nft and new_order.current_state == OrderState.OPEN)]
        tx_hash_list: List[str] = await safe_gather(
            *[tracked_order.get_exchange_order_id() for tracked_order in pending_nft_orders]
        )
        self.logger().debug(
            "Polling for order status updates of %d orders.",
            len(tracked_orders)
        )
        update_results: List[Union[Dict[str, Any], Exception]] = await safe_gather(*[
            self._get_gateway_instance().get_transaction_status(
                self.chain,
                self.network,
                tx_hash,
                connector=self.connector_name
            )
            for tx_hash in tx_hash_list
        ], return_exceptions=True)
        for tracked_order, update_result in zip(pending_nft_orders, update_results):
            if isinstance(update_result, Exception):
                raise update_result
            if "txHash" not in update_result:
                self.logger().error(f"No txHash field for transaction status of {tracked_order.client_order_id}: "
                                    f"{update_result}.")
                continue
            if update_result["txStatus"] == 1:
                if update_result["txReceipt"]["status"] == 1:
                    gas_used: int = update_result["txReceipt"]["gasUsed"]
                    gas_price: Decimal = tracked_order.gas_price
                    fee: Decimal = Decimal(str(gas_used)) * Decimal(str(gas_price)) / Decimal(str(1e9))
                    tracked_order.fee_paid = fee
                    if tracked_order.lp_type == LPType.ADD:
                        token_id = int(list(filter(lambda evt: evt["name"] == "tokenId", list(filter(lambda log: log["name"] == "IncreaseLiquidity", update_result["txReceipt"]["logs"]))[0]["events"]))[0]["value"])
                        self.logger().info(f"Liquidity added for position with ID {token_id}.")
                        self.trigger_event(
                            MarketEvent.RangePositionLiquidityAdded,
                            RangePositionLiquidityAddedEvent(
                                timestamp=self.current_timestamp,
                                order_id=tracked_order.client_order_id,
                                exchange_order_id=tracked_order.exchange_order_id,
                                trading_pair=tracked_order.trading_pair,
                                lower_price=Decimal(str(tracked_order.lower_price)),
                                upper_price=Decimal(str(tracked_order.upper_price)),
                                amount=Decimal(str(tracked_order.amount)),
                                fee_tier=tracked_order.fee_tier,
                                creation_timestamp=tracked_order.creation_timestamp,
                                trade_fee=AddedToCostTradeFee(
                                    flat_fees=[TokenAmount(tracked_order.fee_asset, Decimal(str(fee)))]
                                ),
                                token_id=token_id,
                            )
                        )

                        if not self.token_id_exists(token_id):
                            tracked_order.current_state = OrderState.CREATED
                            tracked_order.token_id = token_id
                            continue

                        tracked_order.current_state = OrderState.COMPLETED
                    else:
                        reduce_evt = list(filter(lambda evt: evt["name"] == "tokenId", list(filter(lambda log: log["name"] == "DecreaseLiquidity", update_result["txReceipt"]["logs"]))[0]["events"])) if tracked_order.lp_type == LPType.REMOVE else []
                        collect_evt = list(filter(lambda evt: evt["name"] == "tokenId", list(filter(lambda log: log["name"] == "Collect", update_result["txReceipt"]["logs"]))[0]["events"]))
                        if len(reduce_evt) > 0:
                            token_id = int(reduce_evt[0]["value"])
                            tracked_order.token_id = token_id
                            self.logger().info(f"Liquidity removed for position with ID {token_id}.")
                            self.trigger_event(
                                MarketEvent.RangePositionLiquidityRemoved,
                                RangePositionLiquidityRemovedEvent(
                                    timestamp=self.current_timestamp,
                                    order_id=tracked_order.client_order_id,
                                    exchange_order_id=tracked_order.exchange_order_id,
                                    trading_pair=tracked_order.trading_pair,
                                    creation_timestamp=tracked_order.creation_timestamp,
                                    token_id=token_id,
                                    trade_fee=AddedToCostTradeFee(
                                        flat_fees=[TokenAmount(tracked_order.fee_asset, Decimal(str(fee)))]
                                    ),
                                )
                            )
                        if len(collect_evt) > 0:
                            token_id = int(collect_evt[0]["value"])
                            tracked_order.token_id = token_id
                            self.logger().info(f"Unclaimed fees collected for position with ID {token_id}.")
                            self.trigger_event(
                                MarketEvent.RangePositionFeeCollected,
                                RangePositionFeeCollectedEvent(
                                    timestamp=self.current_timestamp,
                                    order_id=tracked_order.client_order_id,
                                    exchange_order_id=tracked_order.exchange_order_id,
                                    trading_pair=tracked_order.trading_pair,
                                    token_id=token_id,
                                    creation_timestamp=tracked_order.creation_timestamp,
                                    trade_fee=AddedToCostTradeFee(
                                        flat_fees=[TokenAmount(tracked_order.fee_asset, Decimal(str(fee)))]
                                    ),
                                )
                            )
                        tracked_order.current_state = OrderState.COMPLETED
                else:
                    self.logger().info(
                        f"The LP update order {tracked_order.client_order_id} has failed according to order status API. ")
                    self.trigger_event(MarketEvent.RangePositionUpdateFailure,
                                       RangePositionUpdateFailureEvent(
                                           self.current_timestamp,
                                           tracked_order.client_order_id,
                                           tracked_order.lp_type
                                       ))
                self.stop_tracking_order(tracked_order.client_order_id)

    async def update_nft(self, tracked_orders: List[GatewayInFlightLPOrder]):
        """
        Calls REST API to get status update for each created in-flight tokens.
        """
        nft_orders: List[GatewayInFlightLPOrder] = [tracked_order for tracked_order in tracked_orders
                                                    if tracked_order.is_nft and tracked_order.token_id > 0]
        token_id_list: List[int] = [nft_order.token_id for nft_order in nft_orders]
        if len(nft_orders) < 1:
            return

        self.logger().debug(
            "Polling for nft updates for %d tokens.",
            len(nft_orders)
        )

        nft_update_results: List[Union[Dict[str, Any], Exception]] = await safe_gather(*[
            self._get_gateway_instance().amm_lp_position(
                self.chain,
                self.network,
                self.connector_name,
                token_id,
            )
            for token_id in token_id_list
        ], return_exceptions=True)

        for nft_order, nft_update_result in zip(nft_orders, nft_update_results):
            if isinstance(nft_update_result, Exception):
                raise nft_update_result
            lower_price = Decimal(nft_update_result["lowerPrice"])
            upper_price = Decimal(nft_update_result["upperPrice"])
            amount_0 = Decimal(nft_update_result["amount0"])
            amount_1 = Decimal(nft_update_result["amount1"])
            unclaimed_fee_0 = Decimal(nft_update_result["unclaimedToken0"])
            unclaimed_fee_1 = Decimal(nft_update_result["unclaimedToken1"])
            fee_tier = nft_update_result["fee"]
            if amount_0 + amount_1 + unclaimed_fee_0 + unclaimed_fee_1 == s_decimal_0:  # position closed, stop tracking
                self.logger().info(f"Position with ID {nft_order.token_id} closed. About to stop tracking...")
                nft_order.current_state = OrderState.COMPLETED
                self.stop_tracking_order(nft_order.client_order_id)
                self.trigger_event(
                    MarketEvent.RangePositionClosed,
                    RangePositionClosedEvent(
                        timestamp=self.current_timestamp,
                        token_id=nft_order.token_id,
                        token_0=nft_update_result["token0"],
                        token_1=nft_update_result["token1"],
                        claimed_fee_0=unclaimed_fee_0,
                        claimed_fee_1=unclaimed_fee_1,
                    )
                )
            else:
                nft_order.adjusted_lower_price = lower_price
                nft_order.adjusted_upper_price = upper_price
                if nft_order.trading_pair.split("-")[0] != nft_update_result["token0"]:
                    nft_order.adjusted_lower_price = Decimal("1") / upper_price
                    nft_order.adjusted_upper_price = Decimal("1") / lower_price
                    unclaimed_fee_0, unclaimed_fee_1 = unclaimed_fee_1, unclaimed_fee_0
                    amount_0, amount_1 = amount_1, amount_0
                nft_order.amount_0 = amount_0
                nft_order.amount_1 = amount_1
                nft_order.unclaimed_fee_0 = unclaimed_fee_0
                nft_order.unclaimed_fee_1 = unclaimed_fee_1
                nft_order.fee_tier = fee_tier

    def token_id_exists(self, token_id: int) -> bool:
        """
        Checks if there are existing tracked inflight orders with same token id created earlier.
        """
        token_id_list = [order for order in self.amm_lp_orders if order.token_id == token_id and order.is_nft]
        return len(token_id_list) > 0

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("1e-15")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        base, quote = trading_pair.split("-")
        return max(self._amount_quantum_dict[base], self._amount_quantum_dict[quote])

    @property
    def ready(self):
        return all(self.status_dict.values())

    def has_allowances(self) -> bool:
        """
        Checks if all tokens have allowance (an amount approved)
        """
        return ((len(self._allowances.values()) == len(self._tokens) * len(self._all_spenders)) and
                (all(amount > s_decimal_0 for amount in self._allowances.values())))

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "allowances": self.has_allowances() if self._trading_required else True,
            "native_currency": self._native_currency is not None,
            "network_transaction_fee": self.network_transaction_fee is not None if self._trading_required else True,
        }

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._auto_approve_task = safe_ensure_future(self.auto_approve())
            self._get_gas_estimate_task = safe_ensure_future(self.get_gas_estimate())
        self._get_chain_info_task = safe_ensure_future(self.get_chain_info())

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._auto_approve_task is not None:
            self._auto_approve_task.cancel()
            self._auto_approve_task = None
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
                    self.update_order_status(self.amm_lp_orders),
                    self.update_nft(self.amm_lp_orders)
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)

    async def update_balances(self, on_interval=False):
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
            resp_json: Dict[str, Any] = await self._get_gateway_instance().get_balances(
                self.chain, self.network, self.address, list(self._tokens) + [self._native_currency] + connector_tokens
            )
            for token, bal in resp_json["balances"].items():
                self._account_available_balances[token] = Decimal(str(bal))
                self._account_balances[token] = Decimal(str(bal))
                remote_asset_names.add(token)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

            self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
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
            tracked_order: GatewayInFlightLPOrder = self._in_flight_orders.get(order_id)
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
                               "expired. Canceling the order...")
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

            tracked_order.current_state = OrderState.PENDING_CANCEL
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
        incomplete_orders: List[GatewayInFlightLPOrder] = [
            o for o in self._in_flight_orders.values()
            if not (o.is_done or o.is_pending_cancel_confirmation)
        ]
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

    @property
    def in_flight_orders(self) -> Dict[str, GatewayInFlightLPOrder]:
        return self._in_flight_orders

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        *required
        Updates inflight order statuses from API results
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        self._in_flight_orders.update({
            key: GatewayInFlightLPOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {key: value.to_json() for key, value in self._in_flight_orders.items()}

    def _get_gateway_instance(self) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        return gateway_instance
