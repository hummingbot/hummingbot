import asyncio
import json
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from bidict import bidict
from grpc.aio import UnaryStreamCall
from pyinjective.async_client import AsyncClient
from pyinjective.composer import Composer as ProtoMsgComposer
from pyinjective.constant import Network
from pyinjective.proto.exchange.injective_accounts_rpc_pb2 import StreamSubaccountBalanceResponse, SubaccountBalance
from pyinjective.proto.exchange.injective_derivative_exchange_rpc_pb2 import (
    DerivativeLimitOrderbook,
    DerivativeMarketInfo,
    DerivativeOrderHistory,
    DerivativePosition,
    DerivativeTrade,
    MarketsResponse,
    OrderbookResponse,
    OrdersHistoryResponse,
    StreamOrdersHistoryResponse,
    StreamOrdersResponse,
    StreamPositionsResponse,
    StreamTradesResponse,
    TokenMeta,
    TradesResponse,
)
from pyinjective.proto.exchange.injective_explorer_rpc_pb2 import GetTxByTxHashResponse, StreamTxsResponse, TxDetailData
from pyinjective.proto.exchange.injective_oracle_rpc_pb2 import StreamPricesResponse

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.gateway.clob_perp.data_sources.gateway_clob_perp_api_data_source_base import (
    GatewayCLOBPerpAPIDataSourceBase,
)
from hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual import (
    injective_perpetual_constants as CONSTANTS,
)
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source import OrderHashManager
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates, TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent, OrderBookDataSourceEvent
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future


