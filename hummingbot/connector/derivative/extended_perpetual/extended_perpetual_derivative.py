import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.extended_perpetual import (
    extended_perpetual_constants as CONSTANTS,
    extended_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.extended_perpetual.extended_perpetual_api_order_book_data_source import (
    ExtendedPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.extended_perpetual.extended_perpetual_api_user_stream_data_source import (
    ExtendedPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.extended_perpetual.extended_perpetual_auth import ExtendedPerpetualAuth
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class ExtendedPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
        self,
        extended_perpetual_api_key: str,
        extended_perpetual_stark_public_key: str,
        extended_perpetual_stark_private_key: str,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        # Store parameters first
        self.extended_perpetual_api_key = extended_perpetual_api_key
        self.extended_perpetual_stark_public_key = extended_perpetual_stark_public_key
        self.extended_perpetual_stark_private_key = extended_perpetual_stark_private_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = PositionMode.ONEWAY  # Extended uses one-way position mode
        self._last_trade_history_timestamp = None
        
        super().__init__(balance_asset_limit, rate_limits_share_pct)
        
        # Log after super().__init__() so logger is available
        self.logger().info(f"🚀 EXTENDED PERPETUAL __INIT__ CALLED WITH:")
        self.logger().info(f"🚀   trading_pairs parameter: {trading_pairs}")
        self.logger().info(f"🚀   self._trading_pairs: {self._trading_pairs}")
        self.logger().info(f"🚀   API Key: {extended_perpetual_api_key[:10]}...")
        self.logger().info(f"🚀 Trading required: {self._trading_required}")

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> ExtendedPerpetualAuth:
        # Always create authenticator if API keys are provided
        # Extended requires auth for balance and other read-only endpoints
        self.logger().info(f"🔐 Creating ExtendedPerpetualAuth with API key: {self.extended_perpetual_api_key[:10]}...")
        auth = ExtendedPerpetualAuth(
            self.extended_perpetual_api_key,
            self.extended_perpetual_stark_public_key,
            self.extended_perpetual_stark_private_key
        )
        self.logger().info(f"🔐 ExtendedPerpetualAuth created successfully")
        return auth

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_URL

    @property
    def funding_fee_poll_interval(self) -> int:
        return CONSTANTS.FUNDING_RATE_UPDATE_INTERNAL_SECOND

    @property
    def trading_pairs(self):
        return self._trading_pairs if self._trading_pairs else []

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]
    
    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        Override to add debug logging for connector status
        """
        status = super().status_dict
        
        # Log each status component safely
        self.logger().info("=" * 60)
        self.logger().info("🔍 CONNECTOR STATUS CHECK")
        for key, value in status.items():
            symbol = "✅" if value else "❌"
            self.logger().info(f"{symbol} {key}: {value}")
        self.logger().info("=" * 60)
        
        return status

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return CONSTANTS.CURRENCY

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return CONSTANTS.CURRENCY

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        error_message = str(status_update_exception).lower()
        return "not found" in error_message or "does not exist" in error_message

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        error_message = str(cancelation_exception).lower()
        return "not found" in error_message or "does not exist" in error_message

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            domain=self._domain,
            auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        print(f"📚 Creating order book data source with trading_pairs: {self._trading_pairs}")
        self.logger().info(f"📚 Creating order book data source with trading_pairs: {self._trading_pairs}")
        return ExtendedPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return ExtendedPerpetualAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        
        if trading_pair in self._trading_fees:
            fees_data = self._trading_fees[trading_pair]
            fee_value = Decimal(fees_data["maker"]) if is_maker else Decimal(fees_data["taker"])
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=PositionAction.OPEN,
                percent_token=CONSTANTS.CURRENCY,
                flat_fees=[TokenAmount(amount=fee_value * amount * price, token=CONSTANTS.CURRENCY)]
            )
        else:
            fee = build_trade_fee(
                self.name,
                is_maker,
                base_currency=base_currency,
                quote_currency=quote_currency,
                order_type=order_type,
                order_side=order_side,
                amount=amount,
                price=price,
            )
        return fee

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        
        self.logger().info("=" * 60)
        self.logger().info("🔄 INITIALIZING TRADING PAIRS FROM EXTENDED")
        self.logger().info("=" * 60)
        self.logger().info(f"Exchange info type: {type(exchange_info)}")
        self.logger().info(f"Exchange info keys: {list(exchange_info.keys()) if isinstance(exchange_info, dict) else 'Not a dict'}")
        self.logger().info(f"Exchange info (first 500 chars): {str(exchange_info)[:500]}")
        
        # Extended returns: {"status": "OK", "data": [array of markets]}
        # Extract the markets array from the nested structure
        if isinstance(exchange_info, dict) and "data" in exchange_info:
            markets = exchange_info.get("data", [])
            self.logger().info(f"✅ Extracted markets from 'data' key")
        elif isinstance(exchange_info, list):
            markets = exchange_info
            self.logger().info(f"✅ Exchange info is already a list")
        else:
            markets = []
            self.logger().error(f"❌ Unexpected exchange_info format: {type(exchange_info)}")
        
        self.logger().info(f"Found {len(markets)} markets to process")
        
        valid_pairs = 0
        for market_data in markets:
            if not isinstance(market_data, dict):
                continue
            
            # Extended uses "name" for market identifier
            market_name = market_data.get("name")
            if not market_name:
                continue
            
            # Check if market is active
            status = market_data.get("status", "").upper()
            if status not in ["ACTIVE", "REDUCE_ONLY"]:
                self.logger().debug(f"Skipping market {market_name} with status {status}")
                continue
            
            # Parse market name: "BTC-USD" -> BTC-USDC (for Hummingbot)
            if "-" in market_name:
                parts = market_name.split("-")
                if len(parts) == 2:
                    base = parts[0]
                    # Extended uses USD but settles in USDC
                    quote = "USDC" if parts[1] == "USD" else parts[1]
                    hb_pair = combine_to_hb_trading_pair(base, quote)
                    mapping[market_name] = hb_pair
                    valid_pairs += 1
                    self.logger().info(f"✅ Mapped: {market_name} -> {hb_pair}")
        
        self.logger().info("=" * 60)
        self.logger().info(f"✅ TOTAL PAIRS MAPPED: {valid_pairs}")
        self.logger().info(f"Available markets: {list(mapping.values())[:10]}...")
        self.logger().info("=" * 60)
        
        if valid_pairs == 0:
            self.logger().error("❌ NO TRADING PAIRS MAPPED! Check exchange_info format")
        
        self._set_trading_pair_symbol_map(mapping)

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ) -> Tuple[str, float]:
        """
        Place an order on Extended perpetual exchange
        """
        market_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        side = "buy" if trade_type == TradeType.BUY else "sell"
        
        data = {
            "market_id": market_id,
            "side": side,
            "size": str(amount),
            "client_order_id": order_id,
        }
        
        if order_type.is_limit_type():
            data["type"] = "limit"
            data["price"] = str(price)
            data["time_in_force"] = "GTT"
            # Extended requires expiration timestamp (max 90 days)
            import time
            expiration = int((time.time() + 86400 * 7) * 1000)  # 7 days from now
            data["expiration"] = expiration
        else:
            data["type"] = "market"
        
        if order_type is OrderType.LIMIT_MAKER:
            data["post_only"] = True
        
        # Add Stark signature
        stark_signature = self._auth.generate_stark_signature(data)
        data["stark_signature"] = stark_signature
        data["stark_public_key"] = self.extended_perpetual_stark_public_key
        
        exchange_order = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_URL,
            data=data,
            is_auth_required=True,
        )

        if not isinstance(exchange_order, dict):
            raise IOError(f"Error placing order: {exchange_order}")
        
        order_id_from_exchange = exchange_order.get("order_id")
        created_at = exchange_order.get("created_at", 0)
        
        if not order_id_from_exchange:
            raise IOError(f"Error placing order: {exchange_order}")
        
        timestamp = created_at / 1000 if created_at > 1e12 else created_at
        
        return (str(order_id_from_exchange), float(timestamp))

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancel an order on Extended
        """
        exchange_order_id = await tracked_order.get_exchange_order_id()
        
        cancel_result = await self._api_delete(
            path_url=f"{CONSTANTS.CANCEL_ORDER_URL}/{exchange_order_id}",
            is_auth_required=True,
        )
        
        if not isinstance(cancel_result, dict):
            return False
        
        return cancel_result.get("status") == "cancelled" or cancel_result.get("success") is True

    async def _update_balances(self):
        """
        Update account balances from Extended API
        """
        self.logger().info(f"💰 UPDATING BALANCES for {self.name}")
        self.logger().info(f"💰 Balance URL: {CONSTANTS.BALANCE_URL}")
        self.logger().info(f"💰 API Key being used: {self.extended_perpetual_api_key[:10]}...")
        
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        try:
            self.logger().info(f"💰 Making API call to get balance...")
            response = await self._api_get(path_url=CONSTANTS.BALANCE_URL, is_auth_required=True)
            self.logger().info(f"💰 Balance response received: {response}")
            
            if isinstance(response, dict):
                # Extended returns: {"status": "OK", "data": {"balance": "500.19", "availableForTrade": "500.19", ...}}
                if response.get("status") == "OK" and "data" in response:
                    balance_data = response.get("data", {})
                    
                    # Extended uses "USD" but it's actually USDC
                    asset = CONSTANTS.CURRENCY  # "USDC"
                    
                    # Get balance fields
                    total_balance = Decimal(str(balance_data.get("balance", 0)))
                    available_balance = Decimal(str(balance_data.get("availableForTrade", 0)))
                    equity = Decimal(str(balance_data.get("equity", 0)))
                    
                    self.logger().info(f"Extended balance - Total: {total_balance}, Available: {available_balance}, Equity: {equity}")
                    
                    # Use equity as total balance (includes unrealized PnL)
                    self._account_balances[asset] = equity if equity > 0 else total_balance
                    self._account_available_balances[asset] = available_balance
                    remote_asset_names.add(asset)
                else:
                    # Fallback to older format if exists
                    balances = response.get("balances", [])
                    for balance_entry in balances:
                        asset_name = balance_entry.get("asset") or CONSTANTS.CURRENCY
                        available = Decimal(str(balance_entry.get("available", 0)))
                        total = Decimal(str(balance_entry.get("total", 0)))
                        
                        self._account_available_balances[asset_name] = available
                        self._account_balances[asset_name] = total
                        remote_asset_names.add(asset_name)
            else:
                raise IOError(f"Error requesting balances: {response}")
        except IOError as e:
            # Extended returns 404 when balance is 0
            if "404" in str(e):
                self.logger().info("No balance found (404) - this is normal if you haven't deposited yet")
                # Set default currency to 0
                self._account_balances[CONSTANTS.CURRENCY] = Decimal("0")
                self._account_available_balances[CONSTANTS.CURRENCY] = Decimal("0")
                remote_asset_names.add(CONSTANTS.CURRENCY)
            else:
                raise

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        """
        Update positions from Extended API
        """
        try:
            response = await self._api_get(path_url=CONSTANTS.POSITIONS_URL, is_auth_required=True)
            
            if isinstance(response, dict):
                positions = response.get("positions", [])
                
                for position_data in positions:
                    market_id = position_data.get("market_id") or position_data.get("market")
                    if not market_id:
                        continue
                    
                    try:
                        trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=market_id)
                        
                        # Parse position data
                        position_size = Decimal(str(position_data.get("size", 0)))
                        if position_size == 0:
                            continue
                        
                        # Determine position side
                        position_side = PositionSide.LONG if position_size > 0 else PositionSide.SHORT
                        amount = abs(position_size)
                        
                        # Get position details
                        entry_price = Decimal(str(position_data.get("entry_price", 0)))
                        leverage = Decimal(str(position_data.get("leverage", 1)))
                        unrealized_pnl = Decimal(str(position_data.get("unrealized_pnl", 0)))
                        
                        position = Position(
                            trading_pair=trading_pair,
                            position_side=position_side,
                            unrealized_pnl=unrealized_pnl,
                            entry_price=entry_price,
                            amount=amount,
                            leverage=leverage,
                        )
                        
                        self._account_positions[trading_pair] = position
                    except Exception as e:
                        self.logger().error(f"Error processing position for {market_id}: {e}")
            else:
                self.logger().warning(f"Unexpected positions response format: {response}")
        except IOError as e:
            # Extended may return 404 if no positions
            if "404" in str(e):
                self.logger().info("No positions found (404)")
                # Clear all positions
                self._account_positions.clear()
            else:
                self.logger().error(f"Error updating positions: {e}")

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Format trading rules from Extended market info
        """
        trading_rules: List[TradingRule] = []
        
        # Extended returns: {"status": "OK", "data": [array of markets]}
        if isinstance(exchange_info_dict, dict) and "data" in exchange_info_dict:
            markets = exchange_info_dict.get("data", [])
        elif isinstance(exchange_info_dict, list):
            markets = exchange_info_dict
        else:
            markets = []
        
        for market in markets:
            try:
                if not isinstance(market, dict):
                    continue
                
                market_name = market.get("name")
                if not market_name:
                    continue
                
                status = market.get("status", "").upper()
                if status not in ["ACTIVE", "REDUCE_ONLY"]:
                    continue
                
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=market_name)
                
                # Get trading config
                config = market.get("tradingConfig", {})
                
                min_order_size = Decimal(str(config.get("minOrderSize", 0)))
                min_order_size_change = Decimal(str(config.get("minOrderSizeChange", 0.001)))
                min_price_change = Decimal(str(config.get("minPriceChange", 0.01)))
                max_position_value = Decimal(str(config.get("maxPositionValue", 999999999)))
                
                rule = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_order_size if min_order_size > 0 else min_order_size_change,
                    max_order_size=max_position_value,
                    min_price_increment=min_price_change if min_price_change > 0 else Decimal("0.01"),
                    min_base_amount_increment=min_order_size_change if min_order_size_change > 0 else Decimal("0.001"),
                    min_notional_size=Decimal("0"),
                )
                trading_rules.append(rule)
            except Exception as e:
                self.logger().exception(f"Error parsing trading rules for market: {market}")

        return trading_rules

    async def _update_trading_fees(self):
        """
        Update trading fees from Extended API
        """
        try:
            resp = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_INFO_URL,
                is_auth_required=True,
            )
            
            # Extended returns fee info in account details
            if isinstance(resp, dict):
                maker_fee = Decimal(str(resp.get("maker_fee", 0.0002)))
                taker_fee = Decimal(str(resp.get("taker_fee", 0.0005)))
                
                # Apply to all trading pairs
                for trading_pair in self._trading_pairs:
                    self._trading_fees[trading_pair] = {
                        "maker": maker_fee,
                        "taker": taker_fee,
                    }
        except Exception as e:
            self.logger().warning(f"Error updating trading fees: {e}")

    async def _user_stream_event_listener(self):
        """
        Process user stream events
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if not isinstance(event_message, dict):
                    continue
                
                event_type = event_message.get("type", "")
                data = event_message.get("data", {})
                
                # Handle order updates
                if event_type == "order_update" or "order" in data:
                    await self._process_order_update_event(data)
                
                # Handle trade/fill updates
                elif event_type == "trade_update" or "trade" in data:
                    await self._process_trade_update_event(data)
                
                # Handle position updates
                elif event_type == "position_update" or "position" in data:
                    await self._update_positions()
                
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _process_order_update_event(self, order_data: Dict[str, Any]):
        """Process order update from websocket"""
        client_order_id = order_data.get("client_order_id")
        exchange_order_id = order_data.get("order_id")
        status = order_data.get("status", "").lower()
        
        new_state = CONSTANTS.ORDER_STATE.get(status, OrderState.OPEN)
        
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if tracked_order:
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=new_state,
                client_order_id=client_order_id,
                exchange_order_id=exchange_order_id,
            )
            self._order_tracker.process_order_update(order_update=order_update)

    async def _process_trade_update_event(self, trade_data: Dict[str, Any]):
        """Process trade update from websocket"""
        client_order_id = trade_data.get("client_order_id")
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        
        if tracked_order:
            fill_amount = Decimal(str(trade_data.get("size", 0)))
            fill_price = Decimal(str(trade_data.get("price", 0)))
            fee_amount = Decimal(str(trade_data.get("fee", 0)))
            
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=PositionAction.OPEN,
                percent_token=CONSTANTS.CURRENCY,
                flat_fees=[TokenAmount(amount=fee_amount, token=CONSTANTS.CURRENCY)],
            )
            
            trade_update = TradeUpdate(
                trade_id=str(trade_data.get("trade_id", self.current_timestamp)),
                client_order_id=client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                fee=fee,
                fill_base_amount=fill_amount,
                fill_quote_amount=fill_amount * fill_price,
                fill_price=fill_price,
                fill_timestamp=self.current_timestamp,
            )
            self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Get all trade updates for a specific order
        Extended provides trade updates via websocket
        """
        return []

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Request order status from Extended API
        """
        exchange_order_id = await tracked_order.get_exchange_order_id()
        
        order_data = await self._api_get(
            path_url=f"{CONSTANTS.ORDER_URL}/{exchange_order_id}",
            is_auth_required=True
        )

        if not isinstance(order_data, dict):
            raise IOError(f"Error requesting order status: {order_data}")
        
        status = order_data.get("status", "").lower()
        new_state = CONSTANTS.ORDER_STATE.get(status, OrderState.OPEN)

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=new_state,
        )

        return order_update

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """
        Get last traded price for a trading pair
        Extended uses: GET /api/v1/info/markets/{market}/stats
        """
        market_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        
        # Build URL with market in path
        stats_url = f"/api/v1/info/markets/{market_id}/stats"
        
        resp_json = await self._api_request(
            path_url=stats_url,
            method=RESTMethod.GET
        )

        if isinstance(resp_json, dict):
            # Extended returns: {"status": "OK", "data": {"lastPrice": "..."}}
            if resp_json.get("status") == "OK" and "data" in resp_json:
                stats_data = resp_json.get("data", {})
                last_price = float(stats_data.get("lastPrice", 0))
                return last_price
            # Fallback for different format
            market_stats = resp_json.get("marketStats", {})
            if market_stats:
                return float(market_stats.get("lastPrice", 0))
        
        return 0.0

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        """
        Fetch last funding fee payment for a trading pair
        Returns: (timestamp, funding_rate, payment_amount)
        If no payment exists, return (0, Decimal("-1"), Decimal("-1"))
        """
        try:
            market_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            
            # Get funding payments history
            payments_url = f"/api/v1/user/funding-payments?market={market_id}&limit=1"
            
            response = await self._api_get(
                path_url=payments_url,
                is_auth_required=True,
            )
            
            self.logger().info(f"💸 Funding payment response for {trading_pair}: {response}")
            
            if isinstance(response, dict) and response.get("status") == "OK":
                data = response.get("data", {})
                payments = data.get("payments", [])
                
                if payments and len(payments) > 0:
                    last_payment = payments[0]
                    payment_amount = Decimal(str(last_payment.get("amount", 0)))
                    funding_rate = Decimal(str(last_payment.get("fundingRate", 0)))
                    timestamp = last_payment.get("timestamp", 0)
                    timestamp = float(timestamp / 1000 if timestamp > 1e12 else timestamp)
                    
                    return timestamp, funding_rate, payment_amount
            
            # No payments found - return default values
            return 0.0, Decimal("-1"), Decimal("-1")
        except Exception as e:
            # If endpoint doesn't exist or errors, return defaults
            self.logger().warning(f"⚠️ Could not fetch funding payment (non-critical): {e}")
            return 0.0, Decimal("-1"), Decimal("-1")

    async def _update_funding_payment(self, trading_pair: str, fire_event_on_new: bool = True):
        """
        Update funding payments for a trading pair
        :param trading_pair: The trading pair to update
        :param fire_event_on_new: Whether to fire an event when a new payment is detected
        """
        try:
            timestamp, funding_rate, payment = await self._fetch_last_fee_payment(trading_pair)
            if timestamp > 0:
                # Record the funding payment
                self.logger().info(f"💸 Funding payment for {trading_pair}: {payment} (rate: {funding_rate}) at {timestamp}")
                # You can add event firing logic here if needed
        except Exception as e:
            self.logger().warning(f"⚠️ Error updating funding payment for {trading_pair}: {e}")

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        """
        Set position mode for a trading pair.
        Extended only supports ONEWAY mode, so this always returns success.
        """
        if mode == PositionMode.ONEWAY:
            return True, ""
        else:
            return False, "Extended only supports ONEWAY position mode"

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """
        Set leverage for a trading pair
        Extended may not support per-market leverage setting via API
        """
        try:
            self.logger().info(f"⚡ Setting leverage {leverage}x for {trading_pair}")
            
            market_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            
            data = {
                "market": market_id,
                "leverage": str(leverage)
            }
            
            # Use _api_post to ensure proper rate limiting
            response = await self._api_post(
                path_url=CONSTANTS.LEVERAGE_URL,
                data=data,
                is_auth_required=True,
            )
            
            self.logger().info(f"⚡ Leverage response: {response}")
            
            if isinstance(response, dict):
                if response.get("status") == "OK" or response.get("success"):
                    self.logger().info(f"✅ Leverage set to {leverage}x for {trading_pair}")
                    return True, ""
                else:
                    msg = response.get("message", str(response))
                    self.logger().warning(f"⚠️ Leverage setting returned: {msg}")
                    # Don't fail - Extended might not support this endpoint
                    return True, ""
            else:
                return True, ""  # Don't block if leverage setting not supported
        except Exception as e:
            # Don't fail the connector if leverage setting fails
            # Extended might not support per-market leverage via API
            self.logger().warning(f"⚠️ Could not set leverage (non-critical): {e}")
            return True, ""  # Return success anyway to not block connector

