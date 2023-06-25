import asyncio
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.clob_spot.data_sources.clob_api_data_source_base import CLOBAPIDataSourceBase
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule, split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates
from hummingbot.core.event.events import MarketEvent, OrderBookDataSourceEvent
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


class GatewayCLOBAPIDataSourceBase(CLOBAPIDataSourceBase, ABC):
    """This class defines the pure-Gateway CLOB implementation.

    Technical note on the lack of user-data streaming (i.e. balance updates, etc.):
    Given that there are no user-stream data events being emitted due to the lack of ws streams from Gateway,
    GatewayClobSpot won't update the _last_received_message_timestamp attribute, and this will result in always
    using the short-polling interval in the polling loop.
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
        self._trading_pairs = trading_pairs
        self._chain = connector_spec["chain"]
        self._network = connector_spec["network"]
        self._account_id = connector_spec["wallet_address"]
        self._client_config = client_config_map
        self._markets_info_lock = asyncio.Lock()
        self._hb_to_exchange_tokens_map: bidict[str, str] = bidict()
        self._snapshots_min_update_interval = 1
        self._snapshots_max_update_interval = 3

        self._markets_update_task: Optional[asyncio.Task] = None
        self._snapshots_update_task: Optional[asyncio.Task] = None

    @property
    @abstractmethod
    def connector_name(self) -> str:
        ...

    @abstractmethod
    def get_supported_order_types(self) -> List[OrderType]:
        ...

    @abstractmethod
    async def get_order_status_update(self, in_flight_order: InFlightOrder) -> OrderUpdate:
        """This method should issue an OrderUpdate event before returning the result."""
        ...

    @abstractmethod
    async def get_all_order_fills(self, in_flight_order: InFlightOrder) -> List[TradeUpdate]:
        ...

    @abstractmethod
    def is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        ...

    @abstractmethod
    def is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        ...

    @abstractmethod
    def _parse_trading_rule(self, trading_pair: str, market_info: Dict[str, Any]) -> TradingRule:
        ...

    @abstractmethod
    def _get_trading_pair_from_market_info(self, market_info: Dict[str, Any]) -> str:
        ...

    @abstractmethod
    def _get_exchange_base_quote_tokens_from_market_info(self, market_info: Dict[str, Any]) -> Tuple[str, str]:
        ...

    @abstractmethod
    def _get_exchange_trading_pair_from_market_info(self, market_info: Dict[str, Any]) -> str:
        ...

    @abstractmethod
    def _get_last_trade_price_from_ticker_data(self, ticker_data: List[Dict[str, Any]]) -> Decimal:
        ...

    @abstractmethod
    def _get_maker_taker_exchange_fee_rates_from_market_info(
        self, market_info: Dict[str, Any]
    ) -> MakerTakerExchangeFeeRates:
        ...

    @property
    def chain(self) -> str:
        return self._chain

    @property
    def network(self) -> str:
        return self._network

    @property
    def real_time_balance_update(self) -> bool:
        return False

    @property
    def markets_update_interval(self) -> int:
        return 8 * 60 * 60

    @property
    def min_snapshots_update_interval(self) -> float:
        """In seconds."""
        return self._snapshots_min_update_interval

    @min_snapshots_update_interval.setter
    def min_snapshots_update_interval(self, value):
        """For unit-tests."""
        self._snapshots_min_update_interval = value

    @property
    def max_snapshots_update_interval(self) -> float:
        """In seconds."""
        return self._snapshots_max_update_interval

    @max_snapshots_update_interval.setter
    def max_snapshots_update_interval(self, value):
        """For unit-tests."""
        self._snapshots_max_update_interval = value

    @staticmethod
    def supported_stream_events() -> List[Enum]:
        return [
            OrderBookDataSourceEvent.SNAPSHOT_EVENT,
            MarketEvent.OrderUpdate,
        ]

    async def start(self):
        self._markets_update_task = self._markets_update_task or safe_ensure_future(
            coro=self._update_markets_loop()
        )
        self._snapshots_update_task = self._snapshots_update_task or safe_ensure_future(
            coro=self._update_snapshots_loop()
        )

    async def stop(self):
        self._markets_update_task and self._markets_update_task.cancel()
        self._markets_update_task = None
        self._snapshots_update_task and self._snapshots_update_task.cancel()
        self._snapshots_update_task = None

    async def place_order(
        self, order: GatewayInFlightOrder, **kwargs
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        order_result = await self._get_gateway_instance().clob_place_order(
            connector=self.connector_name,
            chain=self._chain,
            network=self._network,
            trading_pair=order.trading_pair,
            address=self._account_id,
            trade_type=order.trade_type,
            order_type=order.order_type,
            price=order.price,
            size=order.amount,
            client_order_id=order.client_order_id,
        )

        transaction_hash: Optional[str] = order_result.get("txHash")

        if transaction_hash is None:
            await self._on_create_order_transaction_failure(order=order, order_result=order_result)

        transaction_hash = transaction_hash.lower()

        misc_updates = {
            "creation_transaction_hash": transaction_hash,
        }

        return None, misc_updates

    async def batch_order_create(self, orders_to_create: List[GatewayInFlightOrder]) -> List[PlaceOrderResult]:
        update_result = await self._get_gateway_instance().clob_batch_order_modify(
            connector=self.connector_name,
            chain=self._chain,
            network=self._network,
            address=self._account_id,
            orders_to_create=orders_to_create,
            orders_to_cancel=[],
        )

        transaction_hash: Optional[str] = update_result.get("txHash")
        exception = None

        if transaction_hash is None:
            self.logger().error("The batch order update transaction failed.")
            exception = ValueError(f"The creation transaction has failed on the {self._chain} chain.")

        transaction_hash = "" if transaction_hash is None else transaction_hash.lower()

        place_order_results = []
        for order in orders_to_create:
            place_order_results.append(
                PlaceOrderResult(
                    update_timestamp=self._time(),
                    client_order_id=order.client_order_id,
                    exchange_order_id=None,
                    trading_pair=order.trading_pair,
                    misc_updates={
                        "creation_transaction_hash": transaction_hash,
                    },
                    exception=exception,
                )
            )

        return place_order_results

    async def cancel_order(self, order: GatewayInFlightOrder) -> Tuple[bool, Optional[Dict[str, Any]]]:
        if order.exchange_order_id is None:  # we still haven't receive an order status update
            await self.get_order_status_update(in_flight_order=order)

        await order.get_exchange_order_id()

        cancelation_result = await self._get_gateway_instance().clob_cancel_order(
            connector=self.connector_name,
            chain=self._chain,
            network=self._network,
            trading_pair=order.trading_pair,
            address=self._account_id,
            exchange_order_id=order.exchange_order_id,
        )
        transaction_hash: Optional[str] = cancelation_result.get("txHash")

        if transaction_hash is None:
            await self._on_cancel_order_transaction_failure(order=order, cancelation_result=cancelation_result)

        transaction_hash = transaction_hash.lower()

        misc_updates = {
            "cancelation_transaction_hash": transaction_hash
        }

        return True, misc_updates

    async def batch_order_cancel(self, orders_to_cancel: List[GatewayInFlightOrder]) -> List[CancelOrderResult]:
        in_flight_orders_to_cancel = [
            self._gateway_order_tracker.fetch_tracked_order(client_order_id=order.client_order_id)
            for order in orders_to_cancel
        ]
        cancel_order_results = []
        if len(in_flight_orders_to_cancel) != 0:
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
                connector=self.connector_name,
                chain=self._chain,
                network=self._network,
                address=self._account_id,
                orders_to_create=[],
                orders_to_cancel=found_orders_to_cancel,
            )

            transaction_hash: Optional[str] = update_result.get("txHash")
            exception = None

            if transaction_hash is None:
                self.logger().error("The batch order update transaction failed.")
                exception = ValueError(f"The cancelation transaction has failed on the {self._chain} chain.")

            transaction_hash = "" if transaction_hash is None else transaction_hash.lower()

            for order in found_orders_to_cancel:
                cancel_order_results.append(
                    CancelOrderResult(
                        client_order_id=order.client_order_id,
                        trading_pair=order.trading_pair,
                        misc_updates={
                            "cancelation_transaction_hash": transaction_hash
                        },
                        exception=exception,
                    )
                )

        return cancel_order_results

    async def get_last_traded_price(self, trading_pair: str) -> Decimal:
        ticker_data = await self._get_ticker_data(trading_pair=trading_pair)
        last_traded_price = self._get_last_trade_price_from_ticker_data(ticker_data=ticker_data)
        return last_traded_price

    async def get_order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        data = await self._get_gateway_instance().get_clob_orderbook_snapshot(
            trading_pair=trading_pair, connector=self.connector_name, chain=self._chain, network=self._network
        )
        bids = [
            (Decimal(bid["price"]), Decimal(bid["quantity"]))
            for bid in data["buys"]
            if Decimal(bid["quantity"]) != 0
        ]
        asks = [
            (Decimal(ask["price"]), Decimal(ask["quantity"]))
            for ask in data["sells"]
            if Decimal(ask["quantity"]) != 0
        ]
        snapshot_msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": self._time() * 1e3,
                "bids": bids,
                "asks": asks,
            },
            timestamp=data["timestamp"],
        )
        return snapshot_msg

    async def check_network_status(self) -> NetworkStatus:
        status = NetworkStatus.CONNECTED
        try:
            await self._get_gateway_instance().ping_gateway()
        except asyncio.CancelledError:
            raise
        except Exception:
            status = NetworkStatus.NOT_CONNECTED
        return status

    async def get_account_balances(self) -> Dict[str, Dict[str, Decimal]]:
        """Returns a dictionary like

                {
                    asset_name: {
                        "total_balance": Decimal,
                        "available_balance": Decimal,
                    }
                }
        """
        balances = await self._get_gateway_instance().get_balances(
            chain=self._chain,
            network=self._network,
            address=self._account_id,
        )
        return balances

    def _check_markets_initialized(self) -> bool:
        return len(self._markets_info) != 0

    async def _update_markets_loop(self):
        while True:
            await self._sleep(delay=self.markets_update_interval)
            await self._update_markets()

    async def _update_markets(self):
        async with self._markets_info_lock:
            for market_info in await self._get_markets_info():
                trading_pair = self._get_trading_pair_from_market_info(market_info=market_info)
                self._markets_info[trading_pair] = market_info
                base, quote = split_hb_trading_pair(trading_pair=trading_pair)
                base_exchange, quote_exchange = self._get_exchange_base_quote_tokens_from_market_info(
                    market_info=market_info
                )
                self._hb_to_exchange_tokens_map[base] = base_exchange
                self._hb_to_exchange_tokens_map[quote] = quote_exchange

    async def _get_markets_info(self) -> List[Dict[str, Any]]:
        resp = await self._get_gateway_instance().get_clob_markets(
            connector=self.connector_name, chain=self._chain, network=self._network
        )
        return resp["markets"]

    async def _update_snapshots_loop(self):
        while True:
            update_task = safe_ensure_future(coro=self._emit_snapshots_updates())
            min_delay_sleep = self._sleep(delay=self.min_snapshots_update_interval)
            max_delay_sleep = self._sleep(delay=self.max_snapshots_update_interval)

            or_group = next(
                asyncio.as_completed(
                    [update_task, max_delay_sleep]
                )  # returns first done, lets the other run - i.e. run for at most max_delay_sleep
            )
            and_group = safe_gather(min_delay_sleep, or_group)  # run for at least min_delay_sleep

            start_ts = self._time()
            await and_group

            if self._time() - start_ts >= self.max_snapshots_update_interval:
                self.logger().warning(f"Snapshot update took longer than {self.max_snapshots_update_interval}.")

    async def _emit_snapshots_updates(self):
        tasks = [
            self._emit_trading_pair_snapshot_update(trading_pair=trading_pair)
            for trading_pair in self._trading_pairs
        ]
        await safe_gather(*tasks)

    async def _emit_trading_pair_snapshot_update(self, trading_pair: str):
        try:
            snapshot_msg = await self.get_order_book_snapshot(trading_pair=trading_pair)
            self._publisher.trigger_event(event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, message=snapshot_msg)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(f"Failed to update snapshot message for {trading_pair}.")

    async def _get_ticker_data(self, trading_pair: str) -> List[Dict[str, Any]]:
        ticker_data = await self._get_gateway_instance().get_clob_ticker(
            connector=self.connector_name,
            chain=self._chain,
            network=self._network,
            trading_pair=trading_pair,
        )
        return ticker_data["markets"]

    async def _on_create_order_transaction_failure(self, order: GatewayInFlightOrder, order_result: Dict[str, Any]):
        raise ValueError(
            f"The creation transaction for {order.client_order_id} failed. Please ensure you have sufficient"
            f" funds to cover the transaction gas costs."
        )

    async def _on_cancel_order_transaction_failure(self, order: GatewayInFlightOrder, cancelation_result: Dict[str, Any]):
        raise ValueError(
            f"The cancelation transaction for {order.client_order_id} failed. Please ensure you have sufficient"
            f" funds to cover the transaction gas costs."
        )

    @staticmethod
    async def _sleep(delay: float):
        await asyncio.sleep(delay)

    @staticmethod
    def _time() -> float:
        return time.time()

    def _get_gateway_instance(self) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        return gateway_instance
