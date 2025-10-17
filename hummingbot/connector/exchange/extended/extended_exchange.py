import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.extended import (
    extended_constants as CONSTANTS,
    extended_utils as utils,
    extended_web_utils as web_utils,
)
from hummingbot.connector.exchange.extended.extended_api_order_book_data_source import ExtendedAPIOrderBookDataSource
from hummingbot.connector.exchange.extended.extended_api_user_stream_data_source import (
    ExtendedAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.extended.extended_auth import ExtendedAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class ExtendedExchange(ExchangePyBase):
    """
    ExtendedExchange connects with Extended exchange and provides order book pricing, user account tracking and
    trading functionality for perpetual contracts.
    """

    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(
        self,
        extended_api_key: str,
        extended_stark_public_key: str,
        extended_stark_private_key: str,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        """
        :param extended_api_key: The API key to connect to private Extended APIs.
        :param extended_stark_public_key: The Stark public key for order signing.
        :param extended_stark_private_key: The Stark private key for order signing.
        :param balance_asset_limit: Optional balance limits for assets.
        :param rate_limits_share_pct: Percentage of rate limits to use.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        self.extended_api_key = extended_api_key
        self.extended_stark_public_key = extended_stark_public_key
        self.extended_stark_private_key = extended_stark_private_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def domain(self):
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def authenticator(self):
        return ExtendedAuth(
            self.extended_api_key,
            self.extended_stark_public_key,
            self.extended_stark_private_key
        )

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.MARKETS_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.MARKETS_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.MARKETS_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> Dict[str, Any]:
        """
        This method executes a request to the exchange to get the current price for all trades.

        :return: the response from the market statistics endpoint
        """
        pairs_prices = await self._api_get(path_url=CONSTANTS.MARKET_STATS_PATH_URL)
        return pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # Extended API documentation does not clarify the error message for timestamp related problems
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        # Check if the error indicates order not found
        error_message = str(status_update_exception).lower()
        return "not found" in error_message or "does not exist" in error_message

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # Check if the error indicates order not found during cancellation
        error_message = str(cancelation_exception).lower()
        return "not found" in error_message or "does not exist" in error_message

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return ExtendedAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return ExtendedAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
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
    ) -> AddedToCostTradeFee:

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        if trading_pair in self._trading_fees:
            fees_data = self._trading_fees[trading_pair]
            fee_value = Decimal(fees_data["maker"]) if is_maker else Decimal(fees_data["taker"])
            fee = AddedToCostTradeFee(percent=fee_value)
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
        
        # Extended returns markets in format: { "markets": [ { "market_id": "BTC-USDC", ... }, ... ] }
        markets = []
        if isinstance(exchange_info, dict):
            markets = exchange_info.get("markets", [])
        elif isinstance(exchange_info, list):
            markets = exchange_info
        
        for market_data in markets:
            if not isinstance(market_data, dict):
                continue
                
            if not utils.is_pair_information_valid(market_data):
                continue
            
            # Extended uses market_id as the symbol (e.g., "BTC-USDC")
            market_id = market_data.get("market_id") or market_data.get("symbol")
            if not market_id:
                continue
            
            # Parse the market_id to get base and quote
            # Extended format: "BTC-USDC" or "ETH-USDC"
            if "-" in market_id:
                parts = market_id.split("-")
                if len(parts) == 2:
                    base = parts[0]
                    quote = parts[1]
                    hb_pair = combine_to_hb_trading_pair(base, quote)
                    mapping[market_id] = hb_pair
            else:
                # Fallback parsing
                base = market_data.get("base_asset") or market_data.get("base")
                quote = market_data.get("quote_asset") or market_data.get("quote")
                if base and quote:
                    hb_pair = combine_to_hb_trading_pair(base, quote)
                    mapping[market_id] = hb_pair
        
        self._set_trading_pair_symbol_map(mapping)

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        """
        Place an order on Extended exchange
        """
        side = trade_type.name.lower()  # "buy" or "sell"
        market_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        
        data = {
            "market_id": market_id,
            "side": side,
            "size": str(amount),
            "client_order_id": order_id,
        }
        
        if order_type.is_limit_type():
            data["type"] = "limit"
            data["price"] = str(price)
            data["time_in_force"] = "GTC"
        else:
            data["type"] = "market"
        
        if order_type is OrderType.LIMIT_MAKER:
            data["post_only"] = True
        
        # Add Stark signature for order placement
        stark_signature = self._auth.generate_stark_signature(data)
        data["stark_signature"] = stark_signature
        data["stark_public_key"] = self.extended_stark_public_key
        
        exchange_order = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
        )

        if not isinstance(exchange_order, dict):
            raise IOError(f"Error placing order: {exchange_order}")
        
        # Extended returns: { "order_id": "...", "created_at": ... }
        order_id_from_exchange = exchange_order.get("order_id")
        created_at = exchange_order.get("created_at", 0)
        
        if not order_id_from_exchange:
            raise IOError(f"Error placing order: {exchange_order}")
        
        # Convert timestamp to seconds
        timestamp = created_at / 1000 if created_at > 1e12 else created_at
        
        return (str(order_id_from_exchange), float(timestamp))

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancel an order on Extended exchange
        """
        exchange_order_id = await tracked_order.get_exchange_order_id()
        
        # Extended uses DELETE method to cancel orders
        cancel_result = await self._api_delete(
            path_url=f"{CONSTANTS.ORDER_PATH_URL}/{exchange_order_id}",
            is_auth_required=True,
        )
        
        if not isinstance(cancel_result, dict):
            return False
        
        # Check if cancellation was successful
        return cancel_result.get("status") == "cancelled" or cancel_result.get("success") is True

    async def _user_stream_event_listener(self):
        """
        Process user stream events from Extended websocket
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if not isinstance(event_message, dict):
                    continue
                
                event_type = event_message.get("type", "")
                data = event_message.get("data", {})
                
                # Handle order updates
                if event_type == "order_update":
                    await self._process_order_update(data)
                
                # Handle trade/fill updates
                elif event_type == "trade_update":
                    await self._process_trade_update(data)
                
                # Handle balance updates
                elif event_type == "balance_update":
                    await self._process_balance_update(data)
                
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _process_order_update(self, order_data: Dict[str, Any]):
        """Process order update from websocket"""
        client_order_id = order_data.get("client_order_id")
        exchange_order_id = order_data.get("order_id")
        status = order_data.get("status", "").lower()
        
        # Map Extended status to Hummingbot OrderState
        new_state = CONSTANTS.ORDER_STATE.get(status, OrderState.OPEN)
        
        # Find the order
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

    async def _process_trade_update(self, trade_data: Dict[str, Any]):
        """Process trade update from websocket"""
        client_order_id = trade_data.get("client_order_id")
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        
        if tracked_order:
            fill_amount = Decimal(str(trade_data.get("size", 0)))
            fill_price = Decimal(str(trade_data.get("price", 0)))
            fee_amount = Decimal(str(trade_data.get("fee", 0)))
            fee_asset = trade_data.get("fee_currency", tracked_order.quote_asset)
            
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                trade_type=tracked_order.trade_type,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)],
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

    async def _process_balance_update(self, balance_data: Dict[str, Any]):
        """Process balance update from websocket"""
        asset = balance_data.get("asset")
        available = Decimal(str(balance_data.get("available", 0)))
        total = Decimal(str(balance_data.get("total", 0)))
        
        if asset:
            self._account_balances[asset] = total
            self._account_available_balances[asset] = available

    async def _update_balances(self):
        """Update account balances from Extended API"""
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        try:
            response = await self._api_get(path_url=CONSTANTS.BALANCE_PATH_URL, is_auth_required=True)
            
            if isinstance(response, dict):
                balances = response.get("balances", [])
                for balance_entry in balances:
                    asset_name = balance_entry.get("asset") or balance_entry.get("currency")
                    available = Decimal(str(balance_entry.get("available", 0)))
                    total = Decimal(str(balance_entry.get("total", 0)))
                    
                    self._account_available_balances[asset_name] = available
                    self._account_balances[asset_name] = total
                    remote_asset_names.add(asset_name)
            else:
                raise IOError(f"Error requesting balances from Extended: {response}")
        except IOError as e:
            # Extended returns 404 when balance is 0 (no deposits)
            # This is expected behavior, not an error
            if "404" in str(e):
                self.logger().info("No balance found (404) - this is normal if you haven't deposited yet")
                # Clear all balances since Extended says balance is 0
                local_asset_names = set(self._account_balances.keys())
            else:
                raise

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _format_trading_rules(self, raw_trading_pair_info: Dict[str, Any]) -> List[TradingRule]:
        trading_rules: List[TradingRule] = []

        markets = []
        if isinstance(raw_trading_pair_info, dict):
            markets = raw_trading_pair_info.get("markets", [])
        elif isinstance(raw_trading_pair_info, list):
            markets = raw_trading_pair_info

        for market in markets:
            try:
                if not isinstance(market, dict):
                    continue
                if not utils.is_pair_information_valid(market):
                    continue

                market_id = market.get("market_id") or market.get("symbol")
                if not market_id:
                    continue

                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=market_id)

                # Extract trading rules from market data
                min_order_size = Decimal(str(market.get("min_order_size", 0)))
                max_order_size = Decimal(str(market.get("max_order_size", 999999999)))
                tick_size = Decimal(str(market.get("tick_size", 0.01)))
                step_size = Decimal(str(market.get("step_size", 0.001)))
                min_notional = Decimal(str(market.get("min_notional", 0)))

                rule = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_order_size if min_order_size > 0 else step_size,
                    max_order_size=max_order_size if max_order_size > 0 else Decimal("999999999"),
                    min_price_increment=tick_size if tick_size > 0 else Decimal("0.01"),
                    min_base_amount_increment=step_size if step_size > 0 else Decimal("0.001"),
                    min_notional_size=min_notional if min_notional > 0 else Decimal("0"),
                )
                trading_rules.append(rule)
            except Exception:
                self.logger().exception(f"Error parsing trading rules for market: {market}")

        return trading_rules

    async def _update_trading_fees(self):
        """Update trading fees from Extended API"""
        resp = await self._api_get(
            path_url=CONSTANTS.FEES_PATH_URL,
            is_auth_required=True,
        )
        
        fees_data = resp.get("fees", [])
        for fee_entry in fees_data:
            try:
                market_id = fee_entry.get("market_id") or fee_entry.get("symbol")
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=market_id)
                
                maker_fee = Decimal(str(fee_entry.get("maker_fee", 0.0002)))
                taker_fee = Decimal(str(fee_entry.get("taker_fee", 0.0005)))
                
                self._trading_fees[trading_pair] = {
                    "maker": maker_fee,
                    "taker": taker_fee,
                }
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # Extended provides trade updates via websocket
        # This method can be left empty or return empty list
        return []

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """Request order status from Extended API"""
        exchange_order_id = await tracked_order.get_exchange_order_id()
        
        order_data = await self._api_get(
            path_url=f"{CONSTANTS.ORDER_PATH_URL}/{exchange_order_id}",
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
        """Get last traded price for a trading pair"""
        market_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        
        params = {"market_id": market_id}
        resp_json = await self._api_request(
            path_url=CONSTANTS.MARKET_STATS_PATH_URL, 
            method=RESTMethod.GET, 
            params=params
        )

        # Extended returns market statistics with last price
        if isinstance(resp_json, dict):
            markets = resp_json.get("markets", [])
            for market in markets:
                if market.get("market_id") == market_id:
                    return float(market.get("last_price", 0))
        
        return 0.0

