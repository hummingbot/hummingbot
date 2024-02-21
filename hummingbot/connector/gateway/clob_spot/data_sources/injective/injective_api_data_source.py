import asyncio
import json
import time
from asyncio import Lock
from collections import defaultdict
from decimal import Decimal
from enum import Enum
from math import floor
from typing import Any, Dict, List, Mapping, Optional, Tuple

from grpc.aio import UnaryStreamCall
from pyinjective.async_client import AsyncClient
from pyinjective.composer import Composer as ProtoMsgComposer
from pyinjective.core.network import Network
from pyinjective.proto.exchange.injective_accounts_rpc_pb2 import StreamSubaccountBalanceResponse
from pyinjective.proto.exchange.injective_explorer_rpc_pb2 import GetTxByTxHashResponse, StreamTxsResponse
from pyinjective.proto.exchange.injective_portfolio_rpc_pb2 import (
    AccountPortfolioResponse,
    Coin,
    Portfolio,
    StreamAccountPortfolioResponse,
    SubaccountBalanceV2,
)
from pyinjective.proto.exchange.injective_spot_exchange_rpc_pb2 import (
    MarketsResponse,
    SpotMarketInfo,
    SpotOrderHistory,
    SpotTrade,
    StreamOrderbookV2Response,
    StreamOrdersResponse,
    StreamTradesResponse,
    TokenMeta,
)
from pyinjective.proto.injective.exchange.v1beta1.exchange_pb2 import SpotOrder
from pyinjective.wallet import Address

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.clob_spot.data_sources.clob_api_data_source_base import CLOBAPIDataSourceBase
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_constants import (
    BACKEND_TO_CLIENT_ORDER_STATE_MAP,
    CLIENT_TO_BACKEND_ORDER_TYPES_MAP,
    CONNECTOR_NAME,
    DEFAULT_SUB_ACCOUNT_SUFFIX,
    LOST_ORDER_COUNT_LIMIT,
    MARKETS_UPDATE_INTERVAL,
    MSG_BATCH_UPDATE_ORDERS,
    MSG_CANCEL_SPOT_ORDER,
    MSG_CREATE_SPOT_LIMIT_ORDER,
    ORDER_CHAIN_PROCESSING_TIMEOUT,
    REQUESTS_SKIP_STEP,
)
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_utils import OrderHashManager
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book import OrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates, TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent, OrderBookDataSourceEvent
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


