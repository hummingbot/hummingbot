import asyncio
import json
import time
from collections import defaultdict
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from grpc.aio import UnaryStreamCall
from pyinjective.async_client import AsyncClient
from pyinjective.orderhash import OrderHashResponse
from pyinjective.proto.exchange.injective_accounts_rpc_pb2 import StreamSubaccountBalanceResponse
from pyinjective.proto.exchange.injective_derivative_exchange_rpc_pb2 import (
    DerivativeLimitOrderbookV2,
    DerivativeMarketInfo,
    DerivativeOrderHistory,
    DerivativePosition,
    DerivativeTrade,
    FundingPayment,
    FundingPaymentsResponse,
    FundingRate,
    FundingRatesResponse,
    MarketsResponse,
    OrderbooksV2Response,
    OrdersHistoryResponse,
    PositionsResponse,
    StreamOrderbookV2Response,
    StreamOrdersHistoryResponse,
    StreamPositionsResponse,
    StreamTradesResponse,
    TokenMeta,
    TradesResponse,
)
from pyinjective.proto.exchange.injective_explorer_rpc_pb2 import GetTxByTxHashResponse, StreamTxsResponse, TxDetailData
from pyinjective.proto.exchange.injective_oracle_rpc_pb2 import StreamPricesResponse
from pyinjective.proto.exchange.injective_portfolio_rpc_pb2 import (
    AccountPortfolioResponse,
    Coin,
    Portfolio,
    StreamAccountPortfolioResponse,
    SubaccountBalanceV2,
)
from pyinjective.proto.injective.exchange.v1beta1.exchange_pb2 import DerivativeOrder

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.gateway.clob_perp.data_sources.clob_perp_api_data_source_base import CLOBPerpAPIDataSourceBase
from hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual import (
    injective_perpetual_constants as CONSTANTS,
)
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_utils import Composer, OrderHashManager
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates, TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.events import (
    AccountEvent,
    BalanceUpdateEvent,
    MarketEvent,
    OrderBookDataSourceEvent,
    PositionUpdateEvent,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather


class InjectivePerpetualAPIDataSource(CLOBPerpAPIDataSourceBase):
    def __init__(
        self,
        trading_pairs: List[str],
        connector_spec: Dict[str, Any],
        client_config_map: ClientConfigAdapter,
    ):
        super().__init__(
            trading_pairs=trading_pairs, connector_spec=connector_spec, client_config_map=client_config_map
        )
        self._connector_name = CONSTANTS.CONNECTOR_NAME
        self._chain = connector_spec["chain"]
        self._network = connector_spec["network"]
        self._account_id = connector_spec["wallet_address"]
        self._is_default_subaccount = self._account_id[-24:] == "000000000000000000000000"

        self._network_obj = CONSTANTS.NETWORK_CONFIG[self._network]
        self._client = AsyncClient(network=self._network_obj)
        self._account_address: Optional[str] = None
        self._throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)

        self._composer = Composer(network=self._network_obj.string())
        self._order_hash_manager: Optional[OrderHashManager] = None

        # Market Info Attributes
        self._market_id_to_active_perp_markets: Dict[str, DerivativeMarketInfo] = {}

        self._denom_to_token_meta: Dict[str, TokenMeta] = {}

        # Listener(s) and Loop Task(s)
        self._update_market_info_loop_task: Optional[asyncio.Task] = None
        self._trades_stream_listener: Optional[asyncio.Task] = None
        self._order_listeners: Dict[str, asyncio.Task] = {}
        self._funding_info_listeners: Dict[str, asyncio.Task] = {}
        self._order_books_stream_listener: Optional[asyncio.Task] = None
        self._bank_balances_stream_listener: Optional[asyncio.Task] = None
        self._subaccount_balances_stream_listener: Optional[asyncio.Task] = None
        self._positions_stream_listener: Optional[asyncio.Task] = None
        self._transactions_stream_listener: Optional[asyncio.Task] = None

        self._order_placement_lock = asyncio.Lock()

        # Local Balance
        self._account_balances: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        self._account_available_balances: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    @property
    def real_time_balance_update(self) -> bool:
        return True

    @property
    def events_are_streamed(self) -> bool:
        return True

    @staticmethod
    def supported_stream_events() -> List[Enum]:
        return [
            MarketEvent.TradeUpdate,
            MarketEvent.OrderUpdate,
            AccountEvent.BalanceEvent,
            AccountEvent.PositionUpdate,
            MarketEvent.FundingInfo,
            OrderBookDataSourceEvent.TRADE_EVENT,
            OrderBookDataSourceEvent.SNAPSHOT_EVENT,
        ]

    def get_supported_order_types(self) -> List[OrderType]:
        return CONSTANTS.SUPPORTED_ORDER_TYPES

    def supported_position_modes(self) -> List[PositionMode]:
        return CONSTANTS.SUPPORTED_POSITION_MODES

    async def start(self):
        """
        Starts the event streaming.
        """
        async with self._order_placement_lock:
            await self._update_account_address_and_create_order_hash_manager()

        # Fetches and maintains dictionary of active markets
        self._update_market_info_loop_task = self._update_market_info_loop_task or safe_ensure_future(
            coro=self._update_market_info_loop()
        )

        # Ensures all market info has been initialized before starting streaming tasks.
        await self._update_markets()
        await self._start_streams()
        self._gateway_order_tracker.lost_order_count_limit = CONSTANTS.LOST_ORDER_COUNT_LIMIT
        self.logger().debug(f"account: {self._account_id}")
        self.logger().debug(f"balances: {await self.get_account_balances()}")

    async def stop(self):
        """
        Stops the event streaming.
        """
        await self._stop_streams()
        self._update_market_info_loop_task and self._update_market_info_loop_task.cancel()
        self._update_market_info_loop_task = None

    async def check_network_status(self) -> NetworkStatus:
        status = NetworkStatus.CONNECTED
        try:
            async with self._throttler.execute_task(limit_id=CONSTANTS.PING_LIMIT_ID):
                await self._client.ping()
            await self._get_gateway_instance().ping_gateway()
        except asyncio.CancelledError:
            raise
        except Exception:
            status = NetworkStatus.NOT_CONNECTED
        return status

    async def set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """
        Leverage is set on a per order basis. See place_order()
        """
        return True, ""

    async def get_order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        market_info = self._markets_info[trading_pair]
        price_scaler: Decimal = Decimal(f"1e-{market_info.quote_token_meta.decimals}")
        async with self._throttler.execute_task(limit_id=CONSTANTS.ORDER_BOOK_LIMIT_ID):
            response: OrderbooksV2Response = await self._client.get_derivative_orderbooksV2(
                market_ids=[market_info.market_id]
            )

        snapshot_ob: DerivativeLimitOrderbookV2 = response.orderbooks[0].orderbook
        snapshot_timestamp_ms: float = max(
            [entry.timestamp for entry in list(snapshot_ob.buys) + list(snapshot_ob.sells)] + [0]
        )
        snapshot_content: Dict[str, Any] = {
            "trading_pair": combine_to_hb_trading_pair(base=market_info.oracle_base, quote=market_info.oracle_quote),
            "update_id": snapshot_timestamp_ms,
            "bids": [(Decimal(entry.price) * price_scaler, entry.quantity) for entry in snapshot_ob.buys],
            "asks": [(Decimal(entry.price) * price_scaler, entry.quantity) for entry in snapshot_ob.sells],
        }

        snapshot_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=snapshot_content,
            timestamp=snapshot_timestamp_ms * 1e-3,
        )
        return snapshot_msg

    def is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(status_update_exception).startswith("No update found for order")

    def is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    async def get_order_status_update(self, in_flight_order: GatewayInFlightOrder) -> OrderUpdate:
        self.logger().debug(
            f"Fetching order status update for {in_flight_order.client_order_id}"
            f" with order hash {in_flight_order.exchange_order_id}"
        )
        status_update: Optional[OrderUpdate] = None
        misc_updates = {
            "creation_transaction_hash": in_flight_order.creation_transaction_hash,
            "cancelation_transaction_hash": in_flight_order.cancel_tx_hash,
        }

        #  Fetch by Order History
        order_history: Optional[DerivativeOrderHistory] = await self._fetch_order_history(order=in_flight_order)
        if order_history is not None:
            status_update: OrderUpdate = self._parse_order_update_from_order_history(
                order=in_flight_order, order_history=order_history, order_misc_updates=misc_updates
            )

        # Determine if order has failed from transaction hash
        if status_update is None and in_flight_order.creation_transaction_hash is not None:
            try:
                tx_response: GetTxByTxHashResponse = await self._fetch_transaction_by_hash(
                    transaction_hash=in_flight_order.creation_transaction_hash
                )
            except Exception:
                self.logger().debug(
                    f"Failed to fetch transaction {in_flight_order.creation_transaction_hash} for order"
                    f" {in_flight_order.exchange_order_id}.",
                    exc_info=True,
                )
                tx_response = None
            if tx_response is None:
                async with self._order_placement_lock:
                    await self._update_account_address_and_create_order_hash_manager()
            elif await self._check_if_order_failed_based_on_transaction(transaction=tx_response, order=in_flight_order):
                status_update: OrderUpdate = self._parse_failed_order_update_from_transaction_hash_response(
                    order=in_flight_order, response=tx_response, order_misc_updates=misc_updates
                )
                async with self._order_placement_lock:
                    await self._update_account_address_and_create_order_hash_manager()

        if status_update is None:
            raise ValueError(f"No update found for order {in_flight_order.client_order_id}")

        if in_flight_order.current_state == OrderState.PENDING_CREATE and status_update.new_state != OrderState.OPEN:
            open_update = OrderUpdate(
                trading_pair=in_flight_order.trading_pair,
                update_timestamp=status_update.update_timestamp,
                new_state=OrderState.OPEN,
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=status_update.exchange_order_id,
                misc_updates=misc_updates,
            )
            self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=open_update)

        self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=status_update)

        return status_update

    async def place_order(
        self, order: GatewayInFlightOrder, **kwargs
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        perp_order_to_create = [self._compose_derivative_order_for_local_hash_computation(order=order)]
        async with self._order_placement_lock:
            self.logger().debug(f"Creating order {order.client_order_id}")
            order_hashes: OrderHashResponse = self._order_hash_manager.compute_order_hashes(
                spot_orders=[], derivative_orders=perp_order_to_create
            )
            order_hash: str = order_hashes.derivative[0]

            try:
                async with self._throttler.execute_task(limit_id=CONSTANTS.TRANSACTION_POST_LIMIT_ID):
                    order_result: Dict[str, Any] = await self._get_gateway_instance().clob_perp_place_order(
                        connector=self._connector_name,
                        chain=self._chain,
                        network=self._network,
                        trading_pair=order.trading_pair,
                        address=self._account_id,
                        trade_type=order.trade_type,
                        order_type=order.order_type,
                        price=order.price,
                        size=order.amount,
                        leverage=order.leverage,
                    )

                transaction_hash: Optional[str] = order_result.get("txHash")
            except Exception:
                await self._update_account_address_and_create_order_hash_manager()
                self.logger().debug(f"Failed to create order {order.client_order_id}", exc_info=True)
                raise

            self.logger().debug(
                f"Placed order {order.client_order_id} with order hash {order_hash},"
                f" nonce {self._order_hash_manager.current_nonce - 1},"
                f" and tx hash {transaction_hash}."
            )

            if transaction_hash in [None, ""]:
                await self._update_account_address_and_create_order_hash_manager()
                raise ValueError(
                    f"The creation transaction for {order.client_order_id} failed. Please ensure there is sufficient"
                    f" INJ in the bank to cover transaction fees."
                )

        transaction_hash = f"0x{transaction_hash.lower()}"

        misc_updates = {
            "creation_transaction_hash": transaction_hash,
        }

        return order_hash, misc_updates

    async def batch_order_create(self, orders_to_create: List[GatewayInFlightOrder]) -> List[PlaceOrderResult]:
        derivative_orders_to_create = [
            self._compose_derivative_order_for_local_hash_computation(order=order) for order in orders_to_create
        ]

        async with self._order_placement_lock:
            order_hashes = self._order_hash_manager.compute_order_hashes(
                spot_orders=[], derivative_orders=derivative_orders_to_create
            )
            try:
                async with self._throttler.execute_task(limit_id=CONSTANTS.TRANSACTION_POST_LIMIT_ID):
                    update_result = await self._get_gateway_instance().clob_perp_batch_order_modify(
                        connector=self._connector_name,
                        chain=self._chain,
                        network=self._network,
                        address=self._account_id,
                        orders_to_create=orders_to_create,
                        orders_to_cancel=[],
                    )
            except Exception:
                await self._update_account_address_and_create_order_hash_manager()
                raise

            transaction_hash: Optional[str] = update_result.get("txHash")
            exception = None

            if transaction_hash is None:
                await self._update_account_address_and_create_order_hash_manager()
                self.logger().error("The batch order update transaction failed.")
                exception = RuntimeError("The creation transaction has failed on the Injective chain.")

        transaction_hash = f"0x{transaction_hash.lower()}"

        place_order_results = [
            PlaceOrderResult(
                update_timestamp=self._time(),
                client_order_id=order.client_order_id,
                exchange_order_id=order_hash,
                trading_pair=order.trading_pair,
                misc_updates={
                    "creation_transaction_hash": transaction_hash,
                },
                exception=exception,
            )
            for order, order_hash in zip(orders_to_create, order_hashes.derivative)
        ]

        return place_order_results

    async def cancel_order(self, order: GatewayInFlightOrder) -> Tuple[bool, Optional[Dict[str, Any]]]:
        await order.get_exchange_order_id()

        async with self._throttler.execute_task(limit_id=CONSTANTS.TRANSACTION_POST_LIMIT_ID):
            cancelation_result = await self._get_gateway_instance().clob_perp_cancel_order(
                chain=self._chain,
                network=self._network,
                connector=self._connector_name,
                address=self._account_id,
                trading_pair=order.trading_pair,
                exchange_order_id=order.exchange_order_id,
            )
        transaction_hash: Optional[str] = cancelation_result.get("txHash")

        if transaction_hash in [None, ""]:
            async with self._order_placement_lock:
                await self._update_account_address_and_create_order_hash_manager()
            raise ValueError(
                f"The cancelation transaction for {order.client_order_id} failed. Please ensure there is sufficient"
                f" INJ in the bank to cover transaction fees."
            )

        self.logger().debug(
            f"Canceling order {order.client_order_id}"
            f" with order hash {order.exchange_order_id} and tx hash {transaction_hash}."
        )

        transaction_hash = f"0x{transaction_hash.lower()}"

        misc_updates = {"cancelation_transaction_hash": transaction_hash}

        return True, misc_updates

    async def batch_order_cancel(self, orders_to_cancel: List[InFlightOrder]) -> List[CancelOrderResult]:
        in_flight_orders_to_cancel = [
            self._gateway_order_tracker.fetch_tracked_order(client_order_id=order.client_order_id)
            for order in orders_to_cancel
        ]
        exchange_order_ids_to_cancel = await safe_gather(
            *[order.get_exchange_order_id() for order in in_flight_orders_to_cancel],
            return_exceptions=True,
        )
        found_orders_to_cancel = [
            order
            for order, result in zip(orders_to_cancel, exchange_order_ids_to_cancel)
            if not isinstance(result, asyncio.TimeoutError)
        ]

        async with self._throttler.execute_task(limit_id=CONSTANTS.TRANSACTION_POST_LIMIT_ID):
            update_result = await self._get_gateway_instance().clob_perp_batch_order_modify(
                connector=self._connector_name,
                chain=self._chain,
                network=self._network,
                address=self._account_id,
                orders_to_create=[],
                orders_to_cancel=found_orders_to_cancel,
            )

        transaction_hash: Optional[str] = update_result.get("txHash")
        exception = None

        if transaction_hash is None:
            await self._update_account_address_and_create_order_hash_manager()
            self.logger().error("The batch order update transaction failed.")
            exception = RuntimeError("The cancelation transaction has failed on the Injective chain.")

        transaction_hash = f"0x{transaction_hash.lower()}"

        cancel_order_results = [
            CancelOrderResult(
                client_order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                misc_updates={"cancelation_transaction_hash": transaction_hash},
                exception=exception,
            )
            for order in orders_to_cancel
        ]

        return cancel_order_results

    async def fetch_positions(self) -> List[Position]:
        market_ids = self._get_market_ids()
        async with self._throttler.execute_task(limit_id=CONSTANTS.POSITIONS_LIMIT_ID):
            backend_positions: PositionsResponse = await self._client.get_derivative_positions(
                market_ids=market_ids, subaccount_id=self._account_id
            )

        positions = [
            self._parse_backed_position_to_position(backend_position=backed_position)
            for backed_position in backend_positions.positions
        ]
        return positions

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        return await self._request_funding_info(trading_pair=trading_pair)

    async def get_last_traded_price(self, trading_pair: str) -> Decimal:
        return await self._request_last_trade_price(trading_pair=trading_pair)

    async def get_account_balances(self) -> Dict[str, Dict[str, Decimal]]:
        if self._account_address is None:
            async with self._order_placement_lock:
                await self._update_account_address_and_create_order_hash_manager()
        self._check_markets_initialized() or await self._update_markets()

        async with self._throttler.execute_task(limit_id=CONSTANTS.ACCOUNT_PORTFOLIO_LIMIT_ID):
            portfolio_response: AccountPortfolioResponse = await self._client.get_account_portfolio(
                account_address=self._account_address
            )

        portfolio: Portfolio = portfolio_response.portfolio
        bank_balances: List[Coin] = portfolio.bank_balances
        sub_account_balances: List[SubaccountBalanceV2] = portfolio.subaccounts

        balances_dict: Dict[str, Dict[str, Decimal]] = {}

        if self._is_default_subaccount:
            for bank_entry in bank_balances:
                denom_meta = self._denom_to_token_meta.get(bank_entry.denom)
                if denom_meta is not None:
                    asset_name: str = denom_meta.symbol
                    denom_scaler: Decimal = Decimal(f"1e-{denom_meta.decimals}")

                    available_balance: Decimal = Decimal(bank_entry.amount) * denom_scaler
                    total_balance: Decimal = available_balance
                    balances_dict[asset_name] = {
                        "total_balance": total_balance,
                        "available_balance": available_balance,
                    }

        for entry in sub_account_balances:
            if entry.subaccount_id.casefold() != self._account_id.casefold():
                continue

            denom_meta = self._denom_to_token_meta.get(entry.denom)
            if denom_meta is not None:
                asset_name: str = denom_meta.symbol
                denom_scaler: Decimal = Decimal(f"1e-{denom_meta.decimals}")

                total_balance: Decimal = Decimal(entry.deposit.total_balance) * denom_scaler
                available_balance: Decimal = Decimal(entry.deposit.available_balance) * denom_scaler

                balance_element = balances_dict.get(
                    asset_name, {"total_balance": Decimal("0"), "available_balance": Decimal("0")}
                )
                balance_element["total_balance"] += total_balance
                balance_element["available_balance"] += available_balance
                balances_dict[asset_name] = balance_element

        self._update_local_balances(balances=balances_dict)
        return balances_dict

    async def get_all_order_fills(self, in_flight_order: InFlightOrder) -> List[TradeUpdate]:
        self.logger().debug(
            f"Getting all roder fills for {in_flight_order.client_order_id}"
            f" with order hash {in_flight_order.exchange_order_id}"
        )
        exchange_order_id = await in_flight_order.get_exchange_order_id()
        trades: List[DerivativeTrade] = await self._fetch_order_fills(order=in_flight_order)

        trade_updates: List[TradeUpdate] = []
        client_order_id: str = in_flight_order.client_order_id
        for trade in trades:
            if trade.order_hash == exchange_order_id:
                _, trade_update = self._parse_backend_trade(client_order_id=client_order_id, backend_trade=trade)
                trade_updates.append(trade_update)

        return trade_updates

    async def fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")

        if trading_pair not in self._markets_info:
            return timestamp, funding_rate, payment

        async with self._throttler.execute_task(limit_id=CONSTANTS.FUNDING_PAYMENT_LIMIT_ID):
            response: FundingPaymentsResponse = await self._client.get_funding_payments(
                subaccount_id=self._account_id, market_id=self._markets_info[trading_pair].market_id, limit=1
            )

        if len(response.payments) != 0:
            latest_funding_payment: FundingPayment = response.payments[0]  # List of payments sorted by latest

            timestamp: float = latest_funding_payment.timestamp * 1e-3

            # FundingPayment does not include price, hence we have to fetch latest funding rate
            funding_rate: Decimal = await self._request_last_funding_rate(trading_pair=trading_pair)
            amount_scaler: Decimal = Decimal(f"1e-{self._markets_info[trading_pair].quote_token_meta.decimals}")
            payment: Decimal = Decimal(latest_funding_payment.amount) * amount_scaler

        return timestamp, funding_rate, payment

    async def _update_account_address_and_create_order_hash_manager(self):
        if not self._order_placement_lock.locked():
            raise RuntimeError("The order-placement lock must be acquired before creating the order hash manager.")
        async with self._throttler.execute_task(limit_id=CONSTANTS.BALANCES_LIMIT_ID):
            response: Dict[str, Any] = await self._get_gateway_instance().clob_injective_balances(
                chain=self._chain, network=self._network, address=self._account_id
            )
        self._account_address: str = response["injectiveAddress"]

        async with self._throttler.execute_task(limit_id=CONSTANTS.ACCOUNT_LIMIT_ID):
            await self._client.get_account(address=self._account_address)
        async with self._throttler.execute_task(limit_id=CONSTANTS.SYNC_TIMEOUT_HEIGHT_LIMIT_ID):
            await self._client.sync_timeout_height()
        tasks_to_await_submitted_orders_to_be_processed_by_chain = [
            asyncio.wait_for(order.wait_until_processed_by_exchange(), timeout=CONSTANTS.ORDER_CHAIN_PROCESSING_TIMEOUT)
            for order in self._gateway_order_tracker.active_orders.values()
            if order.creation_transaction_hash is not None
        ]  # orders that have been sent to the chain but not yet added to a block will affect the order nonce
        await safe_gather(
            *tasks_to_await_submitted_orders_to_be_processed_by_chain, return_exceptions=True  # await their processing
        )
        self._order_hash_manager = OrderHashManager(network=self._network_obj, sub_account_id=self._account_id)
        async with self._throttler.execute_task(limit_id=CONSTANTS.NONCE_LIMIT_ID):
            await self._order_hash_manager.start()

    def _check_markets_initialized(self) -> bool:
        return (
            len(self._markets_info) != 0
            and len(self._market_id_to_active_perp_markets) != 0
            and len(self._denom_to_token_meta) != 0
        )

    async def trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        """
        Leverage is set on a per order basis. See place_order()
        """
        if mode in self.supported_position_modes() and trading_pair in self._markets_info:
            return True, ""
        return False, "Please check that Position Mode is supported and trading pair is active."

    async def _update_market_info_loop(self):
        while True:
            await self._sleep(delay=CONSTANTS.MARKETS_UPDATE_INTERVAL)
            await self._update_markets()

    async def _update_markets(self):
        """Fetches and updates trading pair maps of active perpetual markets."""
        perpetual_markets: MarketsResponse = await self._fetch_derivative_markets()
        self._update_market_map_attributes(markets=perpetual_markets)
        spot_markets: MarketsResponse = await self._fetch_spot_markets()
        self._update_denom_to_token_meta(markets=spot_markets)

    async def _fetch_derivative_markets(self) -> MarketsResponse:
        market_status: str = "active"
        async with self._throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_MARKETS_LIMIT_ID):
            derivative_markets = await self._client.get_derivative_markets(market_status=market_status)
        return derivative_markets

    async def _fetch_spot_markets(self) -> MarketsResponse:
        market_status: str = "active"
        async with self._throttler.execute_task(limit_id=CONSTANTS.SPOT_MARKETS_LIMIT_ID):
            spot_markets = await self._client.get_spot_markets(market_status=market_status)
        return spot_markets

    def _update_market_map_attributes(self, markets: MarketsResponse):
        """Parses MarketsResponse and re-populate the market map attributes"""
        active_perp_markets: Dict[str, DerivativeMarketInfo] = {}
        market_id_to_market_map: Dict[str, DerivativeMarketInfo] = {}
        for market in markets.markets:
            trading_pair: str = combine_to_hb_trading_pair(base=market.oracle_base, quote=market.oracle_quote)
            market_id: str = market.market_id

            active_perp_markets[trading_pair] = market
            market_id_to_market_map[market_id] = market

        self._markets_info.clear()
        self._market_id_to_active_perp_markets.clear()

        self._markets_info.update(active_perp_markets)
        self._market_id_to_active_perp_markets.update(market_id_to_market_map)

    def _update_denom_to_token_meta(self, markets: MarketsResponse):
        self._denom_to_token_meta.clear()
        for market in markets.markets:
            if market.base_token_meta.symbol != "":  # the meta is defined
                self._denom_to_token_meta[market.base_denom] = market.base_token_meta
            if market.quote_token_meta.symbol != "":  # the meta is defined
                self._denom_to_token_meta[market.quote_denom] = market.quote_token_meta

    def _parse_trading_rule(self, trading_pair: str, market_info: Any) -> TradingRule:
        min_price_tick_size = (
            Decimal(market_info.min_price_tick_size) * Decimal(f"1e-{market_info.quote_token_meta.decimals}")
        )
        min_quantity_tick_size = Decimal(market_info.min_quantity_tick_size)
        trading_rule = TradingRule(
            trading_pair=trading_pair,
            min_order_size=min_quantity_tick_size,
            min_price_increment=min_price_tick_size,
            min_base_amount_increment=min_quantity_tick_size,
            min_quote_amount_increment=min_price_tick_size,
        )
        return trading_rule

    def _compose_derivative_order_for_local_hash_computation(self, order: GatewayInFlightOrder) -> DerivativeOrder:
        market = self._markets_info[order.trading_pair]
        return self._composer.DerivativeOrder(
            market_id=market.market_id,
            subaccount_id=self._account_id.lower(),
            fee_recipient=self._account_address.lower(),
            price=float(order.price),
            quantity=float(order.amount),
            is_buy=order.trade_type == TradeType.BUY,
            is_po=order.order_type == OrderType.LIMIT_MAKER,
            leverage=float(order.leverage),
        )

    async def _fetch_order_history(self, order: GatewayInFlightOrder) -> Optional[DerivativeOrderHistory]:
        # NOTE: Can be replaced by calling GatewayHttpClient.clob_perp_get_orders
        trading_pair: str = order.trading_pair
        order_hash: str = await order.get_exchange_order_id()

        market: DerivativeMarketInfo = self._markets_info[trading_pair]
        direction: str = "buy" if order.trade_type == TradeType.BUY else "sell"
        trade_type: TradeType = order.trade_type
        order_type: OrderType = order.order_type

        order_history: Optional[DerivativeOrderHistory] = None
        skip = 0
        search_completed = False
        while not search_completed:
            async with self._throttler.execute_task(limit_id=CONSTANTS.HISTORICAL_DERIVATIVE_ORDERS_LIMIT_ID):
                response: OrdersHistoryResponse = await self._client.get_historical_derivative_orders(
                    market_id=market.market_id,
                    subaccount_id=self._account_id,
                    direction=direction,
                    start_time=int(order.creation_timestamp * 1e3),
                    limit=CONSTANTS.FETCH_ORDER_HISTORY_LIMIT,
                    skip=skip,
                    order_types=[CONSTANTS.CLIENT_TO_BACKEND_ORDER_TYPES_MAP[(trade_type, order_type)]],
                )
            if len(response.orders) == 0:
                search_completed = True
            else:
                skip += CONSTANTS.FETCH_ORDER_HISTORY_LIMIT
                for response_order in response.orders:
                    if response_order.order_hash == order_hash:
                        order_history = response_order
                        search_completed = True
                        break

        return order_history

    async def _fetch_order_fills(self, order: InFlightOrder) -> List[DerivativeTrade]:
        # NOTE: This can be replaced by calling `GatewayHttpClient.clob_get_order_trades(...)`
        skip = 0
        all_trades: List[DerivativeTrade] = []
        search_completed = False

        market_info: DerivativeMarketInfo = self._markets_info[order.trading_pair]

        market_id: str = market_info.market_id
        direction: str = "buy" if order.trade_type == TradeType.BUY else "sell"

        while not search_completed:
            async with self._throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_TRADES_LIMIT_ID):
                trades = await self._client.get_derivative_trades(
                    market_id=market_id,
                    subaccount_id=self._account_id,
                    direction=direction,
                    skip=skip,
                    start_time=int(order.creation_timestamp * 1e3),
                )
            if len(trades.trades) == 0:
                search_completed = True
            else:
                all_trades.extend(trades.trades)
                skip += len(trades.trades)

        return all_trades

    async def _fetch_transaction_by_hash(self, transaction_hash: str) -> GetTxByTxHashResponse:
        async with self._throttler.execute_task(limit_id=CONSTANTS.TRANSACTION_BY_HASH_LIMIT_ID):
            transaction = await self._client.get_tx_by_hash(tx_hash=transaction_hash)
        return transaction

    def _update_local_balances(self, balances: Dict[str, Dict[str, Decimal]]):
        # We need to keep local copy of total and available balance so we can trigger BalanceUpdateEvent with correct
        # details. This is specifically for Injective during the processing of balance streams, where the messages does not
        # detail the total_balance and available_balance across bank and subaccounts.
        for asset_name, balance_entry in balances.items():
            if "total_balance" in balance_entry:
                self._account_balances[asset_name] = balance_entry["total_balance"]
            if "available_balance" in balance_entry:
                self._account_available_balances[asset_name] = balance_entry["available_balance"]

    async def _request_last_funding_rate(self, trading_pair: str) -> Decimal:
        # NOTE: Can be removed when GatewayHttpClient.clob_perp_funding_info is used.
        market_info: DerivativeMarketInfo = self._markets_info[trading_pair]
        async with self._throttler.execute_task(limit_id=CONSTANTS.FUNDING_RATES_LIMIT_ID):
            response: FundingRatesResponse = await self._client.get_funding_rates(
                market_id=market_info.market_id, limit=1
            )
        funding_rate: FundingRate = response.funding_rates[0]  # We only want the latest funding rate.
        return Decimal(funding_rate.rate)

    async def _request_oracle_price(self, market_info: DerivativeMarketInfo) -> Decimal:
        # NOTE: Can be removed when GatewayHttpClient.clob_perp_funding_info is used.
        """
        According to Injective, Oracle Price refers to mark price.
        """
        async with self._throttler.execute_task(limit_id=CONSTANTS.ORACLE_PRICES_LIMIT_ID):
            response = await self._client.get_oracle_prices(
                base_symbol=market_info.oracle_base,
                quote_symbol=market_info.oracle_quote,
                oracle_type=market_info.oracle_type,
                oracle_scale_factor=0,
            )
        return Decimal(response.price)

    async def _request_last_trade_price(self, trading_pair: str) -> Decimal:
        # NOTE: Can be replaced by calling GatewayHTTPClient.clob_perp_last_trade_price
        market_info: DerivativeMarketInfo = self._markets_info[trading_pair]
        async with self._throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_TRADES_LIMIT_ID):
            response: TradesResponse = await self._client.get_derivative_trades(market_id=market_info.market_id)
        last_trade: DerivativeTrade = response.trades[0]
        price_scaler: Decimal = Decimal(f"1e-{market_info.quote_token_meta.decimals}")
        last_trade_price: Decimal = Decimal(last_trade.position_delta.execution_price) * price_scaler
        return last_trade_price

    def _parse_derivative_ob_message(self, message: StreamOrderbookV2Response) -> OrderBookMessage:
        """
        Order Update Example:
        orderbook {
            buys {
                price: "23452500000"
                quantity: "0.3207"
                timestamp: 1677748154571
            }

            sells {
                price: "23454100000"
                quantity: "0.3207"
                timestamp: 1677748184974
            }
        }
        operation_type: "update"
        timestamp: 1677748187000
        market_id: "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"  # noqa: documentation
        """
        update_ts_ms: int = message.timestamp
        market_id: str = message.market_id
        market: DerivativeMarketInfo = self._market_id_to_active_perp_markets[market_id]
        trading_pair: str = combine_to_hb_trading_pair(base=market.oracle_base, quote=market.oracle_quote)
        price_scaler: Decimal = Decimal(f"1e-{market.quote_token_meta.decimals}")
        bids = [(Decimal(bid.price) * price_scaler, Decimal(bid.quantity)) for bid in message.orderbook.buys]
        asks = [(Decimal(ask.price) * price_scaler, Decimal(ask.quantity)) for ask in message.orderbook.sells]
        snapshot_msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": update_ts_ms,
                "bids": bids,
                "asks": asks,
            },
            timestamp=update_ts_ms * 1e-3,
        )
        return snapshot_msg

    def _process_order_book_stream_event(self, message: StreamOrderbookV2Response):
        snapshot_msg: OrderBookMessage = self._parse_derivative_ob_message(message=message)
        self._publisher.trigger_event(event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, message=snapshot_msg)

    async def _listen_to_order_books_stream(self):
        while True:
            market_ids = self._get_market_ids()
            stream: UnaryStreamCall = await self._client.stream_derivative_orderbook_snapshot(market_ids=market_ids)
            try:
                async for ob_msg in stream:
                    self._process_order_book_stream_event(message=ob_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in orderbook listener loop.")
            self.logger().info("Restarting order books stream.")
            stream.cancel()

    def _parse_backend_trade(
        self, client_order_id: str, backend_trade: DerivativeTrade
    ) -> Tuple[OrderBookMessage, TradeUpdate]:
        exchange_order_id: str = backend_trade.order_hash
        market_id: str = backend_trade.market_id
        market: DerivativeMarketInfo = self._market_id_to_active_perp_markets[market_id]
        trading_pair: str = combine_to_hb_trading_pair(base=market.oracle_base, quote=market.oracle_quote)
        trade_id: str = backend_trade.trade_id

        price_scaler: Decimal = Decimal(f"1e-{market.quote_token_meta.decimals}")
        price: Decimal = Decimal(backend_trade.position_delta.execution_price) * price_scaler
        size: Decimal = Decimal(backend_trade.position_delta.execution_quantity)
        is_taker: bool = backend_trade.execution_side == "taker"

        fee_amount: Decimal = Decimal(backend_trade.fee) * price_scaler
        _, quote = split_hb_trading_pair(trading_pair=trading_pair)
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=TradeFeeSchema(),
            position_action=PositionAction.OPEN,
            flat_fees=[TokenAmount(amount=fee_amount, token=quote)],
        )

        trade_msg_content = {
            "trade_id": trade_id,
            "trading_pair": trading_pair,
            "trade_type": TradeType.BUY if backend_trade.position_delta.trade_direction == "buy" else TradeType.SELL,
            "amount": size,
            "price": price,
            "is_taker": is_taker,
        }
        trade_ob_msg = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            timestamp=backend_trade.executed_at * 1e-3,
            content=trade_msg_content,
        )

        trade_update = TradeUpdate(
            trade_id=trade_id,
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            fill_timestamp=backend_trade.executed_at * 1e-3,
            fill_price=price,
            fill_base_amount=size,
            fill_quote_amount=price * size,
            fee=fee,
        )
        return trade_ob_msg, trade_update

    def _process_trade_stream_event(self, message: StreamTradesResponse):
        trade_message: DerivativeTrade = message.trade
        exchange_order_id = trade_message.order_hash
        tracked_order = self._gateway_order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)
        client_order_id = "" if tracked_order is None else tracked_order.client_order_id
        trade_ob_msg, trade_update = self._parse_backend_trade(
            client_order_id=client_order_id, backend_trade=trade_message
        )

        self._publisher.trigger_event(event_tag=OrderBookDataSourceEvent.TRADE_EVENT, message=trade_ob_msg)
        self._publisher.trigger_event(event_tag=MarketEvent.TradeUpdate, message=trade_update)

    async def _listen_to_trades_stream(self):
        while True:
            market_ids: List[str] = self._get_market_ids()
            stream: UnaryStreamCall = await self._client.stream_derivative_trades(market_ids=market_ids)
            try:
                async for trade_msg in stream:
                    self._process_trade_stream_event(message=trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in public trade listener loop.")
            self.logger().info("Restarting public trades stream.")
            stream.cancel()

    async def _listen_to_bank_balances_streams(self):
        while True:
            stream: UnaryStreamCall = await self._client.stream_account_portfolio(
                account_address=self._account_address, type="bank"
            )
            try:
                async for bank_balance in stream:
                    self._process_bank_balance_stream_event(message=bank_balance)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in account balance listener loop.")
            self.logger().info("Restarting account balances stream.")
            stream.cancel()

    def _process_bank_balance_stream_event(self, message: StreamAccountPortfolioResponse):
        denom_meta = self._denom_to_token_meta[message.denom]
        symbol = denom_meta.symbol
        safe_ensure_future(self._issue_balance_update(token=symbol))

    async def _listen_to_subaccount_balances_stream(self):
        while True:
            # Uses InjectiveAccountsRPC since it provides both total_balance and available_balance in a single stream.
            stream: UnaryStreamCall = await self._client.stream_subaccount_balance(subaccount_id=self._account_id)
            try:
                async for balance_msg in stream:
                    self._process_subaccount_balance_stream_event(message=balance_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in account balance listener loop.")
            self.logger().info("Restarting account balances stream.")
            stream.cancel()

    def _process_subaccount_balance_stream_event(self, message: StreamSubaccountBalanceResponse):
        denom_meta = self._denom_to_token_meta[message.balance.denom]
        symbol = denom_meta.symbol
        safe_ensure_future(self._issue_balance_update(token=symbol))

    async def _issue_balance_update(self, token: str):
        account_balances = await self.get_account_balances()
        token_balances = account_balances.get(token, {})
        total_balance = token_balances.get("total_balance", Decimal("0"))
        available_balance = token_balances.get("available_balance", Decimal("0"))
        balance_msg = BalanceUpdateEvent(
            timestamp=self._time(),
            asset_name=token,
            total_balance=total_balance,
            available_balance=available_balance,
        )
        self._publisher.trigger_event(event_tag=AccountEvent.BalanceEvent, message=balance_msg)

    @staticmethod
    def _parse_order_update_from_order_history(
        order: GatewayInFlightOrder, order_history: DerivativeOrderHistory, order_misc_updates: Dict[str, Any]
    ) -> OrderUpdate:
        order_update: OrderUpdate = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=order_history.updated_at * 1e-3,
            new_state=CONSTANTS.INJ_DERIVATIVE_ORDER_STATES[order_history.state],
            client_order_id=order.client_order_id,
            exchange_order_id=order_history.order_hash,
            misc_updates=order_misc_updates,
        )
        return order_update

    @staticmethod
    def _parse_failed_order_update_from_transaction_hash_response(
        order: GatewayInFlightOrder, response: GetTxByTxHashResponse, order_misc_updates: Dict[str, Any]
    ) -> Optional[OrderUpdate]:
        tx_detail: TxDetailData = response.data

        status_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=tx_detail.block_unix_timestamp * 1e-3,
            new_state=OrderState.FAILED,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            misc_updates=order_misc_updates,
        )
        return status_update

    @staticmethod
    async def _check_if_order_failed_based_on_transaction(
        transaction: GetTxByTxHashResponse, order: GatewayInFlightOrder
    ) -> bool:
        order_hash = await order.get_exchange_order_id()
        return order_hash.lower() not in transaction.data.data.decode().lower()

    async def _process_transaction_event(self, transaction: StreamTxsResponse):
        order: GatewayInFlightOrder = self._gateway_order_tracker.get_fillable_order_by_hash(
            transaction_hash=transaction.hash
        )
        if order is not None:
            messages = json.loads(s=transaction.messages)
            for message in messages:
                if message["type"] in CONSTANTS.INJ_DERIVATIVE_TX_EVENT_TYPES:
                    self.logger().debug(
                        f"received transaction event of type {message['type']} for order {order.exchange_order_id}"
                    )
                    self.logger().debug(f"message: {message}")
                    safe_ensure_future(coro=self.get_order_status_update(in_flight_order=order))

    async def _listen_to_transactions_stream(self):
        while True:
            stream: UnaryStreamCall = await self._client.stream_txs()
            try:
                async for transaction in stream:
                    await self._process_transaction_event(transaction=transaction)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in transaction listener loop.")
            self.logger().info("Restarting transactions stream.")
            stream.cancel()

    async def _process_order_update_event(self, message: StreamOrdersHistoryResponse):
        """
        Order History Stream example:
            order {
                order_hash: "0xfb526d72b85e9ffb4426c37bf332403fb6fb48709fb5d7ca3be7b8232cd10292"  # noqa: documentation
                market_id: "0x90e662193fa29a3a7e6c07be4407c94833e762d9ee82136a2cc712d6b87d7de3"  # noqa: documentation
                is_active: true
                subaccount_id: "0xc6fe5d33615a1c52c08018c47e8bc53646a0e101000000000000000000000000"  # noqa: documentation
                execution_type: "limit"
                order_type: "sell_po"
                price: "274310000"
                trigger_price: "0"
                quantity: "144"
                filled_quantity: "0"
                state: "booked"
                created_at: 1665487076373
                updated_at: 1665487076373
                direction: "sell"
                margin: "3950170000"
                }
            operation_type: "insert"
            timestamp: 1665487078000
        """
        order_update_msg: DerivativeOrderHistory = message.order
        order_hash: str = order_update_msg.order_hash

        in_flight_order = self._gateway_order_tracker.all_fillable_orders_by_exchange_order_id.get(order_hash)
        if in_flight_order is not None:
            market_id = order_update_msg.market_id
            trading_pair = self._get_trading_pair_from_market_id(market_id=market_id)
            order_update = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=order_update_msg.updated_at * 1e-3,
                new_state=CONSTANTS.INJ_DERIVATIVE_ORDER_STATES[order_update_msg.state],
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=order_update_msg.order_hash,
            )
            if in_flight_order.current_state == OrderState.PENDING_CREATE and order_update.new_state != OrderState.OPEN:
                open_update = OrderUpdate(
                    trading_pair=trading_pair,
                    update_timestamp=order_update_msg.updated_at * 1e-3,
                    new_state=OrderState.OPEN,
                    client_order_id=in_flight_order.client_order_id,
                    exchange_order_id=order_update_msg.order_hash,
                )
                self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=open_update)
            self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=order_update)

    def _get_trading_pair_from_market_id(self, market_id: str) -> str:
        market = self._market_id_to_active_perp_markets[market_id]
        trading_pair = combine_to_hb_trading_pair(base=market.oracle_base, quote=market.oracle_quote)
        return trading_pair

    async def _listen_order_updates_stream(self, market_id: str):
        while True:
            stream: UnaryStreamCall = await self._client.stream_historical_derivative_orders(market_id=market_id)
            try:
                async for order in stream:
                    await self._process_order_update_event(message=order)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user order listener loop.")
            self.logger().info("Restarting user orders stream.")
            stream.cancel()

    async def _process_position_event(self, message: StreamPositionsResponse):
        """
        Position Stream example:
        position {
            ticker: "BTC/USDT PERP"
            market_id: "0x90e662193fa29a3a7e6c07be4407c94833e762d9ee82136a2cc712d6b87d7de3"  # noqa: documentation
            subaccount_id: "0xea98e3aa091a6676194df40ac089e40ab4604bf9000000000000000000000000"  # noqa: documentation
            direction: "short"
            quantity: "0.01"
            entry_price: "18000000000"
            margin: "186042357.839476"
            liquidation_price: "34861176937.092952"
            mark_price: "16835930000"
            aggregate_reduce_only_quantity: "0"
            updated_at: 1676412001911
            created_at: -62135596800000
        }
        timestamp: 1652793296000
        """
        backend_position: DerivativePosition = message.position
        position_update = self._parse_backend_position_to_position_event(backend_position=backend_position)

        self._publisher.trigger_event(event_tag=AccountEvent.PositionUpdate, message=position_update)

    def _parse_backed_position_to_position(self, backend_position: DerivativePosition) -> Position:
        position_event = self._parse_backend_position_to_position_event(backend_position=backend_position)
        position = Position(
            trading_pair=position_event.trading_pair,
            position_side=position_event.position_side,
            unrealized_pnl=position_event.unrealized_pnl,
            entry_price=position_event.entry_price,
            amount=position_event.amount,
            leverage=position_event.leverage,
        )
        return position

    def _parse_backend_position_to_position_event(self, backend_position: DerivativePosition) -> PositionUpdateEvent:
        market_info: DerivativeMarketInfo = self._market_id_to_active_perp_markets[backend_position.market_id]
        trading_pair: str = combine_to_hb_trading_pair(base=market_info.oracle_base, quote=market_info.oracle_quote)
        amount: Decimal = Decimal(backend_position.quantity)
        if backend_position.direction != "":
            position_side = PositionSide[backend_position.direction.upper()]
            entry_price: Decimal = (
                Decimal(backend_position.entry_price) * Decimal(f"1e-{market_info.quote_token_meta.decimals}")
            )
            mark_price: Decimal = (
                Decimal(backend_position.mark_price) * Decimal(f"1e-{market_info.oracle_scale_factor}")
            )
            leverage = Decimal(
                round(
                    Decimal(backend_position.entry_price) / (
                        Decimal(backend_position.margin) / Decimal(backend_position.quantity)
                    )
                )
            )
            if backend_position.direction == "short":
                amount = -amount  # client expects short positions to be negative in size
            unrealized_pnl: Decimal = amount * ((1 / entry_price) - (1 / mark_price))
        else:
            position_side = None
            entry_price = Decimal("0")
            unrealized_pnl = Decimal("0")
            leverage = Decimal("0")

        position = PositionUpdateEvent(
            timestamp=backend_position.updated_at * 1e-3,
            trading_pair=trading_pair,
            position_side=position_side,
            unrealized_pnl=unrealized_pnl,
            entry_price=entry_price,
            amount=amount,
            leverage=leverage,
        )

        return position

    async def _listen_to_positions_stream(self):
        while True:
            market_ids = self._get_market_ids()
            stream: UnaryStreamCall = await self._client.stream_derivative_positions(
                market_ids=market_ids, subaccount_id=self._account_id
            )
            try:
                async for message in stream:
                    await self._process_position_event(message=message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in position listener loop.")
            self.logger().info("Restarting position stream.")
            stream.cancel()

    async def _process_funding_info_event(self, market_info: DerivativeMarketInfo, message: StreamPricesResponse):
        trading_pair: str = combine_to_hb_trading_pair(base=market_info.oracle_base, quote=market_info.oracle_quote)
        funding_info = await self._request_funding_info(trading_pair=trading_pair)
        funding_info_event = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=funding_info.index_price,
            mark_price=funding_info.mark_price,
            next_funding_utc_timestamp=funding_info.next_funding_utc_timestamp,
            rate=funding_info.rate,
        )
        self._publisher.trigger_event(event_tag=MarketEvent.FundingInfo, message=funding_info_event)

    async def _request_funding_info(self, trading_pair: str) -> FundingInfo:
        # NOTE: Can be replaced with GatewayHttpClient.clob_perp_funding_info()
        self._check_markets_initialized() or await self._update_markets()
        market_info: DerivativeMarketInfo = self._markets_info[trading_pair]
        last_funding_rate: Decimal = await self._request_last_funding_rate(trading_pair=trading_pair)
        oracle_price: Decimal = await self._request_oracle_price(market_info=market_info)
        last_trade_price: Decimal = await self._request_last_trade_price(trading_pair=trading_pair)
        async with self._throttler.execute_task(limit_id=CONSTANTS.SINGLE_DERIVATIVE_MARKET_LIMIT_ID):
            updated_market_info = await self._client.get_derivative_market(market_id=market_info.market_id)
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=last_trade_price,  # Default to using last trade price
            mark_price=oracle_price,
            next_funding_utc_timestamp=(
                updated_market_info.market.perpetual_market_info.next_funding_timestamp * 1e-3
            ),
            rate=last_funding_rate,
        )
        return funding_info

    async def _listen_to_funding_info_stream(self, market_id: str):
        self._check_markets_initialized() or await self._update_markets()
        while True:
            market_info = self._market_id_to_active_perp_markets[market_id]
            stream: UnaryStreamCall = await self._client.stream_oracle_prices(
                base_symbol=market_info.oracle_base,
                quote_symbol=market_info.oracle_quote,
                oracle_type=market_info.oracle_type,
            )
            try:
                async for message in stream:
                    await self._process_funding_info_event(market_info=market_info, message=message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in position listener loop.")
            self.logger().info("Restarting position stream.")
            stream.cancel()

    async def _start_streams(self):
        self._trades_stream_listener = self._trades_stream_listener or safe_ensure_future(
            coro=self._listen_to_trades_stream()
        )
        self._order_books_stream_listener = self._order_books_stream_listener or safe_ensure_future(
            coro=self._listen_to_order_books_stream()
        )
        if self._is_default_subaccount:
            self._bank_balances_stream_listener = self._bank_balances_stream_listener or safe_ensure_future(
                coro=self._listen_to_bank_balances_streams()
            )
        self._subaccount_balances_stream_listener = self._subaccount_balances_stream_listener or safe_ensure_future(
            coro=self._listen_to_subaccount_balances_stream()
        )
        self._transactions_stream_listener = self._transactions_stream_listener or safe_ensure_future(
            coro=self._listen_to_transactions_stream()
        )
        self._positions_stream_listener = self._positions_stream_listener or safe_ensure_future(
            coro=self._listen_to_positions_stream()
        )
        for market_id in [self._markets_info[tp].market_id for tp in self._trading_pairs]:
            if market_id not in self._order_listeners:
                self._order_listeners[market_id] = safe_ensure_future(
                    coro=self._listen_order_updates_stream(market_id=market_id)
                )
            if market_id not in self._funding_info_listeners:
                self._funding_info_listeners[market_id] = safe_ensure_future(
                    coro=self._listen_to_funding_info_stream(market_id=market_id)
                )

    async def _stop_streams(self):
        self._trades_stream_listener and self._trades_stream_listener.cancel()
        self._trades_stream_listener = None
        for listener in self._order_listeners.values():
            listener.cancel()
        self._order_listeners = {}
        for listener in self._funding_info_listeners.values():
            listener.cancel()
        self._funding_info_listeners = {}
        self._order_books_stream_listener and self._order_books_stream_listener.cancel()
        self._order_books_stream_listener = None
        self._subaccount_balances_stream_listener and self._subaccount_balances_stream_listener.cancel()
        self._subaccount_balances_stream_listener = None
        self._bank_balances_stream_listener and self._bank_balances_stream_listener.cancel()
        self._bank_balances_stream_listener = None
        self._transactions_stream_listener and self._transactions_stream_listener.cancel()
        self._transactions_stream_listener = None
        self._positions_stream_listener and self._positions_stream_listener.cancel()
        self._positions_stream_listener = None

    def _get_exchange_trading_pair_from_market_info(self, market_info: Any) -> str:
        return market_info.market_id

    def _get_maker_taker_exchange_fee_rates_from_market_info(
        self, market_info: Any
    ) -> MakerTakerExchangeFeeRates:
        # Since we are using the API, we are the service provider.
        # Reference: https://api.injective.exchange/#overview-trading-fees-and-gas
        fee_scaler = Decimal("1") - Decimal(market_info.service_provider_fee)
        maker_fee = Decimal(market_info.maker_fee_rate) * fee_scaler
        taker_fee = Decimal(market_info.taker_fee_rate) * fee_scaler
        maker_taker_exchange_fee_rates = MakerTakerExchangeFeeRates(
            maker=maker_fee, taker=taker_fee, maker_flat_fees=[], taker_flat_fees=[]
        )
        return maker_taker_exchange_fee_rates

    def _get_gateway_instance(self) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        return gateway_instance

    def _get_market_ids(self) -> List[str]:
        market_ids = [
            self._markets_info[trading_pair].market_id
            for trading_pair in self._trading_pairs
        ]
        return market_ids

    @staticmethod
    async def _sleep(delay: float):
        await asyncio.sleep(delay)

    @staticmethod
    def _time() -> float:
        return time.time()
