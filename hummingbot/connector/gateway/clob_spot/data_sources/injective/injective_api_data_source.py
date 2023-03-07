import asyncio
import json
import time
from asyncio import Lock
from decimal import Decimal
from math import floor
from typing import Any, Dict, List, Mapping, Optional, Tuple

from bidict import bidict
from grpc.aio import UnaryStreamCall
from pyinjective.async_client import AsyncClient
from pyinjective.composer import Composer as ProtoMsgComposer
from pyinjective.constant import Network
from pyinjective.orderhash import OrderHashResponse, build_eip712_msg, hash_order
from pyinjective.proto.exchange.injective_explorer_rpc_pb2 import GetTxByTxHashResponse, StreamTxsResponse
from pyinjective.proto.exchange.injective_spot_exchange_rpc_pb2 import (
    MarketsResponse,
    SpotMarketInfo,
    SpotOrderHistory,
    SpotTrade,
    StreamOrderbookResponse,
    StreamOrdersResponse,
    StreamTradesResponse,
    TokenMeta,
)
from pyinjective.proto.injective.exchange.v1beta1.exchange_pb2 import DerivativeOrder, SpotOrder

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_constants import (
    ACC_NONCE_PATH_RATE_LIMIT_ID,
    BACKEND_TO_CLIENT_ORDER_STATE_MAP,
    CLIENT_TO_BACKEND_ORDER_TYPES_MAP,
    CONNECTOR_NAME,
    MARKETS_UPDATE_INTERVAL,
    MSG_BATCH_UPDATE_ORDERS,
    MSG_CANCEL_SPOT_ORDER,
    MSG_CREATE_SPOT_LIMIT_ORDER,
    NONCE_PATH,
    RATE_LIMITS,
    REQUESTS_SKIP_STEP,
)
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book import OrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates, TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent, OrderBookDataSourceEvent
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class OrderHashManager:
    def __init__(self, network: Network, sub_account_id: str):
        self._sub_account_id = sub_account_id
        self._network = network
        self._sub_account_nonce = 0
        self._web_assistants_factory = WebAssistantsFactory(throttler=AsyncThrottler(rate_limits=RATE_LIMITS))

    @property
    def current_nonce(self) -> int:
        return self._sub_account_nonce

    async def start(self):
        url = f"{self._network.lcd_endpoint}/{NONCE_PATH}/{self._sub_account_id}"
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        res = await rest_assistant.execute_request(url=url, throttler_limit_id=ACC_NONCE_PATH_RATE_LIMIT_ID)
        nonce = res["nonce"]
        self._sub_account_nonce = nonce + 1

    def compute_order_hashes(
        self, spot_orders: List[SpotOrder], derivative_orders: List[DerivativeOrder]
    ) -> OrderHashResponse:
        order_hashes = OrderHashResponse(spot=[], derivative=[])

        for o in spot_orders:
            order_hash = hash_order(build_eip712_msg(o, self._sub_account_nonce))
            order_hashes.spot.append(order_hash)
            self._sub_account_nonce += 1

        for o in derivative_orders:
            order_hash = hash_order(build_eip712_msg(o, self._sub_account_nonce))
            order_hashes.derivative.append(order_hash)
            self._sub_account_nonce += 1

        return order_hashes