class InjectiveAPIDataSource(CLOBAPIDataSourceBase):
    """An interface class to the Injective blockchain.

    Note — The same wallet address should not be used with different instances of the client as this will cause
    issues with the account sequence management and may result in failed transactions, or worse, wrong locally computed
    order hashes (exchange order IDs), which will in turn result in orphaned orders on the exchange.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector_spec: Dict[str, Any],
        client_config_map: ClientConfigAdapter,
    ):
        super().__init__(
            trading_pairs=trading_pairs, connector_spec=connector_spec, client_config_map=client_config_map
        )
        self._connector_name = CONNECTOR_NAME
        self._chain = connector_spec["chain"]
        self._network = connector_spec["network"]
        self._sub_account_id = connector_spec["wallet_address"]
        self._account_address: str = Address(bytes.fromhex(self._sub_account_id[2:-24])).to_acc_bech32()
        if self._network == "mainnet":
            self._network_obj = Network.mainnet()
        elif self._network == "testnet":
            self._network_obj = Network.testnet()
        else:
            raise ValueError(f"Invalid network: {self._network}")
        self._client = AsyncClient(network=self._network_obj)
        self._composer = ProtoMsgComposer(network=self._network_obj.string())
        self._order_hash_manager: Optional[OrderHashManager] = None

        self._markets_info: Dict[str, SpotMarketInfo] = {}
        self._market_id_to_active_spot_markets: Dict[str, SpotMarketInfo] = {}
        self._denom_to_token_meta: Dict[str, TokenMeta] = {}
        self._markets_update_task: Optional[asyncio.Task] = None

        self._trades_stream_listener: Optional[asyncio.Task] = None
        self._order_listeners: Dict[str, asyncio.Task] = {}
        self._order_books_stream_listener: Optional[asyncio.Task] = None
        self._bank_balances_stream_listener: Optional[asyncio.Task] = None
        self._subaccount_balances_stream_listener: Optional[asyncio.Task] = None
        self._transactions_stream_listener: Optional[asyncio.Task] = None

        self._order_placement_lock = Lock()

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
            OrderBookDataSourceEvent.TRADE_EVENT,
            OrderBookDataSourceEvent.DIFF_EVENT,
            OrderBookDataSourceEvent.SNAPSHOT_EVENT,
        ]

    def get_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def _is_default_subaccount(self):
        return self._sub_account_id[-24:] == DEFAULT_SUB_ACCOUNT_SUFFIX

    async def start(self):
        """Starts the event streaming."""
        async with self._order_placement_lock:
            await self._update_account_address_and_create_order_hash_manager()
        self._markets_update_task = self._markets_update_task or safe_ensure_future(
            coro=self._update_markets_loop()
        )
        await self._update_markets()  # required for the streams
        await self._start_streams()
        self._gateway_order_tracker.lost_order_count_limit = LOST_ORDER_COUNT_LIMIT

    async def stop(self):
        """Stops the event streaming."""
        await self._stop_streams()
        self._markets_update_task and self._markets_update_task.cancel()
        self._markets_update_task = None

    async def check_network_status(self) -> NetworkStatus:
        status = NetworkStatus.CONNECTED
        try:
            await self._client.ping()
            await self._get_gateway_instance().ping_gateway()
        except asyncio.CancelledError:
            raise
        except Exception:
            status = NetworkStatus.NOT_CONNECTED
        return status

    async def get_order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        market = self._markets_info[trading_pair]
        order_book_response = await self._client.get_spot_orderbooksV2(market_ids=[market.market_id])
        price_scale = self._get_backend_price_scaler(market=market)
        size_scale = self._get_backend_denom_scaler(denom_meta=market.base_token_meta)
        last_update_timestamp_ms = 0
        bids = []
        orderbook = order_book_response.orderbooks[0].orderbook
        for bid in orderbook.buys:
            bids.append((Decimal(bid.price) * price_scale, Decimal(bid.quantity) * size_scale))
            last_update_timestamp_ms = max(last_update_timestamp_ms, bid.timestamp)
        asks = []
        for ask in orderbook.sells:
            asks.append((Decimal(ask.price) * price_scale, Decimal(ask.quantity) * size_scale))
            last_update_timestamp_ms = max(last_update_timestamp_ms, ask.timestamp)
        snapshot_msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": last_update_timestamp_ms,
                "bids": bids,
                "asks": asks,
            },
            timestamp=last_update_timestamp_ms * 1e-3,
        )
        return snapshot_msg

    def is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(status_update_exception).startswith("No update found for order")

    def is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    async def get_order_status_update(self, in_flight_order: GatewayInFlightOrder) -> OrderUpdate:
        status_update: Optional[OrderUpdate] = None
        trading_pair = in_flight_order.trading_pair
        order_hash = await in_flight_order.get_exchange_order_id()
        misc_updates = {
            "creation_transaction_hash": in_flight_order.creation_transaction_hash,
            "cancelation_transaction_hash": in_flight_order.cancel_tx_hash,
        }

        market = self._markets_info[trading_pair]
        direction = "buy" if in_flight_order.trade_type == TradeType.BUY else "sell"
        status_update = await self._get_booked_order_status_update(
            trading_pair=trading_pair,
            client_order_id=in_flight_order.client_order_id,
            order_hash=order_hash,
            market_id=market.market_id,
            direction=direction,
            creation_timestamp=in_flight_order.creation_timestamp,
            order_type=in_flight_order.order_type,
            trade_type=in_flight_order.trade_type,
            order_mist_updates=misc_updates,
        )
        if status_update is None and in_flight_order.creation_transaction_hash is not None:
            try:
                tx_response = await self._get_transaction_by_hash(
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
            elif await self._check_if_order_failed_based_on_transaction(
                transaction=tx_response, order=in_flight_order
            ):
                status_update = OrderUpdate(
                    trading_pair=in_flight_order.trading_pair,
                    update_timestamp=tx_response.data.block_unix_timestamp * 1e-3,
                    new_state=OrderState.FAILED,
                    client_order_id=in_flight_order.client_order_id,
                    exchange_order_id=in_flight_order.exchange_order_id,
                    misc_updates=misc_updates,
                )
                async with self._order_placement_lock:
                    await self._update_account_address_and_create_order_hash_manager()
        if status_update is None:
            raise IOError(f"No update found for order {in_flight_order.client_order_id}")

        if in_flight_order.current_state == OrderState.PENDING_CREATE and status_update.new_state != OrderState.OPEN:
            open_update = OrderUpdate(
                trading_pair=trading_pair,
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
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        spot_order_to_create = [self._compose_spot_order_for_local_hash_computation(order=order)]
        async with self._order_placement_lock:
            order_hashes = self._order_hash_manager.compute_order_hashes(
                spot_orders=spot_order_to_create, derivative_orders=[]
            )
            order_hash = order_hashes.spot[0]

            try:
                order_result: Dict[str, Any] = await self._get_gateway_instance().clob_place_order(
                    connector=self._connector_name,
                    chain=self._chain,
                    network=self._network,
                    trading_pair=order.trading_pair,
                    address=self._sub_account_id,
                    trade_type=order.trade_type,
                    order_type=order.order_type,
                    price=order.price,
                    size=order.amount,
                )
                transaction_hash: Optional[str] = order_result.get("txHash")
            except Exception:
                await self._update_account_address_and_create_order_hash_manager()
                raise

            self.logger().debug(
                f"Placed order {order_hash} with nonce {self._order_hash_manager.current_nonce - 1}"
                f" and tx hash {transaction_hash}."
            )

            if transaction_hash in (None, ""):
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
        spot_orders_to_create = [
            self._compose_spot_order_for_local_hash_computation(order=order)
            for order in orders_to_create
        ]

        async with self._order_placement_lock:
            order_hashes = self._order_hash_manager.compute_order_hashes(
                spot_orders=spot_orders_to_create, derivative_orders=[]
            )
            try:
                update_result = await self._get_gateway_instance().clob_batch_order_modify(
                    connector=self._connector_name,
                    chain=self._chain,
                    network=self._network,
                    address=self._sub_account_id,
                    orders_to_create=orders_to_create,
                    orders_to_cancel=[],
                )
            except Exception:
                await self._update_account_address_and_create_order_hash_manager()
                raise

            transaction_hash: Optional[str] = update_result.get("txHash")
            exception = None

            if transaction_hash in (None, ""):
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
            ) for order, order_hash in zip(orders_to_create, order_hashes.spot)
        ]

        return place_order_results

    async def cancel_order(self, order: GatewayInFlightOrder) -> Tuple[bool, Dict[str, Any]]:
        await order.get_exchange_order_id()

        cancelation_result = await self._get_gateway_instance().clob_cancel_order(
            connector=self._connector_name,
            chain=self._chain,
            network=self._network,
            trading_pair=order.trading_pair,
            address=self._sub_account_id,
            exchange_order_id=order.exchange_order_id,
        )
        transaction_hash: Optional[str] = cancelation_result.get("txHash")

        if transaction_hash in (None, ""):
            async with self._order_placement_lock:
                await self._update_account_address_and_create_order_hash_manager()
            raise ValueError(
                f"The cancelation transaction for {order.client_order_id} failed. Please ensure there is sufficient"
                f" INJ in the bank to cover transaction fees."
            )

        transaction_hash = f"0x{transaction_hash.lower()}"

        misc_updates = {
            "cancelation_transaction_hash": transaction_hash
        }

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

        update_result = await self._get_gateway_instance().clob_batch_order_modify(
            connector=self._connector_name,
            chain=self._chain,
            network=self._network,
            address=self._sub_account_id,
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
                misc_updates={
                    "cancelation_transaction_hash": transaction_hash
                },
                exception=exception,
            ) for order in orders_to_cancel
        ]

        return cancel_order_results

    async def get_last_traded_price(self, trading_pair: str) -> Decimal:
        market = self._markets_info[trading_pair]
        trades = await self._client.get_spot_trades(market_id=market.market_id)
        if len(trades.trades) != 0:
            price = self._convert_price_from_backend(price=trades.trades[0].price.price, market=market)
        else:
            price = Decimal("NaN")
        return price

    async def get_account_balances(self) -> Dict[str, Dict[str, Decimal]]:
        if self._account_address is None:
            async with self._order_placement_lock:
                await self._update_account_address_and_create_order_hash_manager()
        self._check_markets_initialized() or await self._update_markets()

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
            if entry.subaccount_id.casefold() != self._sub_account_id.casefold():
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

    async def get_all_order_fills(self, in_flight_order: GatewayInFlightOrder) -> List[TradeUpdate]:
        trading_pair = in_flight_order.trading_pair
        market = self._markets_info[trading_pair]
        exchange_order_id = await in_flight_order.get_exchange_order_id()
        direction = "buy" if in_flight_order.trade_type == TradeType.BUY else "sell"
        trades = await self._get_all_trades(
            market_id=market.market_id,
            direction=direction,
            created_at=int(in_flight_order.creation_timestamp * 1e3),
            updated_at=int(in_flight_order.last_update_timestamp * 1e3)
        )

        client_order_id: str = in_flight_order.client_order_id
        trade_updates = []

        for trade in trades:
            if trade.order_hash == exchange_order_id:
                _, trade_update = self._parse_backend_trade(client_order_id=client_order_id, backend_trade=trade)
                trade_updates.append(trade_update)

        return trade_updates

    async def _update_account_address_and_create_order_hash_manager(self):
        if not self._order_placement_lock.locked():
            raise RuntimeError("The order-placement lock must be acquired before creating the order hash manager.")
        response: Dict[str, Any] = await self._get_gateway_instance().clob_injective_balances(
            chain=self._chain, network=self._network, address=self._sub_account_id
        )
        self._account_address: str = response["injectiveAddress"]

        await self._client.get_account(self._account_address)
        await self._client.sync_timeout_height()
        tasks_to_await_submitted_orders_to_be_processed_by_chain = [
            asyncio.wait_for(order.wait_until_processed_by_exchange(), timeout=ORDER_CHAIN_PROCESSING_TIMEOUT)
            for order in self._gateway_order_tracker.active_orders.values()
            if order.creation_transaction_hash is not None
        ]  # orders that have been sent to the chain but not yet added to a block will affect the order nonce
        await safe_gather(*tasks_to_await_submitted_orders_to_be_processed_by_chain, return_exceptions=True)  # await their processing
        self._order_hash_manager = OrderHashManager(network=self._network_obj, sub_account_id=self._sub_account_id)
        await self._order_hash_manager.start()

    def _check_markets_initialized(self) -> bool:
        return (
            len(self._markets_info) != 0
            and len(self._market_id_to_active_spot_markets) != 0
            and len(self._denom_to_token_meta) != 0
        )

    async def _update_markets_loop(self):
        while True:
            await self._sleep(delay=MARKETS_UPDATE_INTERVAL)
            await self._update_markets()

    async def _update_markets(self):
        markets = await self._get_spot_markets()
        self._update_trading_pair_to_active_spot_markets(markets=markets)
        self._update_market_id_to_active_spot_markets(markets=markets)
        self._update_denom_to_token_meta(markets=markets)

    async def _get_spot_markets(self) -> MarketsResponse:
        market_status = "active"
        markets = await self._client.get_spot_markets(market_status=market_status)
        return markets

    def _update_local_balances(self, balances: Dict[str, Dict[str, Decimal]]):
        # We need to keep local copy of total and available balance so we can trigger BalanceUpdateEvent with correct
        # details. This is specifically for Injective during the processing of balance streams, where the messages does not
        # detail the total_balance and available_balance across bank and subaccounts.
        for asset_name, balance_entry in balances.items():
            if "total_balance" in balance_entry:
                self._account_balances[asset_name] = balance_entry["total_balance"]
            if "available_balance" in balance_entry:
                self._account_available_balances[asset_name] = balance_entry["available_balance"]

    def _update_market_id_to_active_spot_markets(self, markets: MarketsResponse):
        markets_dict = {market.market_id: market for market in markets.markets}
        self._market_id_to_active_spot_markets.clear()
        self._market_id_to_active_spot_markets.update(markets_dict)

    def _parse_trading_rule(self, trading_pair: str, market_info: SpotMarketInfo) -> TradingRule:
        min_price_tick_size = self._convert_price_from_backend(
            price=market_info.min_price_tick_size, market=market_info
        )
        min_quantity_tick_size = self._convert_size_from_backend(
            size=market_info.min_quantity_tick_size, market=market_info
        )
        trading_rule = TradingRule(
            trading_pair=trading_pair,
            min_order_size=min_quantity_tick_size,
            min_price_increment=min_price_tick_size,
            min_base_amount_increment=min_quantity_tick_size,
            min_quote_amount_increment=min_price_tick_size,
        )
        return trading_rule

    def _compose_spot_order_for_local_hash_computation(self, order: GatewayInFlightOrder) -> SpotOrder:
        market = self._markets_info[order.trading_pair]
        return self._composer.SpotOrder(
            market_id=market.market_id,
            subaccount_id=self._sub_account_id.lower(),
            fee_recipient=self._account_address,
            price=float(order.price),
            quantity=float(order.amount),
            is_buy=order.trade_type == TradeType.BUY,
            is_po=order.order_type == OrderType.LIMIT_MAKER,
        )

    async def get_trading_fees(self) -> Mapping[str, MakerTakerExchangeFeeRates]:
        self._check_markets_initialized() or await self._update_markets()

        trading_fees = {}
        for trading_pair, market in self._markets_info.items():
            fee_scaler = Decimal("1") - Decimal(market.service_provider_fee)
            maker_fee = Decimal(market.maker_fee_rate) * fee_scaler
            taker_fee = Decimal(market.taker_fee_rate) * fee_scaler
            trading_fees[trading_pair] = MakerTakerExchangeFeeRates(
                maker=maker_fee, taker=taker_fee, maker_flat_fees=[], taker_flat_fees=[]
            )
        return trading_fees

    async def _get_booked_order_status_update(
        self,
        trading_pair: str,
        client_order_id: str,
        order_hash: str,
        market_id: str,
        direction: str,
        creation_timestamp: float,
        order_type: OrderType,
        trade_type: TradeType,
        order_mist_updates: Dict[str, str],
    ) -> Optional[OrderUpdate]:
        order_status = await self._get_backend_order_status(
            market_id=market_id,
            order_type=order_type,
            trade_type=trade_type,
            order_hash=order_hash,
            direction=direction,
            start_time=int(creation_timestamp * 1e3),
        )

        if order_status is not None:
            status_update = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=order_status.updated_at * 1e-3,
                new_state=BACKEND_TO_CLIENT_ORDER_STATE_MAP[order_status.state],
                client_order_id=client_order_id,
                exchange_order_id=order_status.order_hash,
                misc_updates=order_mist_updates,
            )
        else:
            status_update = None

        return status_update

    def _update_trading_pair_to_active_spot_markets(self, markets: MarketsResponse):
        markets_dict = {}
        for market in markets.markets:
            trading_pair = combine_to_hb_trading_pair(
                base=market.base_token_meta.symbol, quote=market.quote_token_meta.symbol
            )
            markets_dict[trading_pair] = market
        self._markets_info.clear()
        self._markets_info.update(markets_dict)

    def _update_denom_to_token_meta(self, markets: MarketsResponse):
        self._denom_to_token_meta.clear()
        for market in markets.markets:
            if market.base_token_meta.symbol != "":  # the meta is defined
                self._denom_to_token_meta[market.base_denom] = market.base_token_meta
            if market.quote_token_meta.symbol != "":  # the meta is defined
                self._denom_to_token_meta[market.quote_denom] = market.quote_token_meta

    async def _start_streams(self):
        self._trades_stream_listener = (
            self._trades_stream_listener or safe_ensure_future(coro=self._listen_to_trades_stream())
        )
        market_ids = self._get_market_ids()
        for market_id in market_ids:
            if market_id not in self._order_listeners:
                self._order_listeners[market_id] = safe_ensure_future(
                    coro=self._listen_to_orders_stream(market_id=market_id)
                )
        self._order_books_stream_listener = (
            self._order_books_stream_listener or safe_ensure_future(coro=self._listen_to_order_books_stream())
        )
        if self._is_default_subaccount:
            self._bank_balances_stream_listener = (
                self._bank_balances_stream_listener or safe_ensure_future(coro=self._listen_to_bank_balances_streams())
            )
        self._subaccount_balances_stream_listener = self._subaccount_balances_stream_listener or safe_ensure_future(
            coro=self._listen_to_subaccount_balances_stream()
        )
        self._transactions_stream_listener = self._transactions_stream_listener or safe_ensure_future(
            coro=self._listen_to_transactions_stream()
        )

    async def _stop_streams(self):
        self._trades_stream_listener and self._trades_stream_listener.cancel()
        self._trades_stream_listener = None
        for listener in self._order_listeners.values():
            listener.cancel()
        self._order_listeners = {}
        self._order_books_stream_listener and self._order_books_stream_listener.cancel()
        self._order_books_stream_listener = None
        self._subaccount_balances_stream_listener and self._subaccount_balances_stream_listener.cancel()
        self._subaccount_balances_stream_listener = None
        self._bank_balances_stream_listener and self._bank_balances_stream_listener.cancel()
        self._bank_balances_stream_listener = None
        self._transactions_stream_listener and self._transactions_stream_listener.cancel()
        self._transactions_stream_listener = None

    async def _listen_to_trades_stream(self):
        while True:
            market_ids: List[str] = self._get_market_ids()
            stream: UnaryStreamCall = await self._client.stream_spot_trades(market_ids=market_ids)
            try:
                async for trade_msg in stream:
                    self._process_trade_stream_event(message=trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in public trade listener loop.")
            self.logger().info("Restarting public trades stream.")
            stream.cancel()

    def _process_trade_stream_event(self, message: StreamTradesResponse):
        trade_message: SpotTrade = message.trade
        exchange_order_id = trade_message.order_hash
        tracked_order = self._gateway_order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)
        client_order_id = "" if tracked_order is None else tracked_order.client_order_id
        trade_ob_msg, trade_update = self._parse_backend_trade(
            client_order_id=client_order_id, backend_trade=trade_message
        )

        self._publisher.trigger_event(event_tag=OrderBookDataSourceEvent.TRADE_EVENT, message=trade_ob_msg)
        self._publisher.trigger_event(event_tag=MarketEvent.TradeUpdate, message=trade_update)

    async def _listen_to_orders_stream(self, market_id: str):
        while True:
            stream: UnaryStreamCall = await self._client.stream_historical_spot_orders(market_id=market_id)
            try:
                async for order in stream:
                    self._parse_order_stream_update(order=order)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
            self.logger().info("Restarting orders stream.")
            stream.cancel()

    def _parse_order_stream_update(self, order: StreamOrdersResponse):
        order_hash = order.order.order_hash
        in_flight_order = self._gateway_order_tracker.all_fillable_orders_by_exchange_order_id.get(order_hash)
        if in_flight_order is not None:
            market_id = order.order.market_id
            trading_pair = self._get_trading_pair_from_market_id(market_id=market_id)
            order_update = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=order.order.updated_at * 1e-3,
                new_state=BACKEND_TO_CLIENT_ORDER_STATE_MAP[order.order.state],
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=order.order.order_hash,
            )
            if in_flight_order.current_state == OrderState.PENDING_CREATE and order_update.new_state != OrderState.OPEN:
                open_update = OrderUpdate(
                    trading_pair=trading_pair,
                    update_timestamp=order.order.updated_at * 1e-3,
                    new_state=OrderState.OPEN,
                    client_order_id=in_flight_order.client_order_id,
                    exchange_order_id=order.order.order_hash,
                )
                self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=open_update)
            self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=order_update)

    async def _listen_to_order_books_stream(self):
        while True:
            market_ids = self._get_market_ids()
            stream: UnaryStreamCall = await self._client.stream_spot_orderbook_snapshot(market_ids=market_ids)
            try:
                async for order_book_update in stream:
                    self._parse_order_book_event(order_book_update=order_book_update)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
            self.logger().info("Restarting order books stream.")
            stream.cancel()

    def _parse_order_book_event(self, order_book_update: StreamOrderbookV2Response):
        udpate_timestamp_ms = order_book_update.timestamp
        market_id = order_book_update.market_id
        trading_pair = self._get_trading_pair_from_market_id(market_id=market_id)
        market = self._market_id_to_active_spot_markets[market_id]
        price_scale = self._get_backend_price_scaler(market=market)
        size_scale = self._get_backend_denom_scaler(denom_meta=market.base_token_meta)
        bids = [
            (Decimal(bid.price) * price_scale, Decimal(bid.quantity) * size_scale)
            for bid in order_book_update.orderbook.buys
        ]
        asks = [
            (Decimal(ask.price) * price_scale, Decimal(ask.quantity) * size_scale)
            for ask in order_book_update.orderbook.sells
        ]
        snapshot_msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": udpate_timestamp_ms,
                "bids": bids,
                "asks": asks,
            },
            timestamp=udpate_timestamp_ms * 1e-3,
        )
        self._publisher.trigger_event(event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, message=snapshot_msg)

    def _parse_bank_balance_message(self, message: StreamAccountPortfolioResponse) -> BalanceUpdateEvent:
        denom_meta: TokenMeta = self._denom_to_token_meta[message.denom]
        denom_scaler: Decimal = Decimal(f"1e-{denom_meta.decimals}")

        available_balance: Decimal = Decimal(message.amount) * denom_scaler
        total_balance: Decimal = available_balance

        balance_msg = BalanceUpdateEvent(
            timestamp=self._time(),
            asset_name=denom_meta.symbol,
            total_balance=total_balance,
            available_balance=available_balance,
        )
        self._update_local_balances(
            balances={denom_meta.symbol: {"total_balance": total_balance, "available_balance": available_balance}}
        )
        return balance_msg

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
            stream: UnaryStreamCall = await self._client.stream_subaccount_balance(subaccount_id=self._sub_account_id)
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

    async def _get_backend_order_status(
        self,
        market_id: str,
        order_type: OrderType,
        trade_type: TradeType,
        order_hash: Optional[str] = None,
        direction: Optional[str] = None,
        start_time: Optional[int] = None,
    ) -> Optional[SpotOrderHistory]:
        skip = 0
        order_status = None
        search_completed = False

        while not search_completed:
            response = await self._client.get_historical_spot_orders(
                market_id=market_id,
                subaccount_id=self._sub_account_id,
                direction=direction,
                start_time=start_time,
                skip=skip,
                order_types=[CLIENT_TO_BACKEND_ORDER_TYPES_MAP[(trade_type, order_type)]]
            )
            if len(response.orders) == 0:
                search_completed = True
            else:
                skip += REQUESTS_SKIP_STEP
                for response_order in response.orders:
                    if response_order.order_hash == order_hash:
                        order_status = response_order
                        search_completed = True
                        break

        return order_status

    async def _get_all_trades(
        self,
        market_id: str,
        direction: str,
        created_at: int,
        updated_at: int,
    ) -> List[SpotTrade]:
        skip = 0
        all_trades = []
        search_completed = False

        while not search_completed:
            trades = await self._client.get_spot_trades(
                market_id=market_id,
                subaccount_id=self._sub_account_id,
                direction=direction,
                skip=skip,
                start_time=created_at,
            )
            if len(trades.trades) == 0:
                search_completed = True
            else:
                all_trades.extend(trades.trades)
                skip += len(trades.trades)

        return all_trades

    def _parse_backend_trade(
            self, client_order_id: str, backend_trade: SpotTrade
    ) -> Tuple[OrderBookMessage, TradeUpdate]:
        exchange_order_id: str = backend_trade.order_hash
        market = self._market_id_to_active_spot_markets[backend_trade.market_id]
        trading_pair = self._get_trading_pair_from_market_id(market_id=backend_trade.market_id)
        trade_id: str = backend_trade.trade_id

        price = self._convert_price_from_backend(price=backend_trade.price.price, market=market)
        size = self._convert_size_from_backend(size=backend_trade.price.quantity, market=market)
        trade_type = TradeType.BUY if backend_trade.trade_direction == "buy" else TradeType.SELL
        is_taker: bool = backend_trade.execution_side == "taker"

        fee_amount = self._convert_quote_from_backend(quote_amount=backend_trade.fee, market=market)
        _, quote = split_hb_trading_pair(trading_pair=trading_pair)
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=TradeFeeSchema(),
            trade_type=trade_type,
            flat_fees=[TokenAmount(amount=fee_amount, token=quote)]
        )

        trade_msg_content = {
            "trade_id": trade_id,
            "trading_pair": trading_pair,
            "trade_type": trade_type,
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

    async def _listen_to_transactions_stream(self):
        while True:
            stream: UnaryStreamCall = await self._client.stream_txs()
            try:
                async for transaction in stream:
                    await self._parse_transaction_event(transaction=transaction)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
            self.logger().info("Restarting transactions stream.")
            stream.cancel()

    async def _parse_transaction_event(self, transaction: StreamTxsResponse):
        order = self._gateway_order_tracker.get_fillable_order_by_hash(transaction_hash=transaction.hash)
        if order is not None:
            messages = json.loads(s=transaction.messages)
            for message in messages:
                if message["type"] in [MSG_CREATE_SPOT_LIMIT_ORDER, MSG_CANCEL_SPOT_ORDER, MSG_BATCH_UPDATE_ORDERS]:
                    safe_ensure_future(coro=self.get_order_status_update(in_flight_order=order))

    def _get_trading_pair_from_market_id(self, market_id: str) -> str:
        market = self._market_id_to_active_spot_markets[market_id]
        trading_pair = combine_to_hb_trading_pair(
            base=market.base_token_meta.symbol, quote=market.quote_token_meta.symbol
        )
        return trading_pair

    def _get_exchange_trading_pair_from_market_info(self, market_info: Any) -> str:
        return market_info.market_id

    def _get_maker_taker_exchange_fee_rates_from_market_info(self, market_info: Any) -> MakerTakerExchangeFeeRates:
        fee_scaler = Decimal("1") - Decimal(market_info.service_provider_fee)
        maker_fee = Decimal(market_info.maker_fee_rate) * fee_scaler
        taker_fee = Decimal(market_info.taker_fee_rate) * fee_scaler
        return MakerTakerExchangeFeeRates(
            maker=maker_fee, taker=taker_fee, maker_flat_fees=[], taker_flat_fees=[]
        )

    def _convert_price_from_backend(self, price: str, market: SpotMarketInfo) -> Decimal:
        scale = self._get_backend_price_scaler(market=market)
        scaled_price = Decimal(price) * scale
        return scaled_price

    async def _get_transaction_by_hash(self, transaction_hash: str) -> GetTxByTxHashResponse:
        return await self._client.get_tx_by_hash(tx_hash=transaction_hash)

    def _get_market_ids(self) -> List[str]:
        market_ids = [
            self._markets_info[trading_pair].market_id
            for trading_pair in self._trading_pairs
        ]
        return market_ids

    async def _check_if_order_failed_based_on_transaction(self, transaction: GetTxByTxHashResponse,
                                                          order: GatewayInFlightOrder) -> bool:
        order_hash = await order.get_exchange_order_id()
        return order_hash.lower() not in transaction.data.data.decode().lower()

    @staticmethod
    def _get_backend_price_scaler(market: SpotMarketInfo) -> Decimal:
        scale = Decimal(f"1e{market.base_token_meta.decimals - market.quote_token_meta.decimals}")
        return scale

    def _convert_quote_from_backend(self, quote_amount: str, market: SpotMarketInfo) -> Decimal:
        scale = self._get_backend_denom_scaler(denom_meta=market.quote_token_meta)
        scaled_quote_amount = Decimal(quote_amount) * scale
        return scaled_quote_amount

    def _convert_size_from_backend(self, size: str, market: SpotMarketInfo) -> Decimal:
        scale = self._get_backend_denom_scaler(denom_meta=market.base_token_meta)
        size_tick_size = Decimal(market.min_quantity_tick_size) * scale
        scaled_size = Decimal(size) * scale
        return self._floor_to(scaled_size, size_tick_size)

    @staticmethod
    def _get_backend_denom_scaler(denom_meta: TokenMeta):
        scale = Decimal(f"1e{-denom_meta.decimals}")
        return scale

    @staticmethod
    def _floor_to(value: Decimal, target: Decimal) -> Decimal:
        result = int(floor(value / target)) * target
        return result

    @staticmethod
    def _get_backend_order_type(in_flight_order: InFlightOrder) -> str:
        return CLIENT_TO_BACKEND_ORDER_TYPES_MAP[(in_flight_order.trade_type, in_flight_order.order_type)]

    @staticmethod
    async def _sleep(delay: float):
        await asyncio.sleep(delay)

    @staticmethod
    def _time() -> float:
        return time.time()

    def _get_gateway_instance(self) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        return gateway_instance