class InjectivePerpetualAPIDataSource(GatewayCLOBPerpAPIDataSourceBase):
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
        self._connector_name = CONSTANTS.CONNECTOR_NAME
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
            env="mainnet",
        )
        self._client = AsyncClient(network=self._network_obj)

        self._client_config = client_config_map

        self._composer = ProtoMsgComposer(network=self._network_obj.string())
        self._order_hash_manager: Optional[OrderHashManager] = None

        # Market Info Attributes
        self._trading_pair_to_active_perp_markets: Dict[str, DerivativeMarketInfo] = {}
        self._market_id_to_active_perp_markets: Dict[str, DerivativeMarketInfo] = {}
        self._trading_pair_to_market_id_map = bidict()
        self._denom_to_token_meta: Dict[str, Union[Dict[str, Any], TokenMeta]] = {}

        # Listener(s) and Loop Task(s)
        self._update_market_info_loop_task: Optional[asyncio.Task] = None
        self._trades_stream_listener: Optional[asyncio.Task] = None
        self._order_listeners: Dict[str, asyncio.Task] = {}
        self._order_books_stream_listener: Optional[asyncio.Task] = None
        self._account_balances_stream_listener: Optional[asyncio.Task] = None
        self._transactions_stream_listener: Optional[asyncio.Task] = None

        self._order_placement_lock = asyncio.Lock()

    def get_supported_order_types(self) -> List[OrderType]:
        return CONSTANTS.SUPPORTED_ORDER_TYPES

    def supported_position_modes(self) -> List[PositionMode]:
        return CONSTANTS.SUPPORTED_POSITION_MODES

    async def _update_account_address_and_create_order_hash_manager(self):
        if not self._order_placement_lock.locked():
            raise RuntimeError("The order-placement lock must be acquired before creating the order hash manager.")
        response: Dict[str, Any] = await self._get_gateway_instance().clob_injective_balances(
            chain=self._chain,
            network=self._network,
            address=self._sub_account_id
        )
        self._account_address: str = response["injectiveAddress"]

        await self._client.get_account(address=self._account_address)
        await self._client.sync_timeout_height()
        self._order_hash_manager = OrderHashManager(network=self._network_obj, sub_account_id=self._sub_account_id)
        await self._order_hash_manager.start()

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
        self._update_market_info()
        self._start_streams()

    async def stop(self):
        """
        Stops the event streaming.
        """
        await self._stop_streams()
        self._update_market_info_loop_task and self._update_market_info_loop_task.cancel()
        self._update_market_info_loop_task = None
        self._update_funding_info_loop_task and self

    def _get_gateway_instance(self) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        return gateway_instance

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

    async def set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """
        Leverage is set on a per order basis. See place_order()
        """
        return True, ""

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        """
        Leverage is set on a per order basis. See place_order()
        """
        if mode in self.supported_position_modes() and trading_pair in self._trading_pair_to_active_perp_markets:
            return True, ""
        return False, "Please check that Position Mode is supported and trading pair is active."

    # region >>> Trading Fee Function(s) >>>

    def get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = ...,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        return super().get_fee(
            base_currency, quote_currency, order_type, order_side, position_action, amount, price, is_maker
        )

    async def get_trading_fees(self) -> Mapping[str, MakerTakerExchangeFeeRates]:
        self._check_markets_initialized() or await self._update_market_info()

        trading_fees = {}
        for trading_pair, market in self._trading_pair_to_active_perp_markets.items():
            # Since we are using the API, we are the service provider.
            # Reference: https://api.injective.exchange/#overview-trading-fees-and-gas
            fee_scaler = Decimal("1") - Decimal(market.service_provider_fee)
            maker_fee = Decimal(market.maker_fee_rate) * fee_scaler
            taker_fee = Decimal(market.taker_fee_rate) * fee_scaler
            trading_fees[trading_pair] = MakerTakerExchangeFeeRates(
                maker=maker_fee, taker=taker_fee, maker_flat_fees=[], taker_flat_fees=[]
            )
        return trading_fees

    # endregion

    # region >>> Market Functions >>>

    async def get_symbol_map(self) -> bidict[str, str]:
        self._check_markets_initialized() or await self._update_market_info()

        mapping = bidict()
        for trading_pair, market in self._trading_pair_to_active_perp_markets.items():
            mapping[market.market_id] = trading_pair
        return mapping

    def _check_markets_initialized(self) -> bool:
        return (
            len(self._trading_pair_to_active_perp_markets) != 0
            and len(self._market_id_to_active_perp_markets) != 0
            and len(self._denom_to_token_meta) != 0
        )

    async def _fetch_derivative_markets(self) -> MarketsResponse:
        market_status: str = "active"
        return await self._client.get_derivative_markets(market_status=market_status)

    async def get_order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        market_info = self._trading_pair_to_active_perp_markets[trading_pair]
        response: OrderbookResponse = await self._client.get_derivative_orderbook(market_id=market_info.market_id)

        snapshot_ob: DerivativeLimitOrderbook = response.order_book
        snapshot_timestamp: float = max(
            [entry.timestamp for entry in list(response.orderbook.buys) + list(response.orderbook.sells)]
        )
        snapshot_content: Dict[str, Any] = {
            "trading_pair": combine_to_hb_trading_pair(base=market_info.oracle_base, quote=market_info.oracle_quote),
            "update_id": snapshot_timestamp,
            "bids": [(entry.price, entry.quantity) for entry in snapshot_ob.buys],
            "asks": [(entry.price, entry.quantity) for entry in snapshot_ob.sells],
        }

        snapshot_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT, content=snapshot_content, timestamp=snapshot_timestamp
        )
        return snapshot_msg

    def _update_market_map_attributes(self, response: MarketsResponse):
        "Parses MarketsResponse and re-populate the market map attributes"
        active_perp_markets: Dict[str, DerivativeMarketInfo] = {}
        market_id_to_market_map: Dict[str, DerivativeMarketInfo] = {}
        denom_to_token_meta_map: Dict[str, Union[Dict[str, Any], TokenMeta]] = {}
        for market in response.markets:
            trading_pair: str = combine_to_hb_trading_pair(base=market.oracle_base, quote=market.oracle_quote)
            market_id: str = market.market_id
            base_denom: str = market.oracle_base.upper()
            quote_demon: str = market.oracle_quote.upper()

            active_perp_markets[trading_pair] = market
            market_id_to_market_map[market_id] = market
            # Specifically for base token, Derivative API does not provide a Token Meta in the response.
            denom_to_token_meta_map[base_denom] = {"symbol": base_denom, "decimals": market.oracle_scale_factor}
            denom_to_token_meta_map[quote_demon] = market.quote_token_meta

        self._trading_pair_to_active_perp_markets.clear()
        self._market_id_to_active_perp_markets.clear()
        self._denom_to_token_meta.clear()

        self._trading_pair_to_active_perp_markets.update(active_perp_markets)
        self._market_id_to_active_perp_markets.update(market_id_to_market_map)
        self._denom_to_token_meta.update(denom_to_token_meta_map)

    async def _update_market_info(self):
        "Fetches and updates trading pair maps of active perpetual markets."
        response: MarketsResponse = await self._fetch_derivative_markets()
        self._update_market_map_attributes(response=response)

    async def _update_market_info_loop(self):
        while True:
            await self._sleep(delay=CONSTANTS.MARKETS_UPDATE_INTERVAL)
            await self._update_market_info()

    # endregion

    # region >>> User Account, Order & Position Management Function(s)

    async def place_order(
        self, order: GatewayInFlightOrder, **kwargs
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        # TODO: Use POST GatewayHTTPClient's /clob/orders here.
        market: DerivativeMarketInfo = self._trading_pair_to_active_perp_markets[order.trading_pair]
        perp_order_to_create = [
            self._composer.DerivativeOrder(
                market_id=market.market_id,
                subaccount_id=self._sub_account_id,
                fee_recipient=self._account_address,
                price=float(order.price),
                quantity=float(order.amount),
                is_buy=order.trade_type == TradeType.BUY,
                leverage=order.leverage,
                is_po=order.order_type == OrderType.LIMIT_MAKER,
            )
        ]
        async with self._order_placement_lock:
            order_hashes: List[str] = self._order_hash_manager.compute_order_hashes(
                derivative_orders=perp_order_to_create
            )
            order_hash: str = order_hashes.derivate[0]

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
                leverage=order.leverage
                # is_po=order.order_type == OrderType.LIMIT_MAKER
            )

            transaction_hash: Optional[str] = order_result.get("txHash")

            self.logger().debug(f"Placed order {order_hash} with tx hash {transaction_hash}")

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

    async def cancel_order(self, order: GatewayInFlightOrder) -> Tuple[bool, Optional[Dict[str, Any]]]:
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

        if transaction_hash is None:
            async with self._order_placement_lock:
                await self._update_account_address_and_create_order_hash_manager()
            raise ValueError(
                f"The cancelation transaction for {order.client_order_id} failed. Please ensure there is sufficient"
                f" INJ in the bank to cover transaction fees."
            )

        transaction_hash = f"0x{transaction_hash.lower()}"
        self.logger().debug(f"Canceled order {order.exchange_order_id} with tx hash {transaction_hash}")  # todo: remove

        misc_updates = {"cancelation_transaction_hash": transaction_hash}

        return True, misc_updates

    async def fetch_positions(self) -> List[Position]:
        positions: List[Position] = []

        response: Dict[str, Any] = await self._get_gateway_instance().clob_perp_positions(
            address=self._sub_account_id,
            chain=self._chain,
            connector=self._connector_name,
            network=self._network,
            trading_pairs=self._trading_pairs
        )

        positions: List[Dict[str, Any]] = response["positions"]
        for position in positions:
            market_info: DerivativeMarketInfo = self._market_id_to_active_perp_markets[position["marketId"]]

            trading_pair: str = combine_to_hb_trading_pair(base=market_info.oracle_base, quote=market_info.oracle_quote)
            position_side: PositionSide = PositionSide[position["direction"].upper()]
            amount: Decimal = Decimal(position["quantity"])

            scaler: Decimal = Decimal(f"1e-{market_info.oracle_scale_factor}")
            entry_price: Decimal = Decimal(position["entry_price"]) * scaler
            mark_price: Decimal = Decimal(position["mark_price"]) * scaler

            unrealized_pnl: Decimal = amount * ((1 / entry_price) - (1 / mark_price))

            positions.append(
                Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=Decimal(1),  # Simply a placeholder. To be updated using PerpetualTrading component
                )
            )
        return positions

    async def get_account_balances(self) -> Dict[str, Dict[str, Decimal]]:
        response: Dict[str, Any] = await self._get_gateway_instance().clob_injective_balances(
            chain=self._chain,
            network=self._network,
            address=self._sub_account_id
        )
        sub_acct_balances: List[Dict[str, Any]] = response["subaccounts"]
        balances: List[Dict[str, Any]] = []

        for entry in sub_acct_balances:
            if entry["subaccountId"] == self._sub_account_id:
                balances = entry["balances"]
                break

        balances_dict: Dict[str, Dict[str, Decimal]] = {}
        for balance in balances:
            asset_name = balance["token"]
            total_balance = Decimal(balance["totalBalance"])
            available_balance = Decimal(balance["availableBalance"])
            balances_dict[asset_name] = {
                "total_balance": total_balance,
                "available_balance": available_balance,
            }
        return balances_dict

    async def _fetch_order_fills(self, order: InFlightOrder) -> List[DerivativeTrade]:
        skip = 0
        all_trades: List[DerivativeTrade] = []
        search_completed = False

        market_info: DerivativeMarketInfo = self._trading_pair_to_active_perp_markets[order.trading_pair]

        market_id: str = market_info.market_id
        direction: str = "buy" if order.trade_type == TradeType.BUY else "sell"

        while not search_completed:
            trades = await self._client.get_derivative_trades(
                market_id=market_id,
                subaccount_id=self._sub_account_id,
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

    async def get_all_order_fills(self, in_flight_order: InFlightOrder) -> List[TradeUpdate]:
        trades: List[DerivativeTrade] = await self._fetch_order_fills(order=in_flight_order)

        trade_updates: List[TradeUpdate] = []
        for trade in trades:
            _, trade_update = self._parse_derivative_trade_message(trade_message=trade)
            trade_updates.append(trade_update)

        return trade_updates

    # endregion

    # region >>> Funding Payment Function(s) >>>

    async def fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")

        if trading_pair not in self._trading_pair_to_active_perp_markets:
            return timestamp, funding_rate, payment

        response: Dict[str, Any] = await self._get_gateway_instance().clob_perp_funding_payments(
            chain=self._chain,
            network=self._network,
            connector=self._connector_name,
            trading_pair=trading_pair,
            address=self._sub_account_id
        )

        latest_funding_payment: Dict[str, Any] = response["fundingPayments"][0]  # List of payments sorted by latest

        timestamp: float = latest_funding_payment.timestamp * 1e-3

        # FundingPayment does not include price, hence we have to fetch latest funding rate
        funding_rate: Decimal = await self._request_last_funding_rate(trading_pair=trading_pair)
        payment: Decimal = Decimal(latest_funding_payment["amount"])

        return timestamp, funding_rate, payment

    # endregion

    # region >>> Trading Rule Utility Functions >>>

    def _get_trading_rule_from_market(self, trading_pair: str, market: DerivativeMarketInfo) -> TradingRule:
        min_price_tick_size = Decimal(market.min_price_tick_size) * Decimal(f"1e-{market.oracle_scale_factor}")
        min_quantity_tick_size = Decimal(market.min_quantity_tick_size)
        trading_rule = TradingRule(
            trading_pair=trading_pair,
            min_order_size=min_quantity_tick_size,
            min_price_increment=min_price_tick_size,
            min_base_amount_increment=min_quantity_tick_size,
            min_quote_amount_increment=min_price_tick_size,
        )
        return trading_rule

    async def get_trading_rules(self) -> Dict[str, TradingRule]:
        self._check_markets_initialized() or await self._update_market_info()

        trading_rules = {
            trading_pair: self._get_trading_rule_from_market(trading_pair=trading_pair, market=market)
            for trading_pair, market in self._trading_pair_to_active_perp_markets.items()
        }
        return trading_rules

    # endregion <<< Trading Rule Utility Functions <<<

    # region >>> Funding Info Utility Functions >>>

    async def _request_last_funding_rate(self, trading_pair: str) -> Decimal:
        response: Dict[str, Any] = await self._get_gateway_instance().clob_perp_funding_rates(
            chain=self._chain,
            network=self._network,
            connector=self._connector_name,
            trading_pair=trading_pair
        )
        funding_rate: Dict[str, Any] = response["fundingRates"][0]  # We only want the latest funding rate.
        return Decimal(funding_rate["rate"])

    async def _request_oracle_price(self, market_info: DerivativeMarketInfo) -> Decimal:
        """
        According to Injective, Oracle Price refers to mark price.
        """
        response = await self._client.get_oracle_prices(
            base_symbol=market_info.oracle_base,
            quote_symbol=market_info.oracle_quote,
            oracle_type=market_info.oracle_type,
            oracle_scale_factor=market_info.oracle_scale_factor,
        )
        return Decimal(response.price)

    async def _request_last_trade_price(self, market_info: DerivativeMarketInfo) -> Decimal:
        response: TradesResponse = await self._client.get_derivative_trades(market_id=market_info.market_id)
        last_trade: DerivativeTrade = response.trades[0]
        scaler: Decimal = Decimal(market_info.oracle_scale_factor)
        last_trade_price: Decimal = Decimal(last_trade.position_delta.execution_price) * scaler
        return last_trade_price

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        # TODO: Update this to use clob_perp_funding_info
        self._check_markets_initialized() or await self._update_market_info()

        market_info: DerivativeMarketInfo = self._trading_pair_to_active_perp_markets.get(trading_pair, None)
        if market_info is not None:
            last_funding_rate: Decimal = await self._request_last_funding_rate(trading_pair=trading_pair)
            oracle_price: Decimal = await self._request_oracle_price(market_info=market_info)
            last_trade_price: Decimal = await self._request_last_trade_price(market_info=market_info)
            funding_info = FundingInfo(
                trading_pair=trading_pair,
                index_price=last_trade_price,  # Default to using last trade price
                mark_price=oracle_price,
                next_funding_utc_timestamp=market_info.next_funding_timestamp,
                rate=last_funding_rate,
            )
            return funding_info

    async def get_last_traded_price(self, trading_pair: str) -> Decimal:
        market_info: DerivativeMarketInfo = self._trading_pair_to_active_perp_markets[trading_pair]
        return await self._request_last_trade_price(market_info=market_info)

    # endregion

    # region >>> Stream Tasks & Parsing Functions >>>

    def _parse_derivative_ob_message(self, message: StreamOrdersResponse) -> OrderBookMessage:
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
        oracle_scale_factor: Decimal = Decimal(f"1e-{market.oracle_scale_factor}")
        bids = [(Decimal(bid.price) * oracle_scale_factor, Decimal(bid.quantity)) for bid in message.orderbook.buys]
        asks = [(Decimal(ask.price) * oracle_scale_factor, Decimal(ask.quantity)) for ask in message.orderbook.sells]
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

    def _process_order_book_stream_event(self, message: StreamOrdersResponse):
        snapshot_msg: OrderBookMessage = self._parse_derivative_ob_message(message == message)
        self._publisher.trigger_event(event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, message=snapshot_msg)

    async def _listen_to_order_books_stream(self):
        while True:
            market_ids: List[str] = list(self._market_id_to_active_perp_markets.keys())
            stream: UnaryStreamCall = await self._client.stream_derivative_orderbooks(market_ids=market_ids)
            try:
                async for ob_msg in stream:
                    self._process_order_book_stream_event(message=ob_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in orderbook listener loop.")
            self.logger().info("Restarting order books stream.")
            stream.cancel()

    def _parse_derivative_trade_message(self, trade_message: DerivativeTrade) -> Tuple[OrderBookMessage, TradeUpdate]:
        """
        DerivativeTrade Example:
        {
            order_hash: "0xab1d5fbc7c578d2e92f98d18fbeb7199539f84fe62dd474cce87737f0e0a8737"  # noqa: documentation
            subaccount_id: "0xc6fe5d33615a1c52c08018c47e8bc53646a0e101000000000000000000000000"  # noqa: documentation
            market_id: "0x90e662193fa29a3a7e6c07be4407c94833e762d9ee82136a2cc712d6b87d7de3"  # noqa: documentation
            trade_execution_type: "limitMatchNewOrder"
            position_delta {
                trade_direction: "sell"
                execution_price: "25111000000"
                execution_quantity: "0.0001"
                execution_margin: "2400000"
            }
            payout: "0"
            fee: "2511.1"
            executed_at: 1671745977284
            fee_recipient: "inj1cd0d4l9w9rpvugj8upwx0pt054v2fwtr563eh0"
            trade_id: "6205591_ab1d5fbc7c578d2e92f98d18fbeb7199539f84fe62dd474cce87737f0e0a8737"  # noqa: documentation
            execution_side: "taker"
        }
        """
        market_id: str = trade_message.market_id
        market: DerivativeMarketInfo = self._market_id_to_active_perp_markets[market_id]
        trading_pair: str = combine_to_hb_trading_pair(base=market.oracle_base, quote=market.oracle_quote)
        exchange_order_id: str = trade_message.order_hash

        tracked_order: GatewayInFlightOrder = self._gateway_order_tracker.all_fillable_orders_by_exchange_id.get(
            exchange_order_id, None
        )
        client_order_id: str = "" if tracked_order is None else tracked_order.client_order_id
        trade_id: str = trade_message.trade_id
        trade_type: TradeType = (
            TradeType.BUY if trade_message.position_delta.trade_direction == "buy" else TradeType.SELL
        )

        oracle_scale_factor: Decimal = Decimal(f"1e-{market.oracle_scale_factor}")
        price: Decimal = Decimal(trade_message.position_delta.execution_price) * oracle_scale_factor
        size: Decimal = Decimal(trade_message.position_delta.execution_quantity)
        is_taker: bool = trade_message.execution_side == "taker"

        fee_amount: Decimal = Decimal(trade_message.fee)
        _, quote = split_hb_trading_pair(trading_pair=trading_pair)
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=TradeFeeSchema(), trade_type=trade_type, flat_fees=[TokenAmount(amount=fee_amount, token=quote)]
        )

        trade_msg_content = {
            "trade_id": trade_id,
            "trading_pair": trading_pair,
            "trade_type": TradeType.BUY if trade_message.trade_direction == "buy" else TradeType.SELL,
            "amount": size,
            "price": price,
            "is_taker": is_taker,
        }
        trade_ob_msg = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            timestamp=trade_message.executed_at * 1e-3,
            content=trade_msg_content,
        )

        trade_update = TradeUpdate(
            trade_id=trade_id,
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            fill_timestamp=trade_message.executed_at * 1e-3,
            fill_price=price,
            fill_base_amount=size,
            fill_quote_amount=price * size,
            fee=fee,
        )
        return trade_ob_msg, trade_update

    def _process_trade_stream_event(self, message: StreamTradesResponse):
        trade_message: DerivativeTrade = message.trade
        trade_ob_msg, trade_update = self._parse_derivative_trade_message(trade_message=trade_message)

        self._publisher.trigger_event(event_tag=OrderBookDataSourceEvent.TRADE_EVENT, message=trade_ob_msg)
        self._publisher.trigger_event(event_tag=MarketEvent.TradeUpdate, message=trade_update)

    async def _listen_to_trades_stream(self):
        while True:
            market_ids: List[str] = list(self._market_id_to_active_perp_markets.keys())
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

    def _parse_balance_message(self, message: StreamSubaccountBalanceResponse) -> BalanceUpdateEvent:
        """
        Balance Balance Example:
        balance {
            subaccount_id: "0xc7dca7c15c364865f77a4fb67ab11dc95502e6fe000000000000000000000001"  # noqa: documentation
            account_address: "inj1clw20s2uxeyxtam6f7m84vgae92s9eh7vygagt"
            denom: "inj"
            deposit {
                available_balance: "9980001000000000000"
            }
            }
        timestamp: 1675902606000
        """
        subacct_balance: SubaccountBalance = message.balance
        denom_meta: Union[Dict[str, Any], TokenMeta] = self._denom_to_token_meta[subacct_balance.denom.upper()]
        if type(denom_meta) is TokenMeta:
            denom_scaler: Decimal = Decimal(f"1e-{denom_meta.decimals}")
        elif type(denom_meta) is Dict:
            denom_scaler: Decimal = Decimal(f"1e-{denom_meta['decimals']}")
        total_balance = subacct_balance.deposit.total_balance
        total_balance = Decimal(total_balance) * denom_scaler if total_balance != "" else None
        available_balance = subacct_balance.deposit.available_balance
        available_balance = Decimal(available_balance) * denom_scaler if available_balance != "" else None
        balance_msg = BalanceUpdateEvent(
            timestamp=subacct_balance.timestamp * 1e-3,
            asset_name=denom_meta.symbol,
            total_balance=total_balance,
            available_balance=available_balance,
        )
        return balance_msg

    def _process_balance_stream_event(self, message: StreamSubaccountBalanceResponse):
        balance_msg: BalanceUpdateEvent = self._parse_balance_message(message=message)
        self._publisher.trigger_event(event_tag=AccountEvent.BalanceEvent, message=balance_msg)

    async def _listen_to_account_balances_stream(self):
        while True:
            stream: UnaryStreamCall = await self._client.stream_subaccount_balance(subaccount_id=self._sub_account_id)
            try:
                async for balance_msg in stream:
                    self._process_balance_stream_event(message=balance_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in account balance listener loop.")
            self.logger().info("Restarting account balances stream.")
            stream.cancel()

    def _parse_order_update_from_order_history(
        self, order: GatewayInFlightOrder, order_history: DerivativeOrderHistory
    ) -> OrderUpdate:
        order_update: OrderUpdate = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=order_history.updated_at * 1e-3,
            new_state=CONSTANTS.INJ_DERIVATIVE_ORDER_STATES[order_history.state],
            client_order_id=order.client_order_id,
            exchange_order_id=order_history.order_hash,
        )
        return order_update

    async def _fetch_order_history(self, order: GatewayInFlightOrder) -> Optional[DerivativeOrderHistory]:
        """
        # TODO: Update to use clob_get_perp_orders
        """
        trading_pair: str = order.trading_pair
        order_hash: str = await order.get_exchange_order_id()

        market: DerivativeMarketInfo = self._trading_pair_to_active_perp_markets[trading_pair]
        direction: str = "buy" if order.trade_type == TradeType.BUY else "sell"
        trade_type: TradeType = order.trade_type
        order_type: OrderType = order.order_type

        order_history: Optional[DerivativeOrderHistory] = None
        skip = 0
        search_completed = False
        while not search_completed:
            # response: Dict[str, Any] = await self._get_gateway_instance().clob_get_perp_orders(
            #     chain=self._chain,
            #     network=self._network,
            #     connector=self._connector_name,
            #     owner_address=self._sub_account_id
            # )
            response: OrdersHistoryResponse = await self._client.get_historical_derivative_orders(
                market_id=market.market_id,
                subaccount_id=self._sub_account_id,
                direction=direction,
                start_time=int(order.creation_timestamp),
                limit=CONSTANTS.FETCH_ORDER_HISTORY_LIMIT,
                skip=skip,
                order_types=[CONSTANTS.CLIENT_TO_BACKEND_ORDER_TYPES_MAP[(trade_type, order_type)]],
            )
            if len(response.orders) == 0:
                search_completed = True
            else:
                skip += CONSTANTS.FETCH_ORDER_HISTORY_LIMIT
                for order in response.orders:
                    if order.order_hash == order_hash:
                        order_history = order
                        search_completed = True
                        break

        return order_history

    def _parse_failed_order_update_from_transaction_hash_response(
        self, order: GatewayInFlightOrder, response: GetTxByTxHashResponse
    ) -> Optional[OrderUpdate]:
        tx_detail: TxDetailData = response.data

        status_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=tx_detail.block_unix_timestamp * 1e-3,
            new_state=OrderState.FAILED,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
        )
        return status_update

    async def _check_if_order_failed_based_on_transaction(
        transaction: GetTxByTxHashResponse, order: GatewayInFlightOrder
    ) -> bool:
        order_hash = await order.get_exchange_order_id()
        return order_hash.lower() not in transaction.data.data.decode().lower()

    async def _fetch_transaction_by_hash(self, hash: str) -> GetTxByTxHashResponse:
        return await self._client.get_tx_by_hash(tx_hash=hash)

    async def get_order_status_update(self, in_flight_order: GatewayInFlightOrder) -> Tuple[OrderUpdate, OrderUpdate]:
        status_update: Optional[OrderUpdate] = None
        order_update: Optional[OrderUpdate] = None

        #  Fetch by Order History
        order_history: Optional[DerivativeOrderHistory] = await self._fetch_order_history(order=in_flight_order)
        if order_history is not None:
            status_update: OrderUpdate = self._parse_order_update_from_order_history(
                order=in_flight_order, order_history=order_history
            )

        # Determine if order has failed from transaction hash
        if status_update is None and in_flight_order.creation_transaction_hash is not None:
            tx_response: GetTxByTxHashResponse = await self._get_trans_fetch_transaction_by_hashaction_by_hash(
                hash=in_flight_order.creation_transaction_hash
            )
            if await self._check_if_order_failed_based_on_transaction(transaction=tx_response, order=in_flight_order):
                status_update: OrderUpdate = self._parse_failed_order_update_from_transaction_hash_response(
                    order=in_flight_order, response=tx_response
                )

        if status_update is None:
            raise ValueError(f"No update found for order {in_flight_order.client_order_id}")

        if in_flight_order.current_state == OrderState.PENDING_CREATE and status_update.new_state != OrderState.OPEN:
            order_update = OrderUpdate(
                trading_pair=in_flight_order.trading_pair,
                update_timestamp=status_update.update_timestamp,
                new_state=OrderState.OPEN,
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=status_update.exchange_order_id,
            )

        return status_update, order_update

    async def _process_transaction_event(self, transaction: StreamTxsResponse):
        order: GatewayInFlightOrder = self._gateway_order_tracker.get_fillable_order_by_hash(hash=transaction.hash)
        if order is not None:
            messages = json.loads(s=transaction.message)
            for message in messages:
                if message["type"] in [CONSTANTS.INJ_DERIVATIVE_ORDER_STATES]:
                    status_update, order_update = await self.get_order_status_update(in_flight_order=order)
                    if status_update is not None:
                        self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=status_update)
                    if order_update is not None:
                        self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=order_update)

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
        order_update: DerivativeOrderHistory = message.order
        order_hash: str = order_update.order_hash

        in_flight_order = self._gateway_order_tracker.all_fillable_orders_by_exchange_id.get(order_hash)
        if in_flight_order is not None:
            market_id = order_update.market_id
            trading_pair = self._get_trading_pair_from_market_id(market_id=market_id)
            order_update = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=order_update.updated_at * 1e-3,
                new_state=CONSTANTS.INJ_DERIVATIVE_ORDER_STATES[order_update.state],
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=order_update.order_hash,
            )
            if in_flight_order.current_state == OrderState.PENDING_CREATE and order_update.new_state != OrderState.OPEN:
                open_update = OrderUpdate(
                    trading_pair=trading_pair,
                    update_timestamp=order_update.updated_at * 1e-3,
                    new_state=OrderState.OPEN,
                    client_order_id=in_flight_order.client_order_id,
                    exchange_order_id=order_update.order_hash,
                )
                self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=open_update)
            self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=order_update)

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
        position: DerivativePosition = message.position
        market_info: DerivativeMarketInfo = self._market_id_to_active_perp_markets[position.market_id]
        trading_pair: str = combine_to_hb_trading_pair(base=market_info.oracle_base, quote=market_info.oracle_quote)
        position_side: PositionSide = PositionSide[position.direction.upper()]
        scaler: Decimal = Decimal(f"1e-{market_info.oracle_scale_factor}")
        entry_price: Decimal = Decimal(position.entry_price) * scaler
        mark_price: Decimal = Decimal(position.mark_price) * scaler
        amount: Decimal = Decimal(position.quantity)

        unrealized_pnl: Decimal = amount * ((1 / entry_price) - (1 / mark_price))

        position: Position = Position(
            trading_pair=trading_pair,
            position_side=position_side,
            unrealized_pnl=unrealized_pnl,
            entry_price=entry_price,
            amount=amount,
            leverage=Decimal("-1"),  # Injective does not provide information on the leverage of a position here.
        )

        self._publisher.trigger_event(event_tag=AccountEvent.PositionUpdate, message=position)

    async def _listen_to_positions_stream(self):
        while True:
            market_ids: List[str] = ",".join(list(self._market_id_to_active_perp_markets.keys()))
            stream: UnaryStreamCall = await self._client.stream_derivative_positions(
                market_ids=market_ids, subaccount_id=self._sub_account_id
            )
            try:
                async for order in stream:
                    await self._process_position_event(order=order)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in position listener loop.")
            self.logger().info("Restarting position stream.")
            stream.cancel()

    async def parse_funding_info_message(self, raw_message: FundingInfoUpdate, message_queue: asyncio.Queue):
        message_queue.put_nowait(raw_message)

    async def _process_funding_info_event(self, market_info: DerivativeMarketInfo, message: StreamPricesResponse):
        trading_pair: str = combine_to_hb_trading_pair(base=market_info.oracle_base, quote=market_info.oracle_quote)
        oracle_price: Decimal = Decimal(message.price)
        # We need to fetch misssing information with another API call since not all info is provided in the stream.
        last_funding_rate: Decimal = await self._request_last_funding_rate(trading_pair=trading_pair)
        last_trade_price: Decimal = await self._request_last_trade_price(market_info=market_info)
        funding_info = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=last_trade_price,  # Default to using last trade price
            mark_price=oracle_price,
            next_funding_utc_timestamp=market_info.next_funding_timestamp,
            rate=last_funding_rate,
        )
        self._publisher.trigger_event(event_tag=MarketEvent.FundingInfo, message=funding_info)

    async def _listen_to_funding_info_stream(self, market_info: DerivativeMarketInfo):
        while True:
            stream: UnaryStreamCall = await self._client.stream_oracle_prices(
                base_symbol=market_info.oracle_base,
                quote_symbol=market_info.oracle_quote,
                oracle_type=market_info.oracle_type
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
        self._account_balances_stream_listener = self._account_balances_stream_listener or safe_ensure_future(
            coro=self._listen_to_account_balances_stream()
        )
        self._transactions_stream_listener = self._transactions_stream_listener or safe_ensure_future(
            coro=self._listen_to_transactions_stream()
        )
        self._positions_stream_listener = self._positions_stream_listener or safe_ensure_future(
            coro=self._listen_to_positions_stream()
        )
        for market_id in [self._trading_pair_to_active_perp_markets[tp].market_id for tp in self._trading_pairs]:
            if market_id not in self._order_listeners:
                self._order_listeners[market_id] = safe_ensure_future(
                    coro=self._listen_order_updates_stream(market_id=market_id)
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
        self._positions_stream_listener and self._positions_stream_listener.cancel()
        self._positions_stream_listener = None

    # endregion
