import asyncio
import copy
import itertools as it
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Type, Union, cast

from async_timeout import timeout

import hummingbot.connector.gateway.clob.clob_constants as constant
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.gateway.clob.clob_types import Chain
from hummingbot.connector.gateway.clob.clob_utils import (
    convert_order_side,
    convert_order_type,
    convert_trading_pair,
    convert_trading_pairs,
)
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_price_shim import GatewayPriceShim
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
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
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

ZERO = Decimal("0")
INFINITY = Decimal("Infinity")
NaN = Decimal("nan")


class GatewayCLOB(ExchangePyBase):
    """
    Defines basic functions common to connectors that interact with the Gateway.
    """

    _logger: HummingbotLogger

    _chain: str
    _network: str
    _connector: str
    _name: str
    _trading_pairs: List[str]
    _tokens: Set[str]
    _address: str
    _is_trading_required: bool
    _event_loop: asyncio.AbstractEventLoop
    _last_poll_timestamp: float
    _last_balance_poll_timestamp: float
    _last_estimated_gas_cost_reported: float
    _in_flight_orders: Dict[str, GatewayInFlightOrder]
    _allowances: Dict[str, Decimal]
    _markets: Dict[str, Any]
    _chain_information: Dict[str, Any]
    _status_polling_task: Optional[asyncio.Task]
    _get_chain_information_task: Optional[asyncio.Task]
    _get_markets_task: Optional[asyncio.Task]
    _auto_approve_task: Optional[asyncio.Task]
    _poll_notifier: Optional[asyncio.Event]
    _native_currency: str

    def __init__(
        self,
        connector: str,
        chain: str,
        network: str,
        wallet_address: str,
        trading_pairs: List[str] = (),
        is_trading_required: bool = True
    ):
        """
        :param trading_pairs: a list of trading pairs
        :param is_trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        super().__init__()

        self._chain = chain
        self._network = network
        self._connector = connector
        self._address = wallet_address
        self._trading_pairs = trading_pairs
        self._is_trading_required = is_trading_required

        self._name = "_".join([self.chain, self.network, self.connector])
        self._tokens = set()
        [self._tokens.update(set(trading_pair.split("-"))) for trading_pair in trading_pairs]
        self._address = wallet_address
        self._trading_required = is_trading_required
        self._event_loop = asyncio.get_event_loop()
        self._last_poll_timestamp = 0.0
        self._last_balance_poll_timestamp = time.time()
        self._in_flight_orders = {}
        self._allowances = {}
        self._chain_information = {}
        self._markets = {}
        self._status_polling_task = None
        self._get_chain_information_task = None
        self._get_markets_task = None
        self._auto_approve_task = None
        self._get_gas_estimate_task = None
        self._poll_notifier = None
        # self._native_currency = None
        self._network_transaction_fee: Optional[TokenAmount] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            logging.basicConfig(level=METRICS_LOG_LEVEL)
            cls._logger = cast(HummingbotLogger, logging.getLogger(cls.__name__))

        return cls._logger

    @property
    def chain(self):
        return self._chain

    @property
    def network(self):
        return self._network

    @property
    def connector(self):
        return self._connector

    @property
    def name(self):
        return self._name

    @property
    def address(self):
        return self._address

    # Added for compatibility
    @property
    def connector_name(self):
        return self.connector

    @staticmethod
    async def all_trading_pairs(chain: str, network: str) -> List[str]:
        """
        Calls the token's endpoint on the Gateway.
        """
        try:
            tokens = await GatewayHttpClient.get_instance().get_tokens(chain, network)
            token_symbols = [token["symbol"] for token in tokens["tokens"]]
            trading_pairs = []
            for base, quote in it.permutations(token_symbols, 2):
                trading_pairs.append(f"{base}-{quote}")

            return trading_pairs
        except (Exception,):
            GatewayCLOB.logger().warning(f"""No trading paris found for {chain}/{network}.""")

            return []

    @staticmethod
    def is_order(in_flight_order: GatewayInFlightOrder) -> bool:
        return in_flight_order.client_order_id.split("-")[0] in {"buy", "sell"}

    # Added for compatibility
    @staticmethod
    def is_amm_order(in_flight_order: GatewayInFlightOrder) -> bool:
        return GatewayCLOB.is_order(in_flight_order)

    @staticmethod
    def is_approval_order(in_flight_order: GatewayInFlightOrder) -> bool:
        return in_flight_order.client_order_id.split("-")[0] == "approve"

    @property
    def approval_orders(self) -> List[GatewayInFlightOrder]:
        return [
            approval_order
            for approval_order in self._in_flight_orders.values()
            if self.is_approval_order(approval_order)
            and not approval_order.is_cancelling
        ]

    @property
    def orders(self) -> List[GatewayInFlightOrder]:
        return [
            in_flight_order
            for in_flight_order in self._in_flight_orders.values()
            if self.is_order(in_flight_order)
            and not in_flight_order.is_cancelling
        ]

    # Added for compatibility
    @property
    def amm_orders(self) -> List[GatewayInFlightOrder]:
        return self.orders

    @property
    def canceling_orders(self) -> List[GatewayInFlightOrder]:
        return [
            cancel_order
            for cancel_order in self._in_flight_orders.values()
            if cancel_order.is_cancelling
        ]

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self.orders
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

    def create_approval_order_id(self, token_symbol: str) -> str:
        return f"approve-{self.connector}-{token_symbol}"

    @staticmethod
    def get_token_symbol_from_approval_order_id(approval_order_id: str) -> Optional[str]:
        match = constant.APPROVAL_ORDER_ID_PATTERN.search(approval_order_id)
        if match:
            return match.group(2)

        return None

    @staticmethod
    def create_market_order_id(side: TradeType, trading_pair: str) -> str:
        return f"{side.name.lower()}-{trading_pair}-{get_tracking_nonce()}"

    def is_pending_approval(self, token: str) -> bool:
        pending_approval_tokens: List[Optional[str]] = [
            self.get_token_symbol_from_approval_order_id(order_id)
            for order_id in self._in_flight_orders.keys()
        ]

        return True if token in pending_approval_tokens else False

    async def get_chain_info(self):
        """
        Calls the base endpoint of the connector on Gateway to know basic info about chain being used.
        """
        try:
            self._chain_information = await GatewayHttpClient.get_instance().get_network_status(
                chain=self.chain, network=self.network
            )
            if type(self._chain_information) != list:
                if self.chain == Chain.SOLANA.chain:
                    self._native_currency = self._chain_information.get("nativeCurrency", Chain.SOLANA.native_currency)
                else:
                    self._native_currency = self._chain_information.get("nativeCurrency", Chain.ETHEREUM.native_currency)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"""Error fetching chain information from {self.chain}/{self.network}.""",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_markets(self):
        try:
            self._markets = await GatewayHttpClient.get_instance().clob_get_markets(
                chain=self.chain,
                network=self.network,
                connector=self.connector,
                names=convert_trading_pairs(self._trading_pairs)
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"""Error fetching markets information from {self.chain}/{self.network}/{self.connector}.""",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_gas_estimate(self):
        """
        Gets the gas estimates for the connector.
        """
        self.network_transaction_fee = TokenAmount(Chain.SOLANA.native_currency, constant.FIVE_THOUSAND_LAMPORTS)

    async def auto_approve(self):
        """
        Automatically approves trading pair tokens for contract(s).
        It first checks if there are any already approved amount (allowance)
        """
        await self.update_allowances()
        for token, amount in self._allowances.items():
            if amount <= ZERO and not self.is_pending_approval(token):
                await self.approve_token(token)

    async def approve_token(self, token_symbol: str, **request_args) -> Optional[GatewayInFlightOrder]:
        """
        Approves contract as a spender for a token.
        :param token_symbol: token to approve.
        """
        order_id: str = self.create_approval_order_id(token_symbol)
        if self.chain == "solana":
            resp: Dict[str, Any] = await GatewayHttpClient.get_instance().solana_post_token(
                self.network,
                self.address,
                token_symbol
            )
        else:
            resp: Dict[str, Any] = await GatewayHttpClient.get_instance().approve_token(
                self.chain,
                self.network,
                self.address,
                token_symbol,
                self.connector,
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
                f"""Maximum {token_symbol} approval for {self.chain}/{self.network}/{self.connector} contract sent, hash: {hash}."""
            )

            return tracked_order
        else:
            self.logger().info(f"""Missing data from approval result. Incomplete return result for ({resp.keys()})""")
            self.logger().info(f"""Approval for {token_symbol} on {self.chain}/{self.network}/{self.connector} failed.""")

            return None

    async def update_allowances(self):
        self._allowances = await self.get_allowances()

    async def get_allowances(self) -> Dict[str, Decimal]:
        """
        Retrieves allowances for token in trading_pairs
        :return: A dictionary of token and its allowance.
        """
        ret_val = {}
        resp: Dict[str, Any] = await GatewayHttpClient.get_instance().solana_post_balances(
            self.network, self.address, list(self._tokens)
        )
        for token, amount in resp.items():
            if amount is None:
                ret_val[token] = ZERO
            else:
                ret_val[token] = Decimal(str(INFINITY))

        return ret_val

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

        base, quote = trading_pair.split("-")
        side: TradeType = TradeType.BUY if is_buy else TradeType.SELL

        # Get the price from gateway price shim for integration tests.
        if not ignore_shim:
            test_price: Optional[Decimal] = await GatewayPriceShim.get_instance().get_connector_price(
                self.connector,
                self.chain,
                self.network,
                trading_pair,
                is_buy,
                amount
            )
            if test_price is not None:
                # Grab the gas price for testnet.
                self.network_transaction_fee = TokenAmount(Chain.SOLANA.native_currency, constant.FIVE_THOUSAND_LAMPORTS)

        # Pull the price from gateway.
        try:
            ticker = await GatewayHttpClient.get_instance().clob_get_tickers(
                self.chain, self.network, self.connector, market_name=constant.SOL_USDC_MARKET
            )
            gas_limit: int = constant.FIVE_THOUSAND_LAMPORTS
            gas_price_token: str = Chain.SOLANA.native_currency
            gas_cost: Decimal = constant.FIVE_THOUSAND_LAMPORTS
            price: Decimal = Decimal(ticker["price"])
            self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)
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
                swaps_count=constant.ZERO
            )
            for index in range(len(exceptions)):
                self.logger().warning(
                    f"Warning! [{index + 1}/{len(exceptions)}] {side} order - {exceptions[index]}"
                )

            if price is not None and len(exceptions) == 0:
                return Decimal(str(price))

            # Didn't pass all the checks - no price available.
            return None
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

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal) -> str:
        """
        Buys an amount of base token for a given price (or cheaper).
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param order_type: Any order type is fine, not needed for this.
        :param price: The maximum price for the order.
        :return: A newly created order id (internal).
        """
        return self.place_order(True, trading_pair, amount, price)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal) -> str:
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

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        base, quote = trading_pair.split("-")
        self.start_tracking_order(
            order_id=order_id,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=price,
            amount=amount
        )
        try:
            order_result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_post_orders(
                self.chain,
                self.network,
                self.connector,
                order={
                    "id": order_id,
                    "marketName": f"{base}/{quote}",
                    "ownerAddress": self.address,
                    "payerAddress": self.address,
                    "side": convert_order_side(trade_type),
                    "price": price,
                    "amount": amount,
                    "type": convert_order_type(OrderType.LIMIT)
                }
            )
            transaction_hash: str = order_result.get("signature")
            nonce: int = constant.DEFAULT_NONCE
            await self._update_nonce(nonce)

            tracked_order: GatewayInFlightOrder = self._in_flight_orders.get(order_id)

            ticker = await GatewayHttpClient.get_instance().clob_get_tickers(
                self.chain, self.network, self.connector, market_name=constant.SOL_USDC_MARKET
            )

            gas_price: Decimal = constant.ONE
            gas_limit: int = constant.FIVE_THOUSAND_LAMPORTS
            gas_price_token: str = Chain.SOLANA.native_currency
            gas_cost: Decimal = constant.FIVE_THOUSAND_LAMPORTS
            price: Decimal = Decimal(ticker["price"])

            self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)

            if tracked_order is not None:
                self.logger().info(f"Created {trade_type.name} order {order_id} txHash: {transaction_hash} "
                                   f"for {amount} {trading_pair} using {self.chain}/{self.network}/{self.connector}. Estimated Gas Cost: {gas_cost} "
                                   f" (gas limit: {gas_limit}, gas price: {gas_price})")
                tracked_order.update_exchange_order_id(transaction_hash)
                tracked_order.gas_price = gas_price
                tracked_order.last_state = "OPEN"
            if transaction_hash is not None:
                tracked_order.nonce = nonce
                tracked_order.fee_asset = self._native_currency
                tracked_order.executed_amount_base = amount
                tracked_order.executed_amount_quote = amount * price
                event_tag: MarketEvent = (
                    MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY
                    else MarketEvent.SellOrderCreated
                )
                event_class: Union[Type[BuyOrderCreatedEvent], Type[SellOrderCreatedEvent]] = (
                    BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
                )
                self.trigger_event(event_tag, event_class(
                    timestamp=self.current_timestamp,
                    type=OrderType.LIMIT,
                    trading_pair=trading_pair,
                    amount=amount,
                    price=price,
                    order_id=order_id,
                    creation_timestamp=tracked_order.creation_timestamp,
                    exchange_order_id=transaction_hash
                ))
            else:
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))
                self.stop_tracking_order(order_id)
        except asyncio.CancelledError:
            raise
        except (Exception,):
            self.stop_tracking_order(order_id)
            self.logger().error(
                f"Error submitting {trade_type.name} swap order to {self.chain}/{self.network}/{self.connector} for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True
            )
            self.trigger_event(
                MarketEvent.OrderFailure,
                MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT)
            )

    def start_tracking_order(
        self,
        order_id: str,
        exchange_order_id: Optional[str] = None,
        trading_pair: str = "",
        trade_type: TradeType = TradeType.BUY,
        price: Decimal = ZERO,
        amount: Decimal = ZERO,
        gas_price: Decimal = ZERO
    ):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = GatewayInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=trade_type,
            price=price,
            amount=amount,
            gas_price=gas_price,
            creation_timestamp=self.current_timestamp
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

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
            GatewayHttpClient.get_instance().get_transaction_status(
                self.chain,
                self.network,
                tx_hash
            )
            for tx_hash in tx_hash_list
        ], return_exceptions=True)
        for tracked_approval, transaction_status in zip(tracked_approvals, transaction_states):
            token_symbol: str = self.get_token_symbol_from_approval_order_id(tracked_approval.client_order_id)
            if isinstance(transaction_status, Exception):
                self.logger().error(f"Error while trying to approve token {token_symbol} for {self.chain}/{self.network}/{self.connector}: "
                                    f"{transaction_status}")
                continue
            if "txHash" not in transaction_status:
                self.logger().error(f"Error while trying to approve token {token_symbol} for {self.chain}/{self.network}/{self.connector}: "
                                    "txHash key not found in transaction status.")
                continue
            if transaction_status["txStatus"] == 1:
                if transaction_status["txReceipt"]["status"] == 1:
                    self.logger().info(f"Token approval for {tracked_approval.client_order_id} on {self.chain}/{self.network}/{self.connector} "
                                       f"successful.")
                    self.trigger_event(
                        TokenApprovalEvent.ApprovalSuccessful,
                        TokenApprovalSuccessEvent(
                            self.current_timestamp,
                            self.connector,
                            token_symbol
                        )
                    )
                    safe_ensure_future(self.update_allowances())
                else:
                    self.logger().warning(
                        f"Token approval for {tracked_approval.client_order_id} on {self.chain}/{self.network}/{self.connector} failed."
                    )
                    self.trigger_event(
                        TokenApprovalEvent.ApprovalFailed,
                        TokenApprovalFailureEvent(
                            self.current_timestamp,
                            self.connector,
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
            GatewayHttpClient.get_instance().get_transaction_status(
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
                    if tracked_order.last_state == "CANCELING":
                        if self.is_order(tracked_order):
                            self.trigger_event(
                                MarketEvent.OrderCancelled,
                                OrderCancelledEvent(
                                    self.current_timestamp,
                                    tracked_order.client_order_id,
                                    tracked_order.exchange_order_id,
                                )
                            )
                            self.logger().info(f"The {tracked_order.trade_type.name} order "
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
                                    self.connector,
                                    token_symbol
                                )
                            )
                            self.logger().info(f"Token approval for {tracked_order.client_order_id} on "
                                               f"{self.chain}/{self.network}/{self.connector} has been canceled.")
                        tracked_order.last_state = "CANCELED"
                    self.stop_tracking_order(tracked_order.client_order_id)

    async def update_order_status(self, tracked_orders: List[GatewayInFlightOrder]):
        """
        Calls REST API to get status update for each in-flight orders.
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
            GatewayHttpClient.get_instance().get_transaction_status(
                self.chain,
                self.network,
                tx_hash
            )
            for tx_hash in tx_hash_list
        ], return_exceptions=True)
        for tracked_order, update_result in zip(tracked_orders, update_results):
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
                    self.trigger_event(
                        MarketEvent.OrderFilled,
                        OrderFilledEvent(
                            self.current_timestamp,
                            tracked_order.client_order_id,
                            tracked_order.trading_pair,
                            tracked_order.trade_type,
                            tracked_order.order_type,
                            Decimal(str(tracked_order.price)),
                            Decimal(str(tracked_order.amount)),
                            AddedToCostTradeFee(
                                flat_fees=[TokenAmount(tracked_order.fee_asset, Decimal(str(fee)))]
                            ),
                            exchange_trade_id=tracked_order.exchange_order_id
                        )
                    )
                    tracked_order.last_state = "FILLED"
                    event_tag: MarketEvent = (
                        MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY
                        else MarketEvent.SellOrderCompleted
                    )
                    event_class: Union[Type[BuyOrderCompletedEvent], Type[SellOrderCompletedEvent]] = (
                        BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY
                        else SellOrderCompletedEvent
                    )
                    self.trigger_event(
                        event_tag,
                        event_class(
                            timestamp=self.current_timestamp,
                            order_id=tracked_order.client_order_id,
                            base_asset=tracked_order.base_asset,
                            quote_asset=tracked_order.quote_asset,
                            base_asset_amount=tracked_order.executed_amount_base,
                            quote_asset_amount=tracked_order.executed_amount_quote,
                            order_type=tracked_order.order_type,
                            exchange_order_id=tracked_order.exchange_order_id
                        )
                    )
                else:
                    self.logger().info(
                        f"The market order {tracked_order.client_order_id} has failed according to order status API. ")
                    self.trigger_event(
                        MarketEvent.OrderFailure,
                        MarketOrderFailureEvent(
                            self.current_timestamp,
                            tracked_order.client_order_id,
                            tracked_order.order_type
                        )
                    )
                self.stop_tracking_order(tracked_order.client_order_id)

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal((await GatewayHttpClient.get_instance().clob_get_markets(
            self.chain, self.network, self.connector, name=convert_trading_pair(trading_pair)
        ))['tickSize'])

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return Decimal((await GatewayHttpClient.get_instance().clob_get_markets(
            self.chain, self.network, self.connector, name=convert_trading_pair(trading_pair)
        ))['minimumOrderSize'])

    @property
    def ready(self):
        return all(self.status_dict.values())

    def has_allowances(self) -> bool:
        """
        Checks if all tokens have allowance (an amount approved)
        """
        return ((len(self._allowances.values()) == len(self._tokens)) and
                (all(amount > ZERO for amount in self._allowances.values())))

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._is_trading_required else True,
            "allowances": self.has_allowances() if self._is_trading_required else True,
            "native_currency": self._native_currency is not None,
            "network_transaction_fee": self.network_transaction_fee is not None if self._is_trading_required else True,
            "markets": self._markets is not None,
        }

    async def start_network(self):
        if self._is_trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._auto_approve_task = safe_ensure_future(self.auto_approve())
            self._get_gas_estimate_task = safe_ensure_future(self.get_gas_estimate())
        self._get_chain_information_task = safe_ensure_future(self.get_chain_info())
        self._get_markets_task = safe_ensure_future(self.get_markets())

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._auto_approve_task is not None:
            self._auto_approve_task.cancel()
            self._auto_approve_task = None
        if self._get_chain_information_task is not None:
            self._get_chain_information_task.cancel()
            self._get_chain_information_task = None
        if self._get_gas_estimate_task is not None:
            self._get_gas_estimate_task.cancel()
            self._get_chain_information_task = None
        if self._get_markets_task is not None:
            self._get_markets_task.cancel()
            self._get_markets_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            if await GatewayHttpClient.get_instance().ping_gateway():
                return NetworkStatus.CONNECTED
        except asyncio.CancelledError:
            raise
        except (Exception,):
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.NOT_CONNECTED

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        if time.time() - self._last_poll_timestamp > constant.POLL_INTERVAL:
            if self._poll_notifier is not None and not self._poll_notifier.is_set():
                self._poll_notifier.set()

    async def _update_nonce(self, new_nonce: Optional[int] = None):
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

    async def update_balances(self, on_interval=False):
        """
        Calls Eth API to update total and available balances.
        """
        if self._native_currency is None:
            await self.get_chain_info()
        last_tick = self._last_balance_poll_timestamp
        current_tick = self.current_timestamp
        if not on_interval or (current_tick - last_tick) > constant.UPDATE_BALANCE_INTERVAL:
            self._last_balance_poll_timestamp = current_tick
            local_asset_names = set(self._account_balances.keys())
            remote_asset_names = set()
            resp_json: Dict[str, Any] = await GatewayHttpClient.get_instance().get_balances(
                self.chain, self.network, self.address, list(self._tokens) + [self._native_currency]
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
        This is intentionally not awaited because cancellation is expensive on blockchains. It's not worth it for
        Hummingbot to force cancel all orders whenever Hummingbot quits.
        """
        # noinspection PyAsyncCall
        GatewayHttpClient.get_instance().clob_delete_orders(
            self.chain, self.network, self.address
        )

        return []

    async def _execute_cancel(self, order_id: str, cancel_age: int) -> Optional[str]:
        """
        Cancel an existing order if the age of the order is greater than its cancel_age,
        and if the order is not done or already in the cancelling state.
        """
        try:
            tracked_order: GatewayInFlightOrder = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                self.logger().error(f"The order {order_id} is not being tracked.")
                raise ValueError(f"The order {order_id} is not being tracked.")

            if (self.current_timestamp - tracked_order.creation_timestamp) < cancel_age:
                return None

            if tracked_order.is_done:
                return None

            if tracked_order.is_cancelling:
                return order_id

            self.logger().info(f"The blockchain transaction for {order_id} with nonce {tracked_order.nonce} has "
                               f"expired. Canceling the order...")
            resp: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_delete_orders(
                self.chain,
                self.network,
                self.connector,
                self.address,
                order={
                    "id": order_id,
                    "marketName": convert_trading_pair(tracked_order.trading_pair),
                    "ownerAddress": self.address,
                }
            )

            tx_hash: Optional[str] = resp.get("signature")
            if tx_hash is not None:
                tracked_order.cancel_tx_hash = tx_hash
            else:
                raise EnvironmentError(f"Missing txHash from the transaction response: {resp}.")

            tracked_order.last_state = "CANCELING"
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
        incomplete_orders: List[GatewayInFlightOrder] = [
            o for o in self._in_flight_orders.values()
            if not (o.is_done or o.is_cancelling)
        ]
        if len(incomplete_orders) < 1:
            return []

        timeout_seconds: float = 30.0
        canceling_id_set: Set[str] = set([o.client_order_id for o in incomplete_orders])
        sent_cancellations: List[CancellationResult] = []

        try:
            async with timeout(timeout_seconds):
                # XXX (martin_kou): We CANNOT perform parallel transactions before the nonce architecture is fixed.
                # See: https://app.shortcut.com/coinalpha/story/24553/nonce-architecture-in-current-amm-trade-and-evm-approve-apis-is-incorrect-and-causes-trouble-with-concurrent-requests
                for incomplete_order in incomplete_orders:
                    try:
                        canceling_order_id: Optional[str] = await self._execute_cancel(
                            incomplete_order.client_order_id,
                            cancel_age
                        )
                    except (Exception,):
                        continue
                    if canceling_order_id is not None:
                        canceling_id_set.remove(canceling_order_id)
                        sent_cancellations.append(CancellationResult(canceling_order_id, True))
        except asyncio.CancelledError:
            raise
        except (Exception,):
            self.logger().network(
                "Unexpected error cancelling outdated orders.",
                exc_info=True,
                app_warning_msg=f"Failed to cancel orders on {self.chain}/{self.network}/{self.connector}."
            )

        skipped_cancellations: List[CancellationResult] = [CancellationResult(oid, False) for oid in canceling_id_set]
        return sent_cancellations + skipped_cancellations

    @property
    def in_flight_orders(self) -> Dict[str, GatewayInFlightOrder]:
        return self._in_flight_orders