class InjectiveAPIDataSource(GatewayCLOBAPIDataSourceBase):
    """An interface class to the Injective blockchain.

    Note — The same wallet address should not be used with different instances of the client as this will cause
    issues with the account sequence management and may result in failed transactions, or worse, wrong locally computed
    order hashes (exchange order IDs), which will in turn result in orphaned orders on the exchange.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        chain: str,
        network: str,
        address: str,
        client_config_map: ClientConfigAdapter,
    ):
        super().__init__()
        self._trading_pairs = trading_pairs
        self._connector_name = CONNECTOR_NAME
        self._chain = chain
        self._network = network
        self._sub_account_id = address
        self._account_address: Optional[str] = None
        self._network_obj = Network.custom(
            lcd_endpoint="https://k8s.global.mainnet.lcd.injective.network:443",
            tm_websocket_endpoint="wss://k8s.global.mainnet.tm.injective.network:443/websocket",
            grpc_endpoint="k8s.global.mainnet.chain.grpc.injective.network:443",
            grpc_exchange_endpoint="k8s.global.mainnet.exchange.grpc.injective.network:443",
            grpc_explorer_endpoint="k8s.mainnet.explorer.grpc.injective.network:443",
            chain_id="injective-1",
            env="mainnet"
        )
        self._client = AsyncClient(network=self._network_obj)
        self._composer = ProtoMsgComposer(network=self._network_obj.string())
        self._order_hash_manager: Optional[OrderHashManager] = None
        self._client_config = client_config_map

        self._trading_pair_to_active_spot_markets: Dict[str, SpotMarketInfo] = {}
        self._market_id_to_active_spot_markets: Dict[str, SpotMarketInfo] = {}
        self._denom_to_token_meta: Dict[str, TokenMeta] = {}
        self._markets_update_task: Optional[asyncio.Task] = None

        self._trades_stream_listener: Optional[asyncio.Task] = None
        self._order_listeners: Dict[str, asyncio.Task] = {}
        self._order_books_stream_listener: Optional[asyncio.Task] = None
        self._account_balances_stream_listener: Optional[asyncio.Task] = None
        self._transactions_stream_listener: Optional[asyncio.Task] = None

        self._order_placement_lock = Lock()

    def get_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def start(self):
        """Starts the event streaming."""
        async with self._order_placement_lock:
            await self._update_account_address_and_create_order_hash_manager()
        self._markets_update_task = self._markets_update_task or safe_ensure_future(
            coro=self._update_markets_loop()
        )
        await self._update_markets()  # required for the streams
        await self._start_streams()

    async def stop(self):
        """Stops the event streaming."""
        await self._stop_streams()
        self._markets_update_task and self._markets_update_task.cancel()
        self._markets_update_task = None

    async def place_order(
        self, order: GatewayInFlightOrder, **kwargs
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        market = self._trading_pair_to_active_spot_markets[order.trading_pair]
        spot_order_to_create = [
            self._composer.SpotOrder(
                market_id=market.market_id,
                subaccount_id=self._sub_account_id,
                fee_recipient=self._account_address,
                price=float(order.price),
                quantity=float(order.amount),
                is_buy=order.trade_type == TradeType.BUY,
                is_po=order.order_type == OrderType.LIMIT_MAKER,
            ),
        ]

        async with self._order_placement_lock:
            order_hashes = self._order_hash_manager.compute_order_hashes(
                spot_orders=spot_order_to_create, derivative_orders=[]
            )
            order_hash = order_hashes.spot[0]

            self.logger().debug(
                f"Placing order {order.client_order_id} with order hash {order_hash} from nonce"
                f" {self._order_hash_manager.current_nonce - 1}"
            )  # todo: remove

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
            except Exception:
                await self._update_account_address_and_create_order_hash_manager()
                raise

            transaction_hash: Optional[str] = order_result.get("txHash")

            self.logger().debug(f"Placed order {order_hash} with tx hash {transaction_hash}")  # todo: remove

            if transaction_hash is None:
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

    async def cancel_order(self, order: GatewayInFlightOrder) -> Tuple[bool, Dict[str, Any]]:

        await order.get_exchange_order_id()
        self.logger().debug(f"Canceling order {order.exchange_order_id}")  # todo: remove

        cancelation_result = await self._get_gateway_instance().clob_cancel_order(
            connector=self._connector_name,
            chain=self._chain,
            network=self._network,
            trading_pair=order.trading_pair,
            address=self._sub_account_id,
            exchange_order_id=order.exchange_order_id,
        )
        transaction_hash: Optional[str] = cancelation_result.get("txHash")

        if transaction_hash is None:
            async with self._order_placement_lock:
                await self._update_account_address_and_create_order_hash_manager()
            raise ValueError(
                f"The cancelation transaction for {order.client_order_id} failed. Please ensure there is sufficient"
                f" INJ in the bank to cover transaction fees."
            )

        transaction_hash = f"0x{transaction_hash.lower()}"
        self.logger().debug(f"Canceled order {order.exchange_order_id} with tx hash {transaction_hash}")  # todo: remove

        misc_updates = {
            "cancelation_transaction_hash": transaction_hash
        }

        return True, misc_updates

    async def get_trading_rules(self) -> Dict[str, TradingRule]:
        self._check_markets_initialized() or await self._update_markets()

        trading_rules = {
            trading_pair: self._get_trading_rule_from_market(trading_pair=trading_pair, market=market)
            for trading_pair, market in self._trading_pair_to_active_spot_markets.items()
        }
        return trading_rules

    async def get_symbol_map(self) -> bidict[str, str]:
        self._check_markets_initialized() or await self._update_markets()

        mapping = bidict()
        for trading_pair, market in self._trading_pair_to_active_spot_markets.items():
            mapping[market.market_id] = trading_pair
        return mapping

    async def get_last_traded_price(self, trading_pair: str) -> Decimal:
        market = self._trading_pair_to_active_spot_markets[trading_pair]
        trades = await self._client.get_spot_trades(market_id=market.market_id)
        if len(trades.trades) != 0:
            price = self._convert_price_from_backend(price=trades.trades[0].price.price, market=market)
        else:
            price = Decimal("NaN")
        return price

    async def get_order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        market = self._trading_pair_to_active_spot_markets[trading_pair]
        order_book_response = await self._client.get_spot_orderbook(market_id=market.market_id)
        price_scale = self._get_backend_price_scaler(market=market)
        size_scale = self._get_backend_denom_scaler(denom_meta=market.base_token_meta)
        last_update_timestamp_ms = 0
        bids = []
        for bid in order_book_response.orderbook.buys:
            bids.append((Decimal(bid.price) * price_scale, Decimal(bid.quantity) * size_scale))
            last_update_timestamp_ms = max(last_update_timestamp_ms, bid.timestamp)
        asks = []
        for ask in order_book_response.orderbook.sells:
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

    async def get_account_balances(self) -> Dict[str, Dict[str, Decimal]]:
        """Returns a dictionary like

        {
            asset_name: {
                "total_balance": Decimal,
                "available_balance": Decimal,
            }
        }

        Sub-account balances response example:

        balances [
            {
                subaccount_id: "0x972a7e7d1db231f67e797fccfbd04d17f825fcde000000000000000000000000"  # noqa: mock
                account_address: "inj1ju48ulgakgclvlne0lx0h5zdzluztlx7suwq7z"
                denom: "inj"
                deposit {
                    total_balance: "33624286700000000000000"
                    available_balance: "33425992700000000000000"
                }
            }
        ]

        Bank balances response example:

        balances {
          denom: "inj"
          amount: "4997743375000000000"
        }
        pagination {
          total: 1
        }
        """
        self._check_markets_initialized() or await self._update_markets()

        balances_dict = {}
        sub_account_balances = await self._client.get_subaccount_balances_list(subaccount_id=self._sub_account_id)
        for balance in sub_account_balances.balances:
            denom_meta = self._denom_to_token_meta[balance.denom]
            asset_name = denom_meta.symbol
            asset_scaler = self._get_backend_denom_scaler(denom_meta=denom_meta)
            total_balance = Decimal(balance.deposit.total_balance) * asset_scaler
            available_balance = Decimal(balance.deposit.available_balance) * asset_scaler
            balances_dict[asset_name] = {
                "total_balance": total_balance,
                "available_balance": available_balance,
            }
        return balances_dict

    async def get_all_order_fills(self, in_flight_order: GatewayInFlightOrder) -> List[TradeUpdate]:
        trading_pair = in_flight_order.trading_pair
        market = self._trading_pair_to_active_spot_markets[trading_pair]
        direction = "buy" if in_flight_order.trade_type == TradeType.BUY else "sell"

        trade_updates = []
        trades = await self._get_all_trades(
            market_id=market.market_id,
            direction=direction,
            created_at=int(in_flight_order.creation_timestamp * 1e3),
            updated_at=int(in_flight_order.last_update_timestamp * 1e3)
        )

        for backend_trade in trades:
            trade_update = self._parse_backend_trade(
                client_order_id=in_flight_order.client_order_id, backend_trade=backend_trade
            )
            trade_updates.append(trade_update)

        return trade_updates

    async def get_order_status_update(self, in_flight_order: GatewayInFlightOrder) -> OrderUpdate:
        self.logger().debug(f"Getting order status update for {in_flight_order.exchange_order_id}")  # todo: remove
        trading_pair = in_flight_order.trading_pair
        order_hash = await in_flight_order.get_exchange_order_id()
        misc_updates = {
            "creation_transaction_hash": in_flight_order.creation_transaction_hash,
            "cancelation_transaction_hash": in_flight_order.cancel_tx_hash,
        }

        market = self._trading_pair_to_active_spot_markets[trading_pair]
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
            self.logger().debug(
                f"Failed to find status update for {in_flight_order.exchange_order_id}. Attempting from transaction"
                f" hash {in_flight_order.creation_transaction_hash}."
            )  # todo: remove
            creation_transaction = await self._get_transaction_by_hash(
                transaction_hash=in_flight_order.creation_transaction_hash
            )
            if await self._check_if_order_failed_based_on_transaction(
                transaction=creation_transaction, order=in_flight_order
            ):
                status_update = OrderUpdate(
                    trading_pair=in_flight_order.trading_pair,
                    update_timestamp=creation_transaction.data.block_unix_timestamp * 1e-3,
                    new_state=OrderState.FAILED,
                    client_order_id=in_flight_order.client_order_id,
                    exchange_order_id=in_flight_order.exchange_order_id,
                    misc_updates=misc_updates,
                )
        if status_update is None:
            self.logger().debug(
                f"Failed to find an order status update for {in_flight_order.exchange_order_id}"
            )  # todo: remove
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

    async def get_trading_fees(self) -> Mapping[str, MakerTakerExchangeFeeRates]:
        self._check_markets_initialized() or await self._update_markets()

        trading_fees = {}
        for trading_pair, market in self._trading_pair_to_active_spot_markets.items():
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
            start_time=int(creation_timestamp),
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

    async def _update_account_address_and_create_order_hash_manager(self):
        if not self._order_placement_lock.locked():
            raise RuntimeError("The order-placement lock must be acquired before creating the order hash manager.")
        sub_account_balances = await self._client.get_subaccount_balances_list(subaccount_id=self._sub_account_id)
        self._account_address = sub_account_balances.balances[0].account_address
        await self._client.get_account(self._account_address)
        await self._client.sync_timeout_height()
        self._order_hash_manager = OrderHashManager(
            network=self._network_obj, sub_account_id=self._sub_account_id
        )
        await self._order_hash_manager.start()

    def _check_markets_initialized(self) -> bool:
        return (
            len(self._trading_pair_to_active_spot_markets) != 0
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

    def _update_trading_pair_to_active_spot_markets(self, markets: MarketsResponse):
        markets_dict = {}
        for market in markets.markets:
            trading_pair = combine_to_hb_trading_pair(
                base=market.base_token_meta.symbol, quote=market.quote_token_meta.symbol
            )
            markets_dict[trading_pair] = market
        self._trading_pair_to_active_spot_markets.clear()
        self._trading_pair_to_active_spot_markets.update(markets_dict)

    def _update_market_id_to_active_spot_markets(self, markets: MarketsResponse):
        markets_dict = {market.market_id: market for market in markets.markets}
        self._market_id_to_active_spot_markets.clear()
        self._market_id_to_active_spot_markets.update(markets_dict)

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
        self._account_balances_stream_listener = (
            self._account_balances_stream_listener or safe_ensure_future(coro=self._listen_to_account_balances_stream())
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
        self._account_balances_stream_listener and self._account_balances_stream_listener.cancel()
        self._account_balances_stream_listener = None
        self._transactions_stream_listener and self._transactions_stream_listener.cancel()
        self._transactions_stream_listener = None

    async def _listen_to_trades_stream(self):
        while True:
            market_ids = self._get_market_ids()
            stream: UnaryStreamCall = await self._client.stream_spot_trades(market_ids=market_ids)
            try:
                async for trade in stream:
                    self._parse_trade_event(trade=trade)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
            self.logger().info("Restarting trades stream.")
            stream.cancel()

    def _parse_trade_event(self, trade: StreamTradesResponse):
        """Injective fires two trade updates per transaction.

        Trade update example:

        trade {
          order_hash: "0x289fa654ac64a591e0cee447af3f03b279c8e8cc4d77e2f1c24386eefa8988c9"  # noqa: mock
          subaccount_id: "0x32b16783ea9a08602dc792f24c3d78bba6e333d3000000000000000000000000"  # noqa: mock
          market_id: "0xd1956e20d74eeb1febe31cd37060781ff1cb266f49e0512b446a5fafa9a16034"  # noqa: mock
          trade_execution_type: "limitMatchNewOrder"
          trade_direction: "buy"
          price {
            price: "0.000000001160413"
            quantity: "1000000000000000"
            timestamp: 1669192684763
          }
          fee: "278.49912"
          executed_at: 1669192684763
          fee_recipient: "inj1x2ck0ql2ngyxqtw8jteyc0tchwnwxv7npaungt"
          trade_id: "19906622_289fa654ac64a591e0cee447af3f03b279c8e8cc4d77e2f1c24386eefa8988c9"  # noqa: mock
          execution_side: "taker"
        }
        operation_type: "insert"
        timestamp: 1669192686000
        """
        market_id = trade.trade.market_id
        trading_pair = self._get_trading_pair_from_market_id(market_id=market_id)
        market = self._market_id_to_active_spot_markets[market_id]
        price = self._convert_price_from_backend(price=trade.trade.price.price, market=market)
        size = self._convert_size_from_backend(size=trade.trade.price.quantity, market=market)
        is_taker = trade.trade.execution_side == "taker"

        trade_msg_content = {
            "trade_id": trade.trade.trade_id,
            "trading_pair": trading_pair,
            "trade_type": TradeType.BUY if trade.trade.trade_direction == "buy" else TradeType.SELL,
            "amount": size,
            "price": price,
            "is_taker": is_taker,
        }
        trade_msg = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            timestamp=trade.trade.executed_at * 1e-3,
            content=trade_msg_content,
        )
        self._publisher.trigger_event(event_tag=OrderBookDataSourceEvent.TRADE_EVENT, message=trade_msg)

        exchange_order_id = trade.trade.order_hash
        tracked_order = self._gateway_order_tracker.all_fillable_orders_by_exchange_id.get(exchange_order_id)
        client_order_id = "" if tracked_order is None else tracked_order.client_order_id

        trade_update = self._parse_backend_trade(
            client_order_id=client_order_id, backend_trade=trade.trade
        )
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
        """
        Order update example:

        order {
          order_hash: "0x6df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc7"  # noqa: documentation
          market_id: "0xd1956e20d74eeb1febe31cd37060781ff1cb266f49e0512b446a5fafa9a16034"  # noqa: documentation
          subaccount_id: "0x32b16783ea9a08602dc792f24c3d78bba6e333d3000000000000000000000000"  # noqa: documentation
          execution_type: "limit"
          order_type: "buy_po"
          price: "0.00000000116023"
          trigger_price: "0"
          quantity: "2000000000000000"
          filled_quantity: "0"
          state: "canceled"
          created_at: 1669198777253
          updated_at: 1669198783253
          direction: "buy"
        }
        operation_type: "update"
        timestamp: 1669198784000
        """
        order_hash = order.order.order_hash
        in_flight_order = self._gateway_order_tracker.all_fillable_orders_by_exchange_id.get(order_hash)
        if in_flight_order is not None:
            self.logger().debug(f"Received order status update for {in_flight_order.exchange_order_id}")  # todo: remove
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
            stream: UnaryStreamCall = await self._client.stream_spot_orderbooks(market_ids=market_ids)
            try:
                async for order_book_update in stream:
                    self._parse_order_book_event(order_book_update=order_book_update)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
            self.logger().info("Restarting order books stream.")
            stream.cancel()

    def _parse_order_book_event(self, order_book_update: StreamOrderbookResponse):
        """
        Orderbook update example:

        orderbook {
          buys {
            price: "0.000000001161518"
            quantity: "1000000000000000"
            timestamp: 1662113015864
          }
          sells {
            price: "0.00000000116303"
            quantity: "1366000000000000000"
            timestamp: 1669192832799
          }
        }
        operation_type: "update"
        timestamp: 1669192836000
        market_id: "0xd1956e20d74eeb1febe31cd37060781ff1cb266f49e0512b446a5fafa9a16034"  # noqa: documentation
        """
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

    async def _listen_to_account_balances_stream(self):
        while True:
            stream: UnaryStreamCall = await self._client.stream_subaccount_balance(subaccount_id=self._sub_account_id)
            try:
                async for balance in stream:
                    self._parse_balance_event(balance=balance)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
            self.logger().info("Restarting account balances stream.")
            stream.cancel()

    def _parse_balance_event(self, balance):
        """
        Balance update example:

        balance {
          subaccount_id: "0x972a7e7d1db231f67e797fccfbd04d17f825fcde000000000000000000000000"  # noqa: documentation
          account_address: "inj1ju48ulgakgclvlne0lx0h5zdzluztlx7suwq7z"  # noqa: documentation
          denom: "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7"
          deposit {
            available_balance: "21459060342.811393459150323702"
          }
        }
        """
        denom_meta = self._denom_to_token_meta[balance.balance.denom]
        denom_scaler = self._get_backend_denom_scaler(denom_meta=denom_meta)
        total_balance = balance.balance.deposit.total_balance
        total_balance = Decimal(total_balance) * denom_scaler if total_balance != "" else None
        available_balance = balance.balance.deposit.available_balance
        available_balance = Decimal(available_balance) * denom_scaler if available_balance != "" else None
        balance_msg = BalanceUpdateEvent(
            timestamp=balance.timestamp * 1e-3,
            asset_name=denom_meta.symbol,
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
            orders = await self._client.get_historical_spot_orders(
                market_id=market_id,
                subaccount_id=self._sub_account_id,
                direction=direction,
                start_time=start_time,
                skip=skip,
                order_types=[CLIENT_TO_BACKEND_ORDER_TYPES_MAP[(trade_type, order_type)]]
            )
            if len(orders.orders) == 0:
                search_completed = True
            else:
                skip += REQUESTS_SKIP_STEP
                for order in orders.orders:
                    if order.order_hash == order_hash:
                        order_status = order
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
                end_time=updated_at,
            )
            if len(trades.trades) == 0:
                search_completed = True
            else:
                all_trades.extend(trades.trades)
                skip += len(trades.trades)

        return all_trades

    def _parse_backend_trade(self, client_order_id: str, backend_trade: SpotTrade) -> TradeUpdate:
        market = self._market_id_to_active_spot_markets[backend_trade.market_id]
        trading_pair = self._get_trading_pair_from_market_id(market_id=backend_trade.market_id)
        price = self._convert_price_from_backend(price=backend_trade.price.price, market=market)
        size = self._convert_size_from_backend(size=backend_trade.price.quantity, market=market)
        trade_type = TradeType.BUY if backend_trade.trade_direction == "buy" else TradeType.SELL
        fee_amount = self._convert_quote_from_backend(quote_amount=backend_trade.fee, market=market)
        _, quote = split_hb_trading_pair(trading_pair=trading_pair)
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=TradeFeeSchema(),
            trade_type=trade_type,
            flat_fees=[TokenAmount(amount=fee_amount, token=quote)]
        )
        trade_update = TradeUpdate(
            trade_id=backend_trade.trade_id,
            client_order_id=client_order_id,
            exchange_order_id=backend_trade.order_hash,
            trading_pair=trading_pair,
            fill_timestamp=backend_trade.executed_at * 1e-3,
            fill_price=price,
            fill_base_amount=size,
            fill_quote_amount=price * size,
            fee=fee,
        )
        return trade_update

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
        order = self._gateway_order_tracker.get_fillable_order_by_hash(hash=transaction.hash)
        if order is not None:
            self.logger().debug(f"Received transaction update for {order.exchange_order_id}")  # todo: remove
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

    def _get_trading_rule_from_market(self, trading_pair: str, market: SpotMarketInfo) -> TradingRule:
        min_price_tick_size = self._convert_price_from_backend(price=market.min_price_tick_size, market=market)
        min_quantity_tick_size = self._convert_size_from_backend(size=market.min_quantity_tick_size, market=market)
        trading_rule = TradingRule(
            trading_pair=trading_pair,
            min_order_size=min_quantity_tick_size,
            min_price_increment=min_price_tick_size,
            min_base_amount_increment=min_quantity_tick_size,
            min_quote_amount_increment=min_price_tick_size,
        )
        return trading_rule

    def _convert_price_from_backend(self, price: str, market: SpotMarketInfo) -> Decimal:
        scale = self._get_backend_price_scaler(market=market)
        scaled_price = Decimal(price) * scale
        return scaled_price

    async def _get_transaction_by_hash(self, transaction_hash: str) -> GetTxByTxHashResponse:
        return await self._client.get_tx_by_hash(tx_hash=transaction_hash)

    def _get_market_ids(self) -> List[str]:
        market_ids = [
            self._trading_pair_to_active_spot_markets[trading_pair].market_id
            for trading_pair in self._trading_pairs
        ]
        return market_ids

    @staticmethod
    async def _check_if_order_failed_based_on_transaction(
        transaction: GetTxByTxHashResponse, order: GatewayInFlightOrder
    ) -> bool:
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
