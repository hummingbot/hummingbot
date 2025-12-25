import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from hummingbot.connector.derivative_base import DerivativeBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

from .evedex_perpetual_api_order_book_data_source import EvedexPerpetualAPIOrderBookDataSource
from .evedex_perpetual_api_user_stream_data_source import EvedexPerpetualAPIUserStreamDataSource
from .evedex_perpetual_auth import EvedexPerpetualAuth
from . import (
    evedex_perpetual_constants as CONSTANTS,
    evedex_perpetual_utils as utils,
    evedex_perpetual_web_utils as web_utils,
)

logger = logging.getLogger(__name__)


class EvedexPerpetualExchange(DerivativeBase):
    web_utils = web_utils
    
    def __init__(
        self,
        evedex_perpetual_api_key: str = "",
        evedex_perpetual_api_secret: str = "",
        evedex_perpetual_wallet_address: str = "",
        evedex_perpetual_env: str = "demo",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        self._api_key = evedex_perpetual_api_key
        self._api_secret = evedex_perpetual_api_secret
        self._wallet_address = evedex_perpetual_wallet_address
        self._environment = evedex_perpetual_env
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs or []
        
        auth_base_url = web_utils.get_rest_url(self._environment)
        self._auth = EvedexPerpetualAuth(
            api_key=self._api_key,
            api_secret=self._api_secret,
            wallet_address=self._wallet_address,
            auth_base_url=auth_base_url,
        )
        
        super().__init__()
        
        self._rest_base_url = web_utils.get_rest_url(self._environment)
        self._ws_base_url = web_utils.get_ws_url(self._environment)
        
        self._throttler = web_utils.build_api_throttler()
        
        self._web_assistants_factory: Optional[WebAssistantsFactory] = None
        
        self._order_book_data_source: Optional[EvedexPerpetualAPIOrderBookDataSource] = None
        self._user_stream_data_source: Optional[EvedexPerpetualAPIUserStreamDataSource] = None
        
        self._trading_rules: Dict[str, TradingRule] = {}
        self._position_mode = PositionMode.ONEWAY
        self._leverage: Dict[str, int] = {}
        self._instrument_scales: Dict[str, Dict[str, int]] = {}
        
        self._user_stream_tracker_task: Optional[asyncio.Task] = None
        self._trading_rules_polling_task: Optional[asyncio.Task] = None
        
    @property
    def name(self) -> str:
        return "evedex_perpetual"
    
    @property
    def rate_limits_rules(self) -> List:
        return CONSTANTS.RATE_LIMITS
    
    @property
    def domain(self) -> str:
        return self._environment
    
    @property
    def client_order_id_max_length(self) -> int:
        return 32  # DDDDD:26hex format
    
    @property
    def client_order_id_prefix(self) -> str:
        return ""
    
    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.ENDPOINTS["instrument_list"]
    
    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.ENDPOINTS["instrument_list"]
    
    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.ENDPOINTS["instrument_list"]
    
    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs
    
    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False
    
    @property
    def is_trading_required(self) -> bool:
        return self._trading_required
    
    @property
    def funding_fee_poll_interval(self) -> int:
        return 60  # Poll every minute
    
    def supported_order_types(self) -> List[OrderType]:
        return [
            OrderType.LIMIT,
            OrderType.LIMIT_MAKER,
            OrderType.MARKET,
        ]
    
    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]
    
    def get_buy_collateral_token(self, trading_pair: str) -> str:
        _, quote = utils.split_trading_pair(trading_pair)
        return quote
    
    def get_sell_collateral_token(self, trading_pair: str) -> str:
        _, quote = utils.split_trading_pair(trading_pair)
        return quote
    
    async def start_network(self):
        await super().start_network()
        
        self._web_assistants_factory = await self._get_web_assistants_factory()
        
        if self._trading_required and self._wallet_address:
            # TODO: SIWE authentication
            logger.info("SIWE authentication not yet implemented, using API key only")
        
        await self._initialize_data_sources()
        
        self._trading_rules_polling_task = safe_ensure_future(
            self._trading_rules_polling_loop()
        )
        
    async def stop_network(self):
        await super().stop_network()
        
        if self._user_stream_tracker_task:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        
        if self._trading_rules_polling_task:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
    
    async def _get_web_assistants_factory(self) -> WebAssistantsFactory:
        return WebAssistantsFactory(
            throttler=self._throttler,
        )
    
    async def _initialize_data_sources(self):
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        ws_assistant = await self._web_assistants_factory.get_ws_assistant()
        
        self._order_book_data_source = EvedexPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            rest_assistant=rest_assistant,
            ws_assistant=ws_assistant,
            throttler=self._throttler,
            environment=self._environment,
        )
        
        if self._trading_required:
            ws_assistant_user = await self._web_assistants_factory.get_ws_assistant()
            self._user_stream_data_source = EvedexPerpetualAPIUserStreamDataSource(
                auth=self._auth,
                ws_assistant=ws_assistant_user,
                throttler=self._throttler,
                environment=self._environment,
            )
    
    async def check_network(self) -> NetworkStatus:
        try:
            await self._order_book_data_source.get_instruments()
            return NetworkStatus.CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
    
    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60)  # Update every minute
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error updating trading rules: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def _update_trading_rules(self):
        try:
            instruments = await self._order_book_data_source.get_instruments(
                force_refresh=True
            )
            
            trading_rules = {}
            for instrument_id, info in instruments.items():
                try:
                    trading_pair = utils.to_trading_pair(instrument_id)
                    
                    price_scale = info.get(CONSTANTS.INSTRUMENT_PRICE_SCALE_KEY, 2)
                    qty_scale = info.get(CONSTANTS.INSTRUMENT_QTY_SCALE_KEY, 3)
                    tick_size = info.get(CONSTANTS.INSTRUMENT_TICK_SIZE_KEY, "0.01")
                    lot_size = info.get(CONSTANTS.INSTRUMENT_LOT_SIZE_KEY, "0.001")
                    min_order_size = info.get("minOrderSize", "0.001")
                    
                    self._instrument_scales[trading_pair] = {
                        "price_scale": price_scale,
                        "qty_scale": qty_scale,
                    }
                    
                    trading_rule = TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(str(min_order_size)),
                        min_price_increment=Decimal(str(tick_size)),
                        min_base_amount_increment=Decimal(str(lot_size)),
                        min_notional_size=Decimal("1.0"),
                    )
                    
                    trading_rules[trading_pair] = trading_rule
                    
                except Exception as e:
                    logger.warning(
                        f"Failed to create trading rule for {instrument_id}: {e}"
                    )
            
            self._trading_rules = trading_rules
            logger.info(
                f"Updated trading rules for {len(trading_rules)} pairs "
                f"with scales: {list(self._instrument_scales.keys())}"
            )
            
        except Exception as e:
            logger.error(f"Failed to update trading rules: {e}", exc_info=True)

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.OPEN,
        **kwargs
    ) -> Tuple[str, float]:
        """
        Place order on exchange.
        
        Returns:
            Tuple of (exchange_order_id, timestamp)
        """
        instrument = utils.to_exchange_symbol(trading_pair)
        
        # Get trading rule for validation
        trading_rule = self._trading_rules.get(trading_pair)
        if not trading_rule:
            raise ValueError(f"No trading rule found for {trading_pair}")
        
        scales = self._instrument_scales.get(trading_pair)
        if not scales:
            raise ValueError(
                f"No scale information for {trading_pair}. "
                f"Trading rules may not be initialized yet."
            )
        
        price_scale = scales["price_scale"]
        qty_scale = scales["qty_scale"]
        
        price_float = float(price) if order_type != OrderType.MARKET else 0
        amount_float = float(amount)
        
        utils.validate_order_params(
            price=price_float if order_type != OrderType.MARKET else None,
            quantity=amount_float,
            order_type=order_type.name.lower()
        )
        
        if order_type != OrderType.MARKET:
            price_int, qty_int = utils.normalize_price_qty(
                price_float, amount_float, price_scale, qty_scale
            )
        else:
            qty_int = int(amount_float * (10 ** qty_scale))
            price_int = 0
        
        side = "buy" if trade_type == TradeType.BUY else "sell"
        
        if order_type == OrderType.MARKET:
            order_type_str = "MARKET"
            time_in_force = "IOC"
        elif order_type == OrderType.LIMIT_MAKER:
            order_type_str = "LIMIT"
            time_in_force = "GTC"
        else:  # OrderType.LIMIT
            order_type_str = "LIMIT"
            time_in_force = "GTC"
        
        payload = {
            "orderId": order_id,
            "instrument": instrument,
            "side": side,
            "quantity": qty_int,
            "type": order_type_str,
            "timeInForce": time_in_force,
        }
        
        if order_type != OrderType.MARKET:
            payload["price"] = price_int
        
        if order_type == OrderType.LIMIT_MAKER:
            payload["postOnly"] = True
        
        if position_action == PositionAction.CLOSE:
            payload["reduceOnly"] = True
        
        if order_type == OrderType.MARKET:
            endpoint = CONSTANTS.ENDPOINTS["order_market_v2"]
        else:
            endpoint = CONSTANTS.ENDPOINTS["order_limit_v2"]
        
        url = f"{self._rest_base_url}{endpoint}"
        headers = self._auth.get_headers()
        timestamp = utils.get_timestamp_ms()
        
        # Sign the request
        if self._api_secret:
            signature = utils.sign_request(
                secret=self._api_secret,
                method="POST",
                path=endpoint,
                timestamp=timestamp,
                body=payload
            )
            headers["X-Signature"] = signature
            headers["X-Timestamp"] = str(timestamp)
        else:
            logger.warning("No API secret provided, request may fail")
        
        try:
            response = await web_utils.api_request(
                rest_assistant=await self._web_assistants_factory.get_rest_assistant(),
                method=web_utils.RESTMethod.POST,
                url=url,
                data=payload,
                headers=headers,
                throttler_limit_id="place_order",
            )
            
            exchange_order_id = response.get("orderId", order_id)
            timestamp = response.get("t", utils.get_timestamp_ms()) / 1000.0
            
            logger.info(
                f"Order placed: {order_id} -> {exchange_order_id} "
                f"({side} {amount} {trading_pair} @ {price if order_type != OrderType.MARKET else 'MARKET'})"
            )
            
            return exchange_order_id, timestamp
            
        except web_utils.EvedexPerpetualAuthError:
            logger.warning("Authentication error, token may be expired")
            self._auth.invalidate_tokens()
            raise
        except Exception as e:
            logger.error(f"Failed to place order: {e}", exc_info=True)
            raise
    
    async def _place_cancel(
        self,
        order_id: str,
        tracked_order: InFlightOrder
    ) -> bool:
        # Cancel endpoint doesn't require signature
        endpoint = CONSTANTS.ENDPOINTS["order_cancel"].format(order_id=order_id)
        url = f"{self._rest_base_url}{endpoint}"
        headers = self._auth.get_headers()
        
        try:
            await web_utils.api_request(
                rest_assistant=await self._web_assistants_factory.get_rest_assistant(),
                method=web_utils.RESTMethod.DELETE,
                url=url,
                headers=headers,
                throttler_limit_id="orders",
            )
            
            logger.info(f"Order cancelled: {order_id}")
            return True
            
        except web_utils.EvedexPerpetualAPIError as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def _update_balances(self):
        if not self._trading_required:
            return
        
        endpoint = CONSTANTS.ENDPOINTS["available_balance"]
        url = f"{self._rest_base_url}{endpoint}"
        headers = self._auth.get_headers()
        
        try:
            response = await web_utils.api_request(
                rest_assistant=await self._web_assistants_factory.get_rest_assistant(),
                method=web_utils.RESTMethod.GET,
                url=url,
                headers=headers,
                throttler_limit_id="private",
            )
            
            # Parse balances
            for currency, balance_data in response.items():
                if isinstance(balance_data, dict):
                    total = Decimal(str(balance_data.get("total", 0)))
                    available = Decimal(str(balance_data.get("available", 0)))
                    
                    self._account_available_balances[currency] = available
                    self._account_balances[currency] = total
            
            logger.debug(f"Updated balances: {len(self._account_balances)} currencies")
            
        except web_utils.EvedexPerpetualAuthError:
            logger.warning("Authentication required to fetch balances")
            self._auth.invalidate_tokens()
        except Exception as e:
            logger.error(f"Failed to update balances: {e}")
    
    async def _update_order_status(self):
        if not self._trading_required:
            return
        
        # Get open orders
        endpoint = CONSTANTS.ENDPOINTS["order_status"]
        url = f"{self._rest_base_url}{endpoint}"
        headers = self._auth.get_headers()
        
        try:
            response = await web_utils.api_request(
                rest_assistant=await self._web_assistants_factory.get_rest_assistant(),
                method=web_utils.RESTMethod.GET,
                url=url,
                headers=headers,
                throttler_limit_id="private",
            )
            
            open_orders = response.get("orders", [])
            
            for order_data in open_orders:
                order_id = order_data.get("orderId")
                if order_id in self._order_tracker.all_fillable_orders_by_exchange_order_id:
                    tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id[order_id]
                    
                    # Update order state
                    order_update = OrderUpdate(
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=utils.parse_timestamp(order_data.get("t")),
                        new_state=self._parse_order_status(order_data.get("status")),
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=order_id,
                    )
                    
                    self._order_tracker.process_order_update(order_update)
            
        except Exception as e:
            logger.error(f"Failed to update order status: {e}")
    
    def _parse_order_status(self, status: str) -> OrderState:
        status_map = {
            "NEW": OrderState.OPEN,
            "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
            "FILLED": OrderState.FILLED,
            "CANCELLED": OrderState.CANCELLED,
            "REJECTED": OrderState.FAILED,
            "EXPIRED": OrderState.CANCELLED,
        }
        return status_map.get(status, OrderState.FAILED)
    
    async def _update_positions(self):
        if not self._trading_required:
            return
        
        endpoint = CONSTANTS.ENDPOINTS["positions"]
        url = f"{self._rest_base_url}{endpoint}"
        headers = self._auth.get_headers()
        
        try:
            response = await web_utils.api_request(
                rest_assistant=await self._web_assistants_factory.get_rest_assistant(),
                method=web_utils.RESTMethod.GET,
                url=url,
                headers=headers,
                throttler_limit_id="private",
            )
            
            positions = response.get("positions", [])
            
            for pos_data in positions:
                instrument = pos_data.get("instrument")
                trading_pair = utils.to_trading_pair(instrument)
                
                position_side = pos_data.get("side", "").upper()
                amount = Decimal(str(pos_data.get("quantity", 0)))
                entry_price = Decimal(str(pos_data.get("entryPrice", 0)))
                leverage = Decimal(str(pos_data.get("leverage", 1)))
                unrealized_pnl = Decimal(str(pos_data.get("unrealizedPnl", 0)))
                
                # Update internal position tracking
                # TODO: Integrate with Hummingbot position tracking
                
                logger.debug(
                    f"Position: {trading_pair} {position_side} "
                    f"{amount}@{entry_price} (PnL: {unrealized_pnl})"
                )
                
        except Exception as e:
            logger.error(f"Failed to update positions: {e}")
    
    async def _update_trading_fees(self):
        for trading_pair in self._trading_pairs:
            self._trading_fees[trading_pair] = TradeFeeBase(
                percent=Decimal(str(CONSTANTS.DEFAULT_FEES["maker_percent_fee"])),
                percent_token=self.get_buy_collateral_token(trading_pair),
            )
    
    async def _user_stream_event_listener(self):
        if not self._user_stream_data_source:
            return
        
        output_queue = asyncio.Queue()
        
        # Start listening task
        listen_task = safe_ensure_future(
            self._user_stream_data_source.listen_for_user_stream(output_queue)
        )
        
        try:
            while True:
                try:
                    event = await asyncio.wait_for(output_queue.get(), timeout=1.0)
                    event_type = event.get("type")
                    
                    if event_type == "order_update":
                        await self._process_order_update(event)
                    elif event_type == "order_fill":
                        await self._process_order_fill(event)
                    elif event_type == "balance_update":
                        await self._process_balance_update(event)
                    elif event_type == "position_update":
                        await self._process_position_update(event)
                    elif event_type == "funding_payment":
                        await self._process_funding_payment(event)
                        
                except asyncio.TimeoutError:
                    continue
                    
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"User stream error: {e}", exc_info=True)
        finally:
            listen_task.cancel()
    
    async def _process_order_update(self, event: Dict):
        """Process order update event."""
        exchange_order_id = event.get("order_id")
        client_order_id = event.get("client_order_id")
        if not exchange_order_id and not client_order_id:
            return
        
        tracked_order = self._order_tracker.fetch_order(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
        )
        if not tracked_order:
            return
        
        order_update = OrderUpdate(
            trading_pair=event.get("trading_pair"),
            update_timestamp=event.get("timestamp"),
            new_state=self._parse_order_status(event.get("status")),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id or tracked_order.exchange_order_id,
        )
        
        self._order_tracker.process_order_update(order_update)
    
    async def _process_order_fill(self, event: Dict):
        exchange_order_id = event.get("order_id")
        client_order_id = event.get("client_order_id")
        if not exchange_order_id and not client_order_id:
            return
        
        tracked_order = self._order_tracker.fetch_order(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
        )
        if not tracked_order:
            return
        
        fee = TradeFeeBase(
            percent=Decimal("0"),
            flat_fees=[TokenAmount(
                token=event.get("fee_currency", "USD"),
                amount=Decimal(str(event.get("fee", 0)))
            )]
        )
        
        trade_update = TradeUpdate(
            trade_id=event.get("execution_id"),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id or tracked_order.exchange_order_id,
            trading_pair=event.get("trading_pair") or tracked_order.trading_pair,
            fill_timestamp=event.get("timestamp"),
            fill_price=Decimal(str(event.get("price", 0))),
            fill_base_amount=Decimal(str(event.get("quantity", 0))),
            fill_quote_amount=Decimal(str(event.get("price", 0))) * Decimal(str(event.get("quantity", 0))),
            fee=fee,
        )
        
        self._order_tracker.process_trade_update(trade_update)
    
    async def _process_balance_update(self, event: Dict):
        currency = event.get("currency")
        if currency:
            self._account_balances[currency] = Decimal(str(event.get("total_balance", 0)))
            self._account_available_balances[currency] = Decimal(str(event.get("available_balance", 0)))
    
    async def _process_position_update(self, event: Dict):
        # TODO: Update position tracking
        logger.debug(f"Position update: {event}")
    
    async def _process_funding_payment(self, event: Dict):
        # TODO: Track funding payments
        logger.debug(f"Funding payment: {event}")
    
    def _create_order_book_data_source(self) -> EvedexPerpetualAPIOrderBookDataSource:
        return self._order_book_data_source
    
    def _create_user_stream_data_source(self) -> EvedexPerpetualAPIUserStreamDataSource:
        return self._user_stream_data_source
    
    async def _get_position_mode(self) -> Optional[PositionMode]:
        return self._position_mode
    
    async def _set_position_mode(self, position_mode: PositionMode):
        self._position_mode = position_mode
        logger.info(f"Position mode set to: {position_mode}")
    
    async def _set_leverage(self, trading_pair: str, leverage: int):
        instrument = utils.to_exchange_symbol(trading_pair)
        endpoint = CONSTANTS.ENDPOINTS["position_leverage"].format(instrument=instrument)
        url = f"{self._rest_base_url}{endpoint}"
        headers = self._auth.get_headers()
        
        payload = {"leverage": leverage}
        
        try:
            await web_utils.api_request(
                rest_assistant=await self._web_assistants_factory.get_rest_assistant(),
                method=web_utils.RESTMethod.PUT,
                url=url,
                data=payload,
                headers=headers,
                throttler_limit_id="private",
            )
            
            self._leverage[trading_pair] = leverage
            logger.info(f"Leverage set to {leverage}x for {trading_pair}")
            
        except Exception as e:
            logger.error(f"Failed to set leverage: {e}")
    
    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        # TODO: Implement funding fee fetching
        return 0, Decimal("0"), Decimal("0")
    
    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = Decimal("NaN"),
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        """Calculate trading fee."""
        is_maker = is_maker or (order_type == OrderType.LIMIT_MAKER)
        
        fee_percent = (
            CONSTANTS.DEFAULT_FEES["maker_percent_fee"]
            if is_maker
            else CONSTANTS.DEFAULT_FEES["taker_percent_fee"]
        )
        
        return TradeFeeBase(
            percent=Decimal(str(fee_percent / 100)),
            percent_token=quote_currency,
        )
