import asyncio
import copy
import logging
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union, cast

from async_timeout import timeout

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.clob import clob_constants as constant
from hummingbot.connector.gateway.clob.clob_in_flight_order import CLOBInFlightOrder
from hummingbot.connector.gateway.clob.clob_utils import (
    convert_order_side,
    convert_order_type,
    convert_trading_pair,
    convert_trading_pairs,
)
from hummingbot.connector.gateway.common_types import Chain
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


# TODO remove references to the EVM AMM strategy and class.
class GatewaySOLCLOB(ConnectorBase):
    """
    Defines basic functions common to connectors that interact with the Gateway.
    """

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
    _allowances: Dict[str, Decimal]
    _chain_info: Dict[str, Any]
    _status_polling_task: Optional[asyncio.Task]
    _get_chain_info_task: Optional[asyncio.Task]
    _auto_approve_task: Optional[asyncio.Task]
    _poll_notifier: Optional[asyncio.Event]
    _native_currency: Optional[str]

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            connector_name: str,
            chain: str,
            network: str,
            wallet_address: str,
            trading_pairs: List[str] = (),
            additional_spenders: List[str] = [],  # not implemented
            trading_required: bool = True
    ):
        """
        :param connector_name: name of connector on gateway :param chain: refers to a blockchain, e.g. ethereum or
        avalanche :param network: refers to a network of a particular blockchain e.g. mainnet or kovan :param
        wallet_address: the address of the eth wallet which has been added on gateway :param trading_pairs: a list of
        trading pairs :param trading_required: Whether actual trading is needed. Useful for some functionalities or
            commands like the balance command
        """
        self._client_config = None
        self._connector_name = connector_name
        self._name = "_".join([connector_name, chain, network])
        super().__init__(client_config_map)
        self._chain = chain
        self._network = network
        self._trading_pairs = trading_pairs
        self._tokens = set()
        [self._tokens.update(set(trading_pair.split("-"))) for trading_pair in trading_pairs]
        self._wallet_address = wallet_address
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._last_poll_timestamp = 0.0
        self._last_balance_poll_timestamp = time.time()
        self._last_est_gas_cost_reported = 0
        self._allowances = {}
        self._chain_info = {}
        self._status_polling_task = None
        self._get_chain_info_task = None
        self._auto_approve_task = None
        self._poll_notifier = None
        self._native_currency = None
        self._network_transaction_fee: Optional[TokenAmount] = TokenAmount('SOL', constant.FIVE_THOUSAND_LAMPORTS)
        self._order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self)
        self._get_markets_task = None
        self._markets = None
        self._token_accounts = {}
        self._auto_create_token_accounts_task = None
        self._tokens_accounts_created: bool = False
        self._order_quantum = {}
        self._set_order_price_and_order_size_quantum = False
        self._set_order_price_and_order_size_quantum_task = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(cls.__name__)

        return cast(HummingbotLogger, s_logger)

    @property
    def chain(self):
        return self._chain

    @property
    def network(self):
        return self._network

    @property
    def connector(self):
        return self._connector_name

    @property
    def name(self):
        return self._name

    @property
    def address(self):
        return self._wallet_address

    # Added for compatibility
    @property
    def connector_name(self):
        return self._connector_name

    async def all_trading_pairs(self, chain: str, network: str) -> List[str]:
        # Since the solana tokens trading pairs would be too much, we are returning an empty list here.
        return []

        # """
        # Calls the token's endpoint on the Gateway.
        # """
        # try:
        #     tokens = await self._get_gateway_instance().get_tokens(chain, network)
        #     token_symbols = [token["symbol"] for token in tokens["tokens"]]
        #     trading_pairs = []
        #     for base, quote in it.permutations(token_symbols, 2):
        #         trading_pairs.append(f"{base}-{quote}")
        #
        #     return trading_pairs
        # except (Exception,):
        #     GatewaySOLCLOB.logger().warning(f"""No trading pairs found for {chain}/{network}.""")
        #
        #     return []

    @staticmethod
    def is_order(in_flight_order: CLOBInFlightOrder) -> bool:
        return in_flight_order.client_order_id.split("-")[0] in {"buy", "sell"}

    # Added for compatibility
    @staticmethod
    def is_amm_order(in_flight_order: CLOBInFlightOrder) -> bool:
        return GatewaySOLCLOB.is_order(in_flight_order)

    @staticmethod
    def is_approval_order(in_flight_order: CLOBInFlightOrder) -> bool:
        return in_flight_order.client_order_id.split("-")[0] == "approve"

    @property
    def approval_orders(self) -> List[CLOBInFlightOrder]:
        target_orders = [CLOBInFlightOrder.from_json(order.to_json()) for order in
                         self._order_tracker.active_orders.values()]

        return [
            approval_order
            for approval_order in target_orders
            if approval_order.is_approval_request
        ]

    @property
    def orders(self) -> List[CLOBInFlightOrder]:
        target_orders = [CLOBInFlightOrder.from_json(order.to_json()) for order in
                         self._order_tracker.active_orders.values()]

        return [
            in_flight_order
            for in_flight_order in target_orders
            if in_flight_order.is_open
        ]

    # Added for compatibility with the AMM ARB Strategy
    @property
    def amm_orders(self) -> List[CLOBInFlightOrder]:
        return self.orders

    @property
    def canceling_orders(self) -> List[CLOBInFlightOrder]:
        return [
            cancel_order
            for cancel_order in self.orders
            if cancel_order.is_pending_cancel_confirmation
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

    @property
    def in_flight_orders(self) -> Dict[str, CLOBInFlightOrder]:
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

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.
        :param saved_states: The saved tracking_states.
        """
        self._order_tracker.restore_tracking_states(tracking_states=saved_states)

    def create_approval_order_id(self, token_symbol: str) -> str:
        return f"approve-{self.connector_name}-{token_symbol}"

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
        for order in self.approval_orders:
            if token in order.client_order_id:
                return order.is_pending_approval
        return False

    async def get_chain_info(self):
        """
        Calls the base endpoint of the connector on Gateway to know basic info about chain being used.
        """
        try:
            self._chain_info = await self._get_gateway_instance().get_network_status(
                chain=self.chain, network=self.network
            )
            if type(self._chain_info) != list:
                self._native_currency = self._chain_info.get("nativeCurrency", Chain.SOLANA.native_currency)
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
            self._markets = await self._get_gateway_instance().clob_get_markets(
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

    async def set_order_price_and_order_size_quantum(self):
        for trading_pair in self._trading_pairs:
            market = await self._get_gateway_instance().clob_get_markets(
                self.chain, self.network, self.connector, name=convert_trading_pair(trading_pair)
            )

            self._order_quantum[trading_pair] = {
                'order_price': Decimal(market['tickSize']),
                'order_size': Decimal(market['minimumOrderSize'])
            }

        self._set_order_price_and_order_size_quantum = True

    async def auto_create_token_accounts(self):
        """Automatically creates all token accounts required for trading."""
        if self._trading_required is True:
            for token in self._tokens:
                self._token_accounts[token] = await self.get_or_create_token_account(token)

        self._tokens_accounts_created = True

    async def get_or_create_token_account(self, token: str) -> Union[Dict[str, Any], None]:
        response = await GatewayHttpClient.get_instance().solana_post_token(
            self.network,
            self.address,
            token
        )

        if response.get("accountAddress", None) is None:
            self.logger().warning(
                f"""Token account initialization failed """
                f"""(chain: {self.chain}, network: {self.network}, connector: {self.connector}, """
                f""" wallet: "{self.address}" token: "{token}")."""
            )

            return None
        else:
            self.logger().info(
                f"""Token account successfully initialized """
                f"""(chain: {self.chain}, network: {self.network}, connector: {self.connector}, """
                f"""wallet: "{self.address}" token: "{token}", mint_address: "{response['mintAddress']}")."""
            )

            return response

    async def auto_approve(self):
        """
        Automatically approves trading pair tokens for contract(s).
        It first checks if there are any already approved amount (allowance)
        """
        await self.update_allowances()
        for token, amount in self._allowances.items():
            if amount <= constant.DECIMAL_ZERO and not self.is_pending_approval(token):
                await self.approve_token(token)

    async def approve_token(self, token_symbol: str, **request_args) -> Optional[CLOBInFlightOrder]:
        """
        Approves contract as a spender for a token.
        :param token_symbol: token to approve.
        """
        approval_id: str = self.create_approval_order_id(token_symbol)

        self.logger().info(f"Initiating approval for {token_symbol}.")

        self.start_tracking_order(
            order_id=approval_id,
            trading_pair=token_symbol,
            is_approval=True
        )
        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().solana_post_token(
                self.network,
                self.address,
                token_symbol
            )

            mint_address: Optional[str] = resp.get("mintAddress")
            if mint_address is not None:
                tracked_order = self._order_tracker.fetch_order(client_order_id=approval_id)
                tracked_order.update_exchange_order_id(mint_address)
                self.logger().info(
                    f"Maximum {token_symbol} approval for {self.connector_name} contract sent,"
                    f" mint address: {mint_address}."
                )
                return tracked_order
            else:
                self.stop_tracking_order(approval_id)
                self.logger().info(f"Approval for {token_symbol} on {self.connector_name} failed.")
                return None
        except (Exception,):
            self.stop_tracking_order(approval_id)
            self.logger().error(
                f"Error submitting approval order for {token_symbol} on {self.connector_name}-{self.network}.",
                exc_info=True
            )
            return None

    async def update_allowances(self):
        self._allowances = await self.get_allowances()

    async def get_allowances(self) -> Dict[str, Decimal]:
        """
        Retrieves allowances for token in trading_pairs
        :return: A dictionary of token and its allowance.
        """
        ret_val = {}
        resp: Dict[str, Any] = await self._get_gateway_instance().solana_get_balances(
            self.network, self.address, list(self._tokens)
        )
        for token, amount in resp['balances'].items():
            if amount == '-1':
                ret_val[token] = constant.DECIMAL_ZERO
            else:
                ret_val[token] = Decimal(str(constant.DECIMAL_INFINITY))

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
                self.network_transaction_fee = TokenAmount(
                    Chain.SOLANA.native_currency,
                    constant.FIVE_THOUSAND_LAMPORTS
                )

        # Pull the price from gateway.
        try:
            ticker = await self._get_gateway_instance().clob_get_tickers(
                self.chain, self.network, self.connector, market_name=convert_trading_pair(trading_pair)
            )
            gas_limit: int = constant.FIVE_THOUSAND_LAMPORTS
            gas_price_token: str = Chain.SOLANA.native_currency
            gas_cost: Decimal = constant.FIVE_THOUSAND_LAMPORTS
            price = Decimal(ticker["price"])
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
                swaps_count=constant.DECIMAL_ZERO,
                chain=Chain.SOLANA,
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

    # noinspection PyUnusedLocal
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
            if trade_type == TradeType.SELL:
                payer_address = self.address
            elif trade_type == TradeType.BUY:
                payer_address = self._token_accounts[quote]['accountAddress']
            else:
                raise ValueError(f"Unknown trade type: {trade_type}")

            numeric_order_id = order_id.split('-')[3]

            order_result: Dict[str, Any] = await self._get_gateway_instance().clob_post_orders(
                self.chain,
                self.network,
                self.connector,
                order={
                    "id": numeric_order_id,
                    "marketName": f"{base}/{quote}",
                    "ownerAddress": self.address,
                    "payerAddress": payer_address,
                    "side": convert_order_side(trade_type).value[0],
                    "price": str(amount),
                    "amount": str(amount),
                    "type": convert_order_type(OrderType.LIMIT).value[0]
                }
            )
            signature: str = order_result.get("signature")

            if signature is not None:
                gas_cost = constant.FIVE_THOUSAND_LAMPORTS
                gas_price_token = Chain.SOLANA.native_currency
                gas_price: Decimal = constant.DECIMAL_ONE
                gas_limit: int = constant.FIVE_THOUSAND_LAMPORTS

                self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=order_id,
                    exchange_order_id=signature,  # The GatewayEVMAMM implementation uses the creation transaction hash here.
                    trading_pair=trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.OPEN,  # Assume that the transaction has been successfully mined.
                    misc_updates={
                        "gas_price": gas_price,
                        "gas_limit": gas_limit,
                        "gas_cost": gas_cost,
                        "gas_price_token": gas_price_token,
                        "fee_asset": self._native_currency,
                    }
                )
                self._order_tracker.process_order_update(order_update)
            else:
                raise ValueError
        except asyncio.CancelledError:
            raise
        except (Exception,):
            self.logger().error(
                f"Error submitting {trade_type.name} swap order on {self.chain}/{self.network}/{self.connector} for "
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

    def start_tracking_order(
            self,
            order_id: str,
            exchange_order_id: Optional[str] = None,
            trading_pair: str = "",
            trade_type: TradeType = TradeType.BUY,
            price: Decimal = constant.DECIMAL_ZERO,
            amount: Decimal = constant.DECIMAL_ZERO,
            gas_price: Decimal = constant.DECIMAL_ZERO,
            is_approval: bool = False
    ):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary in ClientOrderTracker.
        """
        self._order_tracker.start_tracking_order(
            CLOBInFlightOrder(
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

    async def update_token_approval_status(self, tracked_approvals: List[CLOBInFlightOrder]):
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
                self.logger().error(
                    f"Error while trying to approve token {token_symbol} for "
                    f"{self.chain}/{self.network}/{self.connector}: "
                    f"{transaction_status}")
                continue
            if "txHash" not in transaction_status:
                self.logger().error(
                    f"Error while trying to approve token {token_symbol} for "
                    f"{self.chain}/{self.network}/{self.connector}: "
                    "txHash key not found in transaction status.")
                continue
            if transaction_status["txStatus"] == 1:
                self.logger().info(f"Token approval for {tracked_approval.client_order_id} on"
                                   f"{self.connector_name} successful.")
                if transaction_status["txReceipt"]["status"] == 1:
                    tracked_approval.current_state = OrderState.APPROVED
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
                        f"Token approval for {tracked_approval.client_order_id} on "
                        f"{self.chain}/{self.network}/{self.connector} failed."
                    )
                    tracked_approval.current_state = OrderState.FAILED
                    self.trigger_event(
                        TokenApprovalEvent.ApprovalFailed,
                        TokenApprovalFailureEvent(
                            self.current_timestamp,
                            self.connector,
                            token_symbol
                        )
                    )
                self.stop_tracking_order(tracked_approval.client_order_id)

    async def update_canceling_transactions(self, canceled_tracked_orders: List[CLOBInFlightOrder]):
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
                            OrderUpdate(
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
                                    self.connector,
                                    token_symbol
                                )
                            )
                            self.logger().info(f"Token approval for {tracked_order.client_order_id} on "
                                               f"{self.chain}/{self.network}/{self.connector} has been canceled.")
                    self.stop_tracking_order(tracked_order.client_order_id)

    async def update_order_status(self, tracked_orders: List[CLOBInFlightOrder]):
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

                trade_fee: TradeFeeBase = AddedToCostTradeFee(
                    flat_fees=[TokenAmount(tracked_order.fee_asset, Decimal(str(fee)))]
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

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.FILLED,
                )
                self._order_tracker.process_order_update(order_update)
            elif tx_status in [-1, 2, 3, 0] or (tx_receipt is not None and tx_receipt.get("status") == 0):
                self.logger().network(
                    f"Error fetching transaction status for the order {tracked_order.client_order_id}: {tx_details}.",
                    app_warning_msg=f"Failed to fetch transaction status for the order {tracked_order.client_order_id}."
                )
                await self._order_tracker.process_order_not_found(tracked_order.client_order_id)

    @staticmethod
    def get_taker_order_type():
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return self._order_quantum[trading_pair]['order_price']

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return self._order_quantum[trading_pair]['order_price']

    @property
    def ready(self):
        return all(self.status_dict.values())

    def has_allowances(self) -> bool:
        """
        Checks if all tokens have allowance (an amount approved)
        """
        return ((len(self._allowances.values()) == len(self._tokens)) and
                (all(amount >= constant.DECIMAL_ZERO for amount in self._allowances.values())))

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "allowances": self.has_allowances() if self._trading_required else True,
            "native_currency": self._native_currency is not None,
            "network_transaction_fee": self.network_transaction_fee is not None if self._trading_required else True,
            "markets": self._markets is not None,
            "set_order_price_and_order_size_quantum": self._set_order_price_and_order_size_quantum,
            "tokens_accounts_created": self._tokens_accounts_created
        }

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._auto_approve_task = safe_ensure_future(self.auto_approve())
        self._get_chain_info_task = safe_ensure_future(self.get_chain_info())
        self._get_markets_task = safe_ensure_future(self.get_markets())
        self._set_order_price_and_order_size_quantum_task = safe_ensure_future(self.set_order_price_and_order_size_quantum())
        self._auto_create_token_accounts_task = safe_ensure_future(self.auto_create_token_accounts())

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
        if self._get_markets_task is not None:
            self._get_markets_task.cancel()
            self._get_markets_task = None
        if self._set_order_price_and_order_size_quantum_task is not None:
            self._set_order_price_and_order_size_quantum_task.cancel()
            self._set_order_price_and_order_size_quantum_task = None
        if self._auto_create_token_accounts_task is not None:
            self._auto_create_token_accounts_task.cancel()
            self._auto_create_token_accounts_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            if await self._get_gateway_instance().ping_gateway():
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
            resp_json: Dict[str, Any] = await self._get_gateway_instance().get_balances(
                self.chain, self.network, self.address, list(self._tokens)
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
        This is intentionally not awaited because cancellation is expensive on blockchains. It's not worth it for
        Hummingbot to force cancel all orders whenever Hummingbot quits.
        """
        asyncio.ensure_future(
            self._get_gateway_instance().clob_delete_orders(
                chain=self.chain,
                network=self.network,
                connector=self.connector,
                orders=[{
                    "marketName": convert_trading_pair(trading_pair),
                    "ownerAddress": self.address,
                } for trading_pair in self._trading_pairs]
            )
        )

        self.logger().warning(
            """Although a process to cancel all orders was dispatched, it is not guaranteed that it will work due """
            """to the nature of the blockchains. Those orders need to be checked manually."""
        )

        return []

    async def _execute_cancel(self, order_id: str, cancel_age: int) -> Optional[str]:
        """
        Cancel an existing order if the age of the order is greater than its cancel_age,
        and if the order is not done or already in the cancelling state.
        """
        try:
            tracked_order: CLOBInFlightOrder = self._order_tracker.fetch_order(client_order_id=order_id)
            if tracked_order is None:
                self.logger().error(f"The order {order_id} is not being tracked.")
                raise ValueError(f"The order {order_id} is not being tracked.")

            if (self.current_timestamp - tracked_order.creation_timestamp) < cancel_age:
                return None

            if tracked_order.is_done:
                return None

            if tracked_order.is_pending_cancel_confirmation:
                return order_id

            self.logger().info(f"The blockchain transaction for {order_id} has "
                               f"expired. Canceling the order...")

            numeric_order_id = order_id.split('-')[3]

            resp = await self._get_gateway_instance().clob_delete_orders(
                self.chain,
                self.network,
                self.connector,
                self.address,
                order={
                    "id": numeric_order_id,
                    "marketName": convert_trading_pair(tracked_order.trading_pair),
                    "ownerAddress": self.address,
                }
            )

            signature: Optional[str] = resp.get("signature")

            if signature is not None:
                tracked_order.cancel_tx_hash = signature
            else:
                raise EnvironmentError(f"Missing txHash from the transaction response: {resp}.")

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
        incomplete_orders: List[CLOBInFlightOrder] = []

        # Incomplete Approval Requests
        incomplete_orders.extend([
            o for o in self.approval_orders
            if o.is_pending_approval
        ])
        # Incomplete Active Orders
        incomplete_orders.extend([
            o for o in self.orders
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

    def _get_gateway_instance(self) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        return gateway_instance

    def c_stop_tracking_order(self, order_id):
        raise NotImplementedError

    def get_price(self, trading_pair: str, is_buy: bool, amount: Decimal = constant.DECIMAL_NaN) -> Decimal:
        raise NotImplementedError

    def cancel(self, trading_pair: str, client_order_id: str):
        raise NotImplementedError
