import asyncio
import copy
from asyncio import Task
from enum import Enum
from time import time
from typing import Any, Dict, List, Optional, Tuple

import jsonpickle
from _decimal import Decimal
from dotmap import DotMap

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)
from hummingbot.connector.gateway.clob_spot.data_sources.kujira.kujira_constants import (
    CONNECTOR,
    DELAY_BETWEEN_RETRIES,
    KUJIRA_NATIVE_TOKEN,
    MARKETS_UPDATE_INTERVAL,
    NUMBER_OF_RETRIES,
    TIMEOUT,
    UPDATE_ORDER_STATUS_INTERVAL,
)
from hummingbot.connector.gateway.clob_spot.data_sources.kujira.kujira_helpers import (
    AsyncLock,
    automatic_retry_with_timeout,
    convert_market_name_to_hb_trading_pair,
    generate_hash,
)
from hummingbot.connector.gateway.clob_spot.data_sources.kujira.kujira_types import OrderStatus as KujiraOrderStatus
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type import in_flight_order
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates, TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.events import AccountEvent, MarketEvent, OrderBookDataSourceEvent, OrderCancelledEvent
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather


class KujiraAPIDataSource(GatewayCLOBAPIDataSourceBase):

    def __init__(
        self,
        trading_pairs: List[str],
        connector_spec: Dict[str, Any],
        client_config_map: ClientConfigAdapter,
    ):
        super().__init__(
            trading_pairs=trading_pairs,
            connector_spec=connector_spec,
            client_config_map=client_config_map
        )

        self._chain = connector_spec["chain"]
        self._network = connector_spec["network"]
        self._connector = CONNECTOR
        self._owner_address = connector_spec["wallet_address"]
        self._payer_address = self._owner_address

        self._markets = None

        self._user_balances = None

        self._tasks = DotMap({
            "update_order_status_loop": None
        }, _dynamic=False)

        self._locks = DotMap({
            "place_order": AsyncLock(),
            "place_orders": AsyncLock(),
            "cancel_order": AsyncLock(),
            "cancel_orders": AsyncLock(),
            "settle_market_funds": AsyncLock(),
            "settle_markets_funds": AsyncLock(),
            "settle_all_markets_funds": AsyncLock(),
            "all_active_orders": AsyncLock(),
        }, _dynamic=False)

        self._gateway = GatewayHttpClient.get_instance(self._client_config)

        self._all_active_orders = None

        self._snapshots_min_update_interval = 30
        self._snapshots_max_update_interval = 60
        self.cancel_all_orders_timeout = TIMEOUT

    @property
    def connector_name(self) -> str:
        return CONNECTOR

    @property
    def real_time_balance_update(self) -> bool:
        return False

    @property
    def events_are_streamed(self) -> bool:
        return False

    @staticmethod
    def supported_stream_events() -> List[Enum]:
        return [
            MarketEvent.TradeUpdate,
            MarketEvent.OrderUpdate,
            MarketEvent.OrderFilled,
            AccountEvent.BalanceEvent,
            OrderBookDataSourceEvent.TRADE_EVENT,
            OrderBookDataSourceEvent.DIFF_EVENT,
            OrderBookDataSourceEvent.SNAPSHOT_EVENT,
        ]

    def get_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    @automatic_retry_with_timeout(retries=NUMBER_OF_RETRIES, delay=DELAY_BETWEEN_RETRIES, timeout=TIMEOUT)
    async def start(self):
        self.logger().setLevel("INFO")
        self.logger().debug("start: start")

        await super().start()

        self._tasks.update_order_status_loop = self._tasks.update_order_status_loop \
            or safe_ensure_future(
                coro=self._update_all_active_orders()
            )

        self.logger().debug("start: end")

    @automatic_retry_with_timeout(retries=NUMBER_OF_RETRIES, delay=DELAY_BETWEEN_RETRIES, timeout=TIMEOUT)
    async def stop(self):
        self.logger().debug("stop: start")

        await super().stop()

        self._tasks.update_order_status_loop and self._tasks.update_order_status_loop.cancel()
        self._tasks.update_order_status_loop = None

        self.logger().debug("stop: end")

    async def place_order(self, order: GatewayInFlightOrder, **kwargs) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        self.logger().debug("place_order: start")

        self._check_markets_initialized() or await self._update_markets()

        async with self._locks.place_order:
            try:
                request = {
                    "connector": self._connector,
                    "chain": self._chain,
                    "network": self._network,
                    "trading_pair": order.trading_pair,
                    "address": self._owner_address,
                    "trade_type": order.trade_type,
                    "order_type": order.order_type,
                    "price": order.price,
                    "size": order.amount,
                    "client_order_id": order.client_order_id,
                }

                self.logger().debug(f"""clob_place_order request:\n "{self._dump(request)}".""")

                response = await self._gateway_clob_place_order(request)

                self.logger().debug(f"""clob_place_order response:\n "{self._dump(response)}".""")

                transaction_hash = response["txHash"]

                order.exchange_order_id = response["id"]

                order.current_state = OrderState.CREATED

                self.logger().info(
                    f"""Order "{order.client_order_id}" / "{order.exchange_order_id}" successfully placed. Transaction hash: "{transaction_hash}"."""
                )
            except Exception as exception:
                self.logger().info(
                    f"""Placement of order "{order.client_order_id}" failed."""
                )

                raise exception

            if transaction_hash in (None, ""):
                raise Exception(
                    f"""Placement of order "{order.client_order_id}" failed. Invalid transaction hash: "{transaction_hash}"."""
                )

        misc_updates = DotMap({
            "creation_transaction_hash": transaction_hash,
        }, _dynamic=False)

        self.logger().debug("place_order: end")

        await self._update_order_status()

        return order.exchange_order_id, misc_updates

    async def batch_order_create(self, orders_to_create: List[GatewayInFlightOrder]) -> List[PlaceOrderResult]:
        self.logger().debug("batch_order_create: start")

        self._check_markets_initialized() or await self._update_markets()

        candidate_orders = [in_flight_order]
        client_ids = []
        for order_to_create in orders_to_create:
            if not order_to_create.client_order_id:
                order_to_create.client_order_id = generate_hash(order_to_create)
            client_ids.append(order_to_create.client_order_id)

            candidate_order = in_flight_order.InFlightOrder(
                amount=order_to_create.amount,
                client_order_id=order_to_create.client_order_id,
                creation_timestamp=0,
                order_type=order_to_create.order_type,
                trade_type=order_to_create.trade_type,
                trading_pair=order_to_create.trading_pair,
            )
            candidate_orders.append(candidate_order)

        async with self._locks.place_orders:
            try:
                request = {
                    "connector": self._connector,
                    "chain": self._chain,
                    "network": self._network,
                    "address": self._owner_address,
                    "orders_to_create": candidate_orders,
                    "orders_to_cancel": [],
                }

                self.logger().debug(f"""clob_batch_order_modify request:\n "{self._dump(request)}".""")

                response = await self._gateway_clob_batch_order_modify(request)

                self.logger().debug(f"""clob_batch_order_modify response:\n "{self._dump(response)}".""")

                transaction_hash = response["txHash"]

                self.logger().info(
                    f"""Orders "{client_ids}" successfully placed. Transaction hash: {transaction_hash}."""
                )
            except Exception as exception:
                self.logger().info(
                    f"""Placement of orders "{client_ids}" failed."""
                )

                raise exception

            if transaction_hash in (None, ""):
                raise RuntimeError(
                    f"""Placement of orders "{client_ids}" failed. Invalid transaction hash: "{transaction_hash}"."""
                )

        place_order_results = []
        for order_to_create, exchange_order_id in zip(orders_to_create, response["ids"]):
            order_to_create.exchange_order_id = None

            place_order_results.append(PlaceOrderResult(
                update_timestamp=time(),
                client_order_id=order_to_create.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=order_to_create.trading_pair,
                misc_updates={
                    "creation_transaction_hash": transaction_hash,
                },
                exception=None,
            ))

        self.logger().debug("batch_order_create: end")

        return place_order_results

    async def cancel_order(self, order: GatewayInFlightOrder) -> Tuple[bool, Optional[Dict[str, Any]]]:
        active_order = self._gateway_order_tracker.active_orders.get(order.client_order_id)

        if active_order.exchange_order_id is None:
            await self._update_order_status()
            active_order = self._gateway_order_tracker.active_orders.get(order.client_order_id)

        fillable = self._gateway_order_tracker.all_fillable_orders_by_exchange_order_id.get(
            active_order.exchange_order_id
        )

        if fillable and (
                active_order
        ) and (
                active_order.current_state != OrderState.CANCELED
        ) and (
                active_order.current_state != OrderState.FILLED
        ) and (
                active_order.exchange_order_id
        ):
            self.logger().debug("cancel_order: start")

            self._check_markets_initialized() or await self._update_markets()

            await order.get_exchange_order_id()

            transaction_hash = None

            async with self._locks.cancel_order:
                try:
                    request = {
                        "connector": self._connector,
                        "chain": self._chain,
                        "network": self._network,
                        "trading_pair": order.trading_pair,
                        "address": self._owner_address,
                        "exchange_order_id": order.exchange_order_id,
                    }

                    self.logger().debug(f"""clob_cancel_order request:\n "{self._dump(request)}".""")

                    response = await self._gateway_clob_cancel_order(request)

                    self.logger().debug(f"""clob_cancel_order response:\n "{self._dump(response)}".""")

                    transaction_hash = response["txHash"]

                    if transaction_hash in ("", None):
                        return False, DotMap({}, _dynamic=False)

                    self.logger().info(
                        f"""Order "{order.client_order_id}" / "{order.exchange_order_id}" successfully cancelled. Transaction hash: "{transaction_hash}"."""
                    )
                except Exception as exception:
                    # await self.gateway_order_tracker.process_order_not_found(order.client_order_id)
                    if f"""Order "{order.exchange_order_id}" not found on markets""" in str(exception.args):
                        # order_update = self.get_order_status_update(order)
                        # self.gateway_order_tracker.process_order_update(order_update)

                        self.logger().info(
                            f"""Order "{order.exchange_order_id}" not found on markets"""
                        )

                        return True, DotMap({}, _dynamic=False)

                    elif 'No orders with the specified information exist' in str(exception.args):
                        self.logger().info(
                            f"""Order "{order.client_order_id}" / "{order.exchange_order_id}" already cancelled."""
                        )

                        transaction_hash = "0000000000000000000000000000000000000000000000000000000000000000"  # noqa: mock
                    else:
                        self.logger().info(
                            f"""Cancellation of order "{order.client_order_id}" / "{order.exchange_order_id}" failed."""
                        )

                        raise exception

            misc_updates = DotMap({
                "cancelation_transaction_hash": transaction_hash,
            }, _dynamic=False)

            self.logger().debug("cancel_order: end")

            order.cancel_tx_hash = transaction_hash

            await self._update_order_status()

            return True, misc_updates

        return False, DotMap({}, _dynamic=False)

    async def batch_order_cancel(self, orders_to_cancel: List[GatewayInFlightOrder]) -> List[CancelOrderResult]:
        self.logger().debug("batch_order_cancel: start")

        self._check_markets_initialized() or await self._update_markets()

        client_ids = [order.client_order_id for order in orders_to_cancel]

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

        ids = [order.exchange_order_id for order in found_orders_to_cancel]

        async with self._locks.cancel_orders:
            try:

                request = {
                    "connector": self._connector,
                    "chain": self._chain,
                    "network": self._network,
                    "address": self._owner_address,
                    "orders_to_create": [],
                    "orders_to_cancel": found_orders_to_cancel,
                }

                self.logger().debug(f"""clob_batch_order_moodify request:\n "{self._dump(request)}".""")

                response = await self._gateway_clob_batch_order_modify(request)

                self.logger().debug(f"""clob_batch_order_modify response:\n "{self._dump(response)}".""")

                transaction_hash = response["txHash"]

                self.logger().info(
                    f"""Orders "{client_ids}" / "{ids}" successfully cancelled. Transaction hash(es): "{transaction_hash}"."""
                )
            except Exception as exception:
                self.logger().info(
                    f"""Cancellation of orders "{client_ids}" / "{ids}" failed."""
                )

                raise exception

            if transaction_hash in (None, ""):
                raise RuntimeError(
                    f"""Cancellation of orders "{client_ids}" / "{ids}" failed. Invalid transaction hash: "{transaction_hash}"."""
                )

        cancel_order_results = []
        for order_to_cancel in orders_to_cancel:
            cancel_order_results.append(CancelOrderResult(
                client_order_id=order_to_cancel.client_order_id,
                trading_pair=order_to_cancel.trading_pair,
                misc_updates={
                    "cancelation_transaction_hash": transaction_hash
                },
                exception=None,
            ))

        self.logger().debug("batch_order_cancel: end")

        return cancel_order_results

    async def get_last_traded_price(self, trading_pair: str) -> Decimal:
        self.logger().debug("get_last_traded_price: start")

        request = {
            "connector": self._connector,
            "chain": self._chain,
            "network": self._network,
            "trading_pair": trading_pair,
        }

        self.logger().debug(f"""get_clob_ticker request:\n "{self._dump(request)}".""")

        response = await self._gateway_get_clob_ticker(request)

        self.logger().debug(f"""get_clob_ticker response:\n "{self._dump(response)}".""")

        ticker = DotMap(response, _dynamic=False).markets[trading_pair]

        ticker_price = Decimal(ticker.price)

        self.logger().debug("get_last_traded_price: end")

        return ticker_price

    async def get_order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        self.logger().debug("get_order_book_snapshot: start")

        request = {
            "trading_pair": trading_pair,
            "connector": self._connector,
            "chain": self._chain,
            "network": self._network,
        }

        self.logger().debug(f"""get_clob_orderbook_snapshot request:\n "{self._dump(request)}".""")

        response = await self._gateway_get_clob_orderbook_snapshot(request)

        self.logger().debug(f"""get_clob_orderbook_snapshot response:\n "{self._dump(response)}".""")

        order_book = DotMap(response, _dynamic=False)

        price_scale = 1
        size_scale = 1

        timestamp = time()

        bids = []
        asks = []
        for bid in order_book.buys:
            bids.append((Decimal(bid.price) * price_scale, Decimal(bid.quantity) * size_scale))

        for ask in order_book.sells:
            asks.append((Decimal(ask.price) * price_scale, Decimal(ask.quantity) * size_scale))

        snapshot = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": timestamp,
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp
        )

        self.logger().debug("get_order_book_snapshot: end")

        return snapshot

    async def get_account_balances(self) -> Dict[str, Dict[str, Decimal]]:
        self.logger().debug("get_account_balances: start")

        if self._trading_pairs:
            token_symbols = []

            for trading_pair in self._trading_pairs:
                symbols = trading_pair.split("-")[0], trading_pair.split("-")[1]
                for symbol in symbols:
                    token_symbols.append(symbol)

            token_symbols.append(KUJIRA_NATIVE_TOKEN.symbol)

            request = {
                "chain": self._chain,
                "network": self._network,
                "address": self._owner_address,
                "connector": self._connector,
                "token_symbols": list(set(token_symbols))
            }
        else:
            request = {
                "chain": self._chain,
                "network": self._network,
                "address": self._owner_address,
                "connector": self._connector,
                "token_symbols": []
            }

        # self.logger().debug(f"""get_balances request:\n "{self._dump(request)}".""")

        response = await self._gateway_get_balances(request)

        self.logger().debug(f"""get_balances response:\n "{self._dump(response)}".""")

        balances = DotMap(response, _dynamic=False).balances

        hb_balances = {}
        for token, balance in balances.items():
            balance = Decimal(balance)
            hb_balances[token] = DotMap({}, _dynamic=False)
            hb_balances[token]["total_balance"] = balance
            hb_balances[token]["available_balance"] = balance

        # self.logger().debug("get_account_balances: end")

        return hb_balances

    async def get_order_status_update(self, in_flight_order: GatewayInFlightOrder) -> OrderUpdate:
        active_order = self.gateway_order_tracker.active_orders.get(in_flight_order.client_order_id)

        if active_order:
            self.logger().debug("get_order_status_update: start")

            if active_order.current_state != OrderState.CANCELED:
                await in_flight_order.get_exchange_order_id()

                request = {
                    "trading_pair": in_flight_order.trading_pair,
                    "chain": self._chain,
                    "network": self._network,
                    "connector": self._connector,
                    "address": self._owner_address,
                    "exchange_order_id": in_flight_order.exchange_order_id,
                }

                self.logger().debug(f"""get_clob_order_status_updates request:\n "{self._dump(request)}".""")

                response = await self._gateway_get_clob_order_status_updates(request)

                self.logger().debug(f"""get_clob_order_status_updates response:\n "{self._dump(response)}".""")

                order_response = DotMap(response, _dynamic=False)["orders"]
                order_update: OrderUpdate
                if order_response:
                    order = order_response[0]
                    if order:
                        order_status = KujiraOrderStatus.to_hummingbot(KujiraOrderStatus.from_name(order.state))
                    else:
                        order_status = in_flight_order.current_state

                    open_update = OrderUpdate(
                        trading_pair=in_flight_order.trading_pair,
                        update_timestamp=time(),
                        new_state=order_status,
                        client_order_id=in_flight_order.client_order_id,
                        exchange_order_id=in_flight_order.exchange_order_id,
                        misc_updates={
                            "creation_transaction_hash": in_flight_order.creation_transaction_hash,
                            "cancelation_transaction_hash": in_flight_order.cancel_tx_hash,
                        },
                    )

                    order_update = open_update
                else:
                    canceled_update = OrderUpdate(
                        trading_pair=in_flight_order.trading_pair,
                        update_timestamp=time(),
                        new_state=OrderState.CANCELED,
                        client_order_id=in_flight_order.client_order_id,
                        exchange_order_id=in_flight_order.exchange_order_id,
                        misc_updates={
                            "creation_transaction_hash": in_flight_order.creation_transaction_hash,
                            "cancelation_transaction_hash": in_flight_order.cancel_tx_hash,
                        },
                    )

                    order_update = canceled_update

                self.logger().debug("get_order_status_update: end")
                return order_update

        no_update = OrderUpdate(
            trading_pair=in_flight_order.trading_pair,
            update_timestamp=time(),
            new_state=in_flight_order.current_state,
            client_order_id=in_flight_order.client_order_id,
            exchange_order_id=in_flight_order.exchange_order_id,
            misc_updates={
                "creation_transaction_hash": in_flight_order.creation_transaction_hash,
                "cancelation_transaction_hash": in_flight_order.cancel_tx_hash,
            },
        )
        self.logger().debug("get_order_status_update: end")
        return no_update

    async def get_all_order_fills(self, in_flight_order: GatewayInFlightOrder) -> List[TradeUpdate]:
        if in_flight_order.exchange_order_id:
            active_order = self.gateway_order_tracker.active_orders.get(in_flight_order.client_order_id)

            if active_order:
                if active_order.current_state != OrderState.CANCELED:
                    self.logger().debug("get_all_order_fills: start")

                    trade_update = None

                    request = {
                        "trading_pair": in_flight_order.trading_pair,
                        "chain": self._chain,
                        "network": self._network,
                        "connector": self._connector,
                        "address": self._owner_address,
                        "exchange_order_id": in_flight_order.exchange_order_id,
                    }

                    self.logger().debug(f"""get_clob_order_status_updates request:\n "{self._dump(request)}".""")

                    response = await self._gateway_get_clob_order_status_updates(request)

                    self.logger().debug(f"""get_clob_order_status_updates response:\n "{self._dump(response)}".""")

                    orders = DotMap(response, _dynamic=False)["orders"]

                    order = None
                    if len(orders):
                        order = orders[0]

                    if order is not None:
                        order_status = KujiraOrderStatus.to_hummingbot(KujiraOrderStatus.from_name(order.state))
                    else:
                        order_status = in_flight_order.current_state

                    if order and order_status == OrderState.FILLED:
                        timestamp = time()
                        trade_id = str(timestamp)

                        market = self._markets_info[in_flight_order.trading_pair]

                        trade_update = TradeUpdate(
                            trade_id=trade_id,
                            client_order_id=in_flight_order.client_order_id,
                            exchange_order_id=in_flight_order.exchange_order_id,
                            trading_pair=in_flight_order.trading_pair,
                            fill_timestamp=timestamp,
                            fill_price=in_flight_order.price,
                            fill_base_amount=in_flight_order.amount,
                            fill_quote_amount=in_flight_order.price * in_flight_order.amount,
                            fee=TradeFeeBase.new_spot_fee(
                                fee_schema=TradeFeeSchema(),
                                trade_type=in_flight_order.trade_type,
                                flat_fees=[TokenAmount(
                                    amount=Decimal(market.fees.taker),
                                    token=market.quoteToken.symbol
                                )]
                            ),
                        )

                    self.logger().debug("get_all_order_fills: end")

                    if trade_update:
                        return [trade_update]

        return []

    def _get_trading_pair_from_market_info(self, market_info: Dict[str, Any]) -> str:
        return market_info["hb_trading_pair"]

    def _get_exchange_base_quote_tokens_from_market_info(self, market_info: Dict[str, Any]) -> Tuple[str, str]:
        base = market_info["baseToken"]["symbol"]
        quote = market_info["quoteToken"]["symbol"]

        return base, quote

    def _get_last_trade_price_from_ticker_data(self, ticker_data: List[Dict[str, Any]]) -> Decimal:
        raise NotImplementedError

    def is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        self.logger().debug("is_order_not_found_during_status_update_error: start")

        output = str(status_update_exception).startswith("No update found for order")

        self.logger().debug("is_order_not_found_during_status_update_error: end")

        return output

    def is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        self.logger().debug("is_order_not_found_during_cancelation_error: start")

        output = False

        self.logger().debug("is_order_not_found_during_cancelation_error: end")

        return output

    async def check_network_status(self) -> NetworkStatus:
        # self.logger().debug("check_network_status: start")

        try:
            status = await self._gateway_ping_gateway()

            if status:
                return NetworkStatus.CONNECTED
            else:
                return NetworkStatus.NOT_CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            self.logger().error(exception)

            return NetworkStatus.NOT_CONNECTED

        # self.logger().debug("check_network_status: end")

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        self.logger().debug("is_cancel_request_in_exchange_synchronous: start")

        output = True

        self.logger().debug("is_cancel_request_in_exchange_synchronous: end")

        return output

    def _check_markets_initialized(self) -> bool:
        # self.logger().debug("_check_markets_initialized: start")

        output = self._markets is not None and bool(self._markets)

        # self.logger().debug("_check_markets_initialized: end")

        return output

    async def _update_markets(self):
        self.logger().debug("_update_markets: start")

        if self._markets_info:
            self._markets_info.clear()

        all_markets_map = DotMap()

        if self._trading_pairs:
            for trading_pair in self._trading_pairs:
                request = {
                    "connector": self._connector,
                    "chain": self._chain,
                    "network": self._network,
                    "trading_pair": trading_pair
                }

                self.logger().debug(f"""get_clob_markets request:\n "{self._dump(request)}".""")

                response = await self._gateway_get_clob_markets(request)

                self.logger().debug(f"""get_clob_markets response:\n "{self._dump(response)}".""")

                market = DotMap(response, _dynamic=False).markets[trading_pair]
                market["hb_trading_pair"] = convert_market_name_to_hb_trading_pair(market.name)
                all_markets_map[trading_pair] = market
                self._markets_info[market["hb_trading_pair"]] = market
        else:
            request = {
                "connector": self._connector,
                "chain": self._chain,
                "network": self._network,
            }

            self.logger().debug(f"""get_clob_markets request:\n "{self._dump(request)}".""")

            response = await self._gateway_get_clob_markets(request)

            self.logger().debug(f"""get_clob_markets response:\n "{self._dump(response)}".""")

            self._markets = DotMap(response, _dynamic=False).markets

            for market in self._markets.values():
                market["hb_trading_pair"] = convert_market_name_to_hb_trading_pair(market.name)
                all_markets_map[market.name] = market
                self._markets_info[market["hb_trading_pair"]] = market

        self._markets = all_markets_map

        self.logger().debug("_update_markets: end")

        return self._markets

    def _parse_trading_rule(self, trading_pair: str, market_info: Any) -> TradingRule:
        self.logger().debug("_parse_trading_rule: start")

        trading_rule = TradingRule(
            trading_pair=trading_pair,
            min_order_size=Decimal(market_info.minimumOrderSize),
            min_price_increment=Decimal(market_info.minimumPriceIncrement),
            min_base_amount_increment=Decimal(market_info.minimumBaseAmountIncrement),
            min_quote_amount_increment=Decimal(market_info.minimumQuoteAmountIncrement),
        )

        self.logger().debug("_parse_trading_rule: end")

        return trading_rule

    def _get_exchange_trading_pair_from_market_info(self, market_info: Any) -> str:
        self.logger().debug("_get_exchange_trading_pair_from_market_info: start")

        output = market_info.id

        self.logger().debug("_get_exchange_trading_pair_from_market_info: end")

        return output

    def _get_maker_taker_exchange_fee_rates_from_market_info(self, market_info: Any) -> MakerTakerExchangeFeeRates:
        self.logger().debug("_get_maker_taker_exchange_fee_rates_from_market_info: start")

        fee_scaler = Decimal("1") - Decimal(market_info.fees.serviceProvider)
        maker_fee = Decimal(market_info.fees.maker) * fee_scaler
        taker_fee = Decimal(market_info.fees.taker) * fee_scaler

        output = MakerTakerExchangeFeeRates(
            maker=maker_fee,
            taker=taker_fee,
            maker_flat_fees=[],
            taker_flat_fees=[]
        )

        self.logger().debug("_get_maker_taker_exchange_fee_rates_from_market_info: end")

        return output

    async def _update_markets_loop(self):
        self.logger().debug("_update_markets_loop: start")

        while True:
            self.logger().debug("_update_markets_loop: start loop")

            await self._update_markets()
            await asyncio.sleep(MARKETS_UPDATE_INTERVAL)

            self.logger().debug("_update_markets_loop: end loop")

    async def _check_if_order_failed_based_on_transaction(
        self,
        transaction: Any,
        order: GatewayInFlightOrder
    ) -> bool:
        order_id = await order.get_exchange_order_id()

        return order_id.lower() not in transaction.data.lower()

    @staticmethod
    def _dump(target: Any):
        try:
            return jsonpickle.encode(target, unpicklable=True, indent=2)
        except (Exception,):
            return target

    @staticmethod
    def _create_task(target: Any) -> Task:
        return asyncio.ensure_future(target)

    @staticmethod
    def _create_event_loop():
        return asyncio.get_event_loop()

    def _create_and_run_task(self, target: Any):
        event_loop = self._create_event_loop()
        task = self._create_task(target)
        if not event_loop.is_running():
            event_loop.run_until_complete(task)

    async def _update_order_status(self):
        async with self._locks.all_active_orders:
            self._all_active_orders = (
                self._gateway_order_tracker.active_orders if self._gateway_order_tracker else {}
            )

            orders = copy.copy(self._all_active_orders).values()

            for order in orders:
                if order.exchange_order_id is None:
                    continue

                request = {
                    "trading_pair": order.trading_pair,
                    "chain": self._chain,
                    "network": self._network,
                    "connector": self._connector,
                    "address": self._owner_address,
                    "exchange_order_id": order.exchange_order_id,
                }

                response = await self._gateway_get_clob_order_status_updates(request)

                try:
                    if response["orders"] is not None and len(response['orders']) and response["orders"][0] is not None and response["orders"][0]["state"] != order.current_state:
                        updated_order = response["orders"][0]

                        message = {
                            "trading_pair": order.trading_pair,
                            "update_timestamp":
                                updated_order["updatedAt"] if len(updated_order["updatedAt"]) else time(),
                            "new_state": updated_order["state"],
                        }

                        if updated_order["state"] in {
                            OrderState.PENDING_CREATE,
                            OrderState.OPEN,
                            OrderState.PARTIALLY_FILLED,
                            OrderState.PENDING_CANCEL,
                        }:

                            self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=message)

                        elif updated_order["state"] == OrderState.FILLED.name:
                            message = {
                                "timestamp":
                                    updated_order["updatedAt"] if len(updated_order["updatedAt"]) else time(),
                                "order_id": order.client_order_id,
                                "trading_pair": order.trading_pair,
                                "trade_type": order.trade_type,
                                "order_type": order.order_type,
                                "price": order.price,
                                "amount": order.amount,
                                "trade_fee": '',
                                "exchange_trade_id": "",
                                "exchange_order_id": order.exchange_order_id,
                            }

                            self._publisher.trigger_event(event_tag=MarketEvent.OrderFilled, message=message)

                        elif updated_order["state"] == OrderState.CANCELED.name:

                            message = {
                                "timestamp":
                                    updated_order["updatedAt"] if len(updated_order["updatedAt"]) else time(),
                                "order_id": order.client_order_id,
                                "exchange_order_id": order.exchange_order_id,
                            }

                            self._publisher.trigger_event(event_tag=OrderCancelledEvent, message=message)

                except Exception:
                    raise self.logger().exception(Exception)

    async def _update_all_active_orders(self):
        while True:
            await self._update_order_status()
            await asyncio.sleep(UPDATE_ORDER_STATUS_INTERVAL)

    @automatic_retry_with_timeout(retries=NUMBER_OF_RETRIES, delay=DELAY_BETWEEN_RETRIES, timeout=TIMEOUT)
    async def _gateway_ping_gateway(self, _request=None):
        return await self._gateway.ping_gateway()

    @automatic_retry_with_timeout(retries=NUMBER_OF_RETRIES, delay=DELAY_BETWEEN_RETRIES, timeout=TIMEOUT)
    async def _gateway_get_clob_markets(self, request):
        return await self._gateway.get_clob_markets(**request)

    @automatic_retry_with_timeout(retries=NUMBER_OF_RETRIES, delay=DELAY_BETWEEN_RETRIES, timeout=TIMEOUT)
    async def _gateway_get_clob_orderbook_snapshot(self, request):
        return await self._gateway.get_clob_orderbook_snapshot(**request)

    @automatic_retry_with_timeout(retries=NUMBER_OF_RETRIES, delay=DELAY_BETWEEN_RETRIES, timeout=TIMEOUT)
    async def _gateway_get_clob_ticker(self, request):
        return await self._gateway.get_clob_ticker(**request)

    @automatic_retry_with_timeout(retries=NUMBER_OF_RETRIES, delay=DELAY_BETWEEN_RETRIES, timeout=TIMEOUT)
    async def _gateway_get_balances(self, request):
        return await self._gateway.get_balances(**request)

    @automatic_retry_with_timeout(retries=NUMBER_OF_RETRIES, delay=DELAY_BETWEEN_RETRIES, timeout=TIMEOUT)
    async def _gateway_clob_place_order(self, request):
        return await self._gateway.clob_place_order(**request)

    @automatic_retry_with_timeout(retries=NUMBER_OF_RETRIES, delay=DELAY_BETWEEN_RETRIES, timeout=TIMEOUT)
    async def _gateway_clob_cancel_order(self, request):
        return await self._gateway.clob_cancel_order(**request)

    @automatic_retry_with_timeout(retries=NUMBER_OF_RETRIES, delay=DELAY_BETWEEN_RETRIES, timeout=TIMEOUT)
    async def _gateway_clob_batch_order_modify(self, request):
        return await self._gateway.clob_batch_order_modify(**request)

    @automatic_retry_with_timeout(retries=NUMBER_OF_RETRIES, delay=DELAY_BETWEEN_RETRIES, timeout=TIMEOUT)
    async def _gateway_get_clob_order_status_updates(self, request):
        return await self._gateway.get_clob_order_status_updates(**request)
