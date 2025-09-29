import asyncio
import math
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import hummingbot.connector.exchange.coinmate.coinmate_constants as CONSTANTS
import hummingbot.connector.exchange.coinmate.coinmate_utils as utils
import hummingbot.connector.exchange.coinmate.coinmate_web_utils as web_utils
from hummingbot.connector.exchange.coinmate.coinmate_api_order_book_data_source import (
    CoinmateAPIOrderBookDataSource
)
from hummingbot.connector.exchange.coinmate.coinmate_api_user_stream_data_source import (
    CoinmateAPIUserStreamDataSource
)
from hummingbot.connector.exchange.coinmate.coinmate_auth import CoinmateAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import (
    InFlightOrder,
    OrderState,
    OrderUpdate,
    TradeUpdate
)
from hummingbot.core.data_type.order_book_tracker_data_source import (
    OrderBookTrackerDataSource
)
from hummingbot.core.data_type.trade_fee import TradeFeeBase, TokenAmount
from hummingbot.core.data_type.user_stream_tracker_data_source import (
    UserStreamTrackerDataSource
)
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import (
    WebAssistantsFactory
)


class CoinmateExchange(ExchangePyBase):
    
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    web_utils = web_utils

    def __init__(
        self,
        coinmate_api_key: str,
        coinmate_secret_key: str,
        coinmate_client_id: str,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.coinmate_api_key = coinmate_api_key
        self.coinmate_secret_key = coinmate_secret_key
        self.coinmate_client_id = coinmate_client_id
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_coinmate_timestamp = 1.0
        self._trading_fees = {}
        self._auth = None
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> CoinmateAuth:
        if self._auth is None:
            self._auth = CoinmateAuth(
                api_key=self.coinmate_api_key,
                secret_key=self.coinmate_secret_key,
                client_id=self.coinmate_client_id
            )
        return self._auth

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.TRADING_PAIRS_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.TRADING_PAIRS_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.TICKER_PATH_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]
        
    async def _api_request_with_retry(
        self,
        method: RESTMethod,
        path_url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_auth_required: bool = False,
        max_retries: Optional[int] = None,
        throttler_limit_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if max_retries is None:
            max_retries = CONSTANTS.MAX_RETRIES
            
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(path_url, domain=self._domain)
        
        for attempt in range(max_retries + 1):
            try:
                response = await rest_assistant.execute_request(
                    url=url,
                    method=method,
                    params=params,
                    data=data or {},
                    is_auth_required=is_auth_required,
                    throttler_limit_id=throttler_limit_id or path_url,
                    timeout=CONSTANTS.REQUEST_TIMEOUT
                )
                
                return response
                
            except asyncio.CancelledError:
                raise
                
            except Exception as e:
                if attempt >= max_retries:
                    self.logger().error(f"Request to {path_url} failed after {max_retries} retries: {e}")
                    raise e
                backoff_time = utils.calculate_backoff_time(attempt)
                self.logger().warning(f"Request to {path_url} failed (attempt {attempt + 1}), retrying in {backoff_time}s: {e}")
                await asyncio.sleep(backoff_time)

    def _is_request_exception_related_to_time_synchronizer(
        self, request_exception: Exception
    ) -> bool:
        error_description = str(request_exception).lower()
        return (
            "time" in error_description or 
            "timestamp" in error_description or 
            "nonce" in error_description
        )

    def _is_order_not_found_during_status_update_error(
        self, status_update_exception: Exception
    ) -> bool:
        error_description = str(status_update_exception)
        return (
            CONSTANTS.ORDER_NOT_EXIST_ERROR_MESSAGE in error_description or
            "order does not exist" in error_description.lower()
        )

    def _is_order_not_found_during_cancelation_error(
        self, cancelation_exception: Exception
    ) -> bool:
        error_description = str(cancelation_exception)
        return (
            CONSTANTS.ORDER_NOT_EXIST_ERROR_MESSAGE in error_description or
            "order does not exist" in error_description.lower()
        )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            domain=self._domain,
            auth=self.authenticator
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CoinmateAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return CoinmateAPIUserStreamDataSource(
            auth=self.authenticator,
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
        price: Decimal = None,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        
        return build_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            order_side=order_side,
            order_type=order_type,
            amount=amount,
            price=price,
            base_currency=base_currency,
            quote_currency=quote_currency,
        )

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
        coinmate_symbol = web_utils.convert_to_exchange_trading_pair(trading_pair)
        
        if order_type == OrderType.LIMIT:
            if trade_type == TradeType.BUY:
                path_url = CONSTANTS.BUY_LIMIT_PATH_URL
            else:
                path_url = CONSTANTS.SELL_LIMIT_PATH_URL
        elif order_type == OrderType.MARKET:
            # Market orders in Coinmate are instant orders
            if trade_type == TradeType.BUY:
                path_url = CONSTANTS.BUY_INSTANT_PATH_URL
            else:
                path_url = CONSTANTS.SELL_INSTANT_PATH_URL
        else:
            if trade_type == TradeType.BUY:
                path_url = CONSTANTS.BUY_LIMIT_PATH_URL
            else:
                path_url = CONSTANTS.SELL_LIMIT_PATH_URL

        trading_rules = self.trading_rules.get(trading_pair)
        price_decimals = 2
        if trading_rules and hasattr(trading_rules, 'min_price_increment'):
            price_decimals = int(-math.log10(float(trading_rules.min_price_increment)))
        
        formatted_price = f"{float(price):.{price_decimals}f}"
        
        if order_type == OrderType.LIMIT:
            data = {
                "currencyPair": coinmate_symbol,
                "amount": str(amount),
                "price": formatted_price,
            }
        elif order_type == OrderType.MARKET:
            if trade_type == TradeType.BUY:
                total_quote = float(amount)
                data = {
                    "currencyPair": coinmate_symbol,
                    "total": str(total_quote),
                }
            else:
                base_amount = float(amount)
                data = {
                    "currencyPair": coinmate_symbol,
                    "amount": str(base_amount),
                }
        else:
            data = {
                "currencyPair": coinmate_symbol,
                "amount": str(amount),
                "price": formatted_price,
            }

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(path_url, domain=self._domain)
        
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data=data,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
            )

        if response.get("error"):
            raise IOError(f"Error placing order: {response['errorMessage']}")

        exchange_order_id = str(response.get("data", ""))
        
        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        data = {"orderId": tracked_order.exchange_order_id}
        
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL, domain=self._domain)
        
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data=data,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
        )

        if response.get("error"):
            error_msg = response.get('errorMessage', 'Unknown error')
            self.logger().error(f"Failed to cancel order {order_id}: {error_msg}")
            return False

        return True

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        rules = []
        
        if not utils.is_exchange_information_valid(exchange_info_dict):
            return rules

        data = exchange_info_dict.get("data", [])
        
        for pair_info in data:
            try:
                pair_name = pair_info.get("name", "")
                if not pair_name:
                    continue
                    
                trading_pair = web_utils.convert_from_exchange_trading_pair(pair_name)
                
                min_order_size = Decimal(str(pair_info.get("minAmount", "0.001")))
                
                price_decimals = int(pair_info.get("priceDecimals", 2))
                lot_decimals = int(pair_info.get("lotDecimals", 8))
                
                min_price_increment = Decimal("10") ** -price_decimals
                min_base_amount_increment = Decimal("10") ** -lot_decimals
                
                rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=min_price_increment,
                        min_base_amount_increment=min_base_amount_increment,
                    )
                )
                
            except Exception as e:
                self.logger().error(
                    f"Error parsing trading rules for {pair_name}: {e}",
                    exc_info=True
                )
                continue
                
        return rules

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        from bidict import bidict
        
        mapping = bidict()
        
        if not utils.is_exchange_information_valid(exchange_info):
            self.logger().warning("Invalid exchange information provided for trading pair symbols initialization")
            return
        
        data = exchange_info.get("data", [])
        
        for pair_info in data:
            try:
                exchange_symbol = pair_info.get("name", "")
                if not exchange_symbol:
                    continue
                
                trading_pair = web_utils.convert_from_exchange_trading_pair(exchange_symbol)
                
                if exchange_symbol in mapping:
                    self.logger().error(
                        f"Exchange symbol {exchange_symbol} (trading pair {trading_pair}) already present in the map "
                        f"(with trading pair {mapping[exchange_symbol]})."
                    )
                    continue
                elif trading_pair in mapping.inverse:
                    self.logger().error(
                        f"Trading pair {trading_pair} (exchange symbol {exchange_symbol}) already present in the map "
                        f"(with symbol {mapping.inverse[trading_pair]})."
                    )
                    continue
                
                mapping[exchange_symbol] = trading_pair
                
            except Exception as e:
                self.logger().error(
                    f"Error processing trading pair info {pair_info}: {e}",
                    exc_info=True
                )
                continue
        
        self._set_trading_pair_symbol_map(mapping)
        self.logger().info(f"Initialized {len(mapping)} trading pair symbol mappings")

    async def _update_trading_fees(self):
        try:
            rest_assistant = await self._web_assistants_factory.get_rest_assistant()
            
            for trading_pair in self._trading_pairs:
                coinmate_symbol = web_utils.convert_to_exchange_trading_pair(trading_pair)
                
                url = web_utils.private_rest_url(CONSTANTS.TRADER_FEES_PATH_URL, domain=self._domain)
                data = {"currencyPair": coinmate_symbol}
                
                data_string = urlencode(data)
                
                response = await rest_assistant.execute_request(
                    url=url,
                    method=RESTMethod.POST,
                    data=data_string,
                    is_auth_required=True,
                    throttler_limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if not response.get("error") and response.get("data"):
                    fee_data = response["data"]
                    maker_fee = Decimal(str(fee_data.get("maker", 0.5))) / 100
                    taker_fee = Decimal(str(fee_data.get("taker", 0.5))) / 100 
                    self._trading_fees[trading_pair] = {
                        "maker_percent": maker_fee,
                        "taker_percent": taker_fee
                    }
                    
        except Exception as e:
            self.logger().error(f"Error updating trading fees: {e}", exc_info=True)
            for trading_pair in self._trading_pairs:
                self._trading_fees[trading_pair] = {
                    "maker_percent": Decimal("0.005"),
                    "taker_percent": Decimal("0.005")
                }

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("event")
                
                if event_type == "data":
                    payload = event_message.get("payload", {})
                    channel = payload.get("channel", "")
                    
                    if "private-open_orders" in channel:
                        await self._process_order_event(payload)
                    elif "private-user_balances" in channel:
                        await self._process_balance_event(payload)
                    elif "private-user-trades" in channel:
                        await self._process_trade_event(payload)
                        
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop", exc_info=True
                )
                await self._sleep(5.0)

    async def _process_order_event(self, payload):
        try:
            orders = payload.get("data", [])
            if not isinstance(orders, list):
                orders = [orders]
                
            for order_data in orders:
                order_id = str(order_data.get("id", ""))
                change_event = order_data.get("orderChangePushEvent", "")
                
                tracked_order = None
                for order in self._order_tracker.all_orders.values():
                    if order.exchange_order_id == order_id:
                        tracked_order = order
                        break
                        
                if tracked_order is None:
                    continue
                    
                if change_event == "REMOVAL":
                    new_state = OrderState.CANCELED
                    if order_data.get("status") == "FILLED":
                        new_state = OrderState.FILLED
                elif change_event == "UPDATE":
                    new_state = OrderState.PARTIALLY_FILLED
                elif change_event in ["CREATION", "SNAPSHOT"]:
                    new_state = OrderState.OPEN
                else:
                    continue
                    
                order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=new_state,
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=order_id,
                )
                self._order_tracker.process_order_update(order_update)
                
        except Exception as e:
            self.logger().error(f"Error processing order event: {e}", exc_info=True)

    async def _process_balance_event(self, payload):
        try:
            balances = payload.get("data", {})
            self.logger().info(f"Received balance event: {balances}")
            
            for currency, balance_data in balances.items():
                if isinstance(balance_data, dict):
                    total_balance = Decimal(str(balance_data.get("balance", "0")))
                    available_balance = Decimal(str(balance_data.get("available", "0")))
                    reserved_balance = Decimal(str(balance_data.get("reserved", "0")))
                    
                    self._account_balances[currency] = total_balance
                    self._account_available_balances[currency] = available_balance
                    
                    self.logger().info(
                        f"Updated {currency} balance from websocket: "
                        f"total={total_balance}, available={available_balance}, reserved={reserved_balance}"
                    )
                    
        except Exception as e:
            self.logger().error(f"Error processing balance event: {e}", exc_info=True)

    async def _process_trade_event(self, payload):
        try:
            trades = payload.get("data", [])
            if not isinstance(trades, list):
                trades = [trades]
                
            for trade_data in trades:
                order_id = str(trade_data.get("orderId", ""))
                
                tracked_order = None
                for order in self._order_tracker.all_fillable_orders.values():
                    if order.exchange_order_id == order_id:
                        tracked_order = order
                        break
                        
                if tracked_order is None:
                    continue
                    
                fill_amount = Decimal(str(trade_data.get("amount", "0")))
                fill_price = Decimal(str(trade_data.get("price", "0")))
                fill_timestamp = float(trade_data.get("date", self.current_timestamp * 1000)) / 1000
                fee_amount = Decimal(str(trade_data.get("fee", "0")))
                
                base, quote = tracked_order.trading_pair.split("-")
                fee_currency = quote if tracked_order.trade_type == TradeType.BUY else base
                
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=tracked_order.trade_type,
                    percent_token=fee_currency,
                    flat_fees=[TokenAmount(amount=fee_amount, token=fee_currency)]
                )
                
                trade_update = TradeUpdate(
                    trade_id=str(trade_data.get("transactionId", "")),
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=order_id,
                    trading_pair=tracked_order.trading_pair,
                    fee=fee,
                    fill_base_amount=fill_amount,
                    fill_quote_amount=fill_amount * fill_price,
                    fill_price=fill_price,
                    fill_timestamp=fill_timestamp,
                )
                self._order_tracker.process_trade_update(trade_update)
                
        except Exception as e:
            self.logger().error(f"Error processing trade event: {e}", exc_info=True)

    async def _update_balances(self):
        try:
            response = await self._api_request_with_retry(
                method=RESTMethod.POST,
                path_url=CONSTANTS.ACCOUNTS_PATH_URL,
                data={},
                is_auth_required=True,
                throttler_limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
            )
            
            if response.get("error"):
                error_message = response.get("errorMessage", "Unknown error")
                self.logger().error(f"Error fetching balances: {error_message}")
                return

            balances_data = response.get("data", {})
            self.logger().info(f"Received balance data: {balances_data}")
            
            self._account_balances.clear()
            self._account_available_balances.clear()
            
            for currency, balance_info in balances_data.items():
                if isinstance(balance_info, dict):
                    total_balance = Decimal(str(balance_info.get("balance", "0")))
                    available_balance = Decimal(str(balance_info.get("available", "0")))
                    reserved_balance = Decimal(str(balance_info.get("reserved", "0")))
                    
                    if total_balance > 0:
                        self._account_balances[currency] = total_balance
                        self._account_available_balances[currency] = available_balance
                        
                        self.logger().info(
                            f"Updated {currency} balance: "
                            f"total={total_balance}, available={available_balance}, reserved={reserved_balance}"
                        )
                    else:
                        self._account_balances[currency] = total_balance
                        self._account_available_balances[currency] = available_balance
                else:
                    balance = Decimal(str(balance_info))
                    if balance > 0:
                        self._account_balances[currency] = balance
                        self._account_available_balances[currency] = balance
                        self.logger().info(f"Updated {currency} balance (simple format): {balance}")
                        
            self.logger().info(f"Balance update complete. Total currencies: {len(self._account_balances)}")
                        
        except Exception as e:
            self.logger().error(f"Exception during balance update: {e}", exc_info=True)

    async def _update_order_status(self):
        """
        Update order statuses from Coinmate with retry logic
        """
        try:
            response = await self._api_request_with_retry(
                method=RESTMethod.POST,
                path_url=CONSTANTS.OPEN_ORDERS_PATH_URL,
                data={},  # Empty dict - auth parameters will be added by CoinmateAuth
                is_auth_required=True,
                throttler_limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
            )
            
            if response.get("error"):
                self.logger().error(f"Error fetching open orders: {response.get('errorMessage', 'Unknown error')}")
                return
        except Exception as e:
            self.logger().error(f"Failed to fetch open orders after retries: {e}")
            return

        open_orders = response.get("data", [])
        
        for order_info in open_orders:
            try:
                exchange_order_id = str(order_info.get("id"))
                client_order_id = None
                
                tracked_order = None
                for order in self._order_tracker.all_orders.values():
                    if order.exchange_order_id == exchange_order_id:
                        tracked_order = order
                        client_order_id = order.client_order_id
                        break
                
                if tracked_order is None:
                    continue
                    
                order_status = order_info.get("status", "").lower()
                new_state = CONSTANTS.ORDER_STATE.get(order_status, OrderState.OPEN)
                
                order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=new_state,
                    client_order_id=client_order_id,
                    exchange_order_id=exchange_order_id,
                )
                
                self._order_tracker.process_order_update(order_update)
                
            except Exception as e:
                self.logger().error(f"Error processing order update: {e}", exc_info=True)

    async def _update_order_fills_from_trades(self):
        """
        Update order fills from trade history using Coinmate's /tradeHistory endpoint
        """
        if len(self._order_tracker.all_orders) == 0:
            return

        order_by_exchange_id_map: Dict[str, InFlightOrder] = {}
        for tracked_order in self._order_tracker.all_orders.values():
            if tracked_order.exchange_order_id is not None:
                order_by_exchange_id_map[tracked_order.exchange_order_id] = tracked_order

        if len(order_by_exchange_id_map) == 0:
            return

        try:
            rest_assistant = await self._web_assistants_factory.get_rest_assistant()
            url = web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL, domain=self._domain)
            
            data = {
                "limit": 100,
                "sort": "DESC",  
                "timestampFrom": int((self.current_timestamp - 24 * 60 * 60) * 1000)
            }
            
            data_string = urlencode(data)
            
            response = await rest_assistant.execute_request(
                url=url,
                method=RESTMethod.POST,
                data=data_string,
                is_auth_required=True,
                throttler_limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            if response.get("error"):
                self.logger().error(f"Error fetching trade history: "
                                  f"{response.get('errorMessage', 'Unknown error')}")
                return

            trades = response.get("data", [])
            
            for trade in trades:
                try:
                    exchange_order_id = str(trade.get("orderId", ""))
                    if exchange_order_id in order_by_exchange_id_map:
                        # This is a fill for a tracked order
                        tracked_order = order_by_exchange_id_map[exchange_order_id]
                        
                        # Parse trade details
                        fill_amount = Decimal(str(trade.get("amount", "0")))
                        fill_price = Decimal(str(trade.get("price", "0")))
                        fill_timestamp = float(trade.get("createdTimestamp", 
                                               self.current_timestamp * 1000)) / 1000
                        
                        fill_quote_amount = fill_amount * fill_price
                        
                        fee_amount = Decimal(str(trade.get("fee", "0")))
                        
                        trading_pair = tracked_order.trading_pair
                        base, quote = trading_pair.split("-")
                        fee_currency = quote if tracked_order.trade_type == TradeType.BUY else base
                        
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=fee_currency,
                            flat_fees=[TokenAmount(amount=fee_amount, token=fee_currency)]
                        )
                        
                        trade_update = TradeUpdate(
                            trade_id=str(trade.get("transactionId", "")),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fee=fee,
                            fill_base_amount=fill_amount,
                            fill_quote_amount=fill_quote_amount,
                            fill_price=fill_price,
                            fill_timestamp=fill_timestamp,
                        )
                        
                        self._order_tracker.process_trade_update(trade_update)
                        
                except Exception as e:
                    self.logger().error(f"Error processing trade update: {e}", exc_info=True)
                    continue
                    
        except Exception as e:
            self.logger().error(f"Error fetching trade history for order fills: {e}", exc_info=True)


    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        try:
            rest_assistant = await self._web_assistants_factory.get_rest_assistant()
            url = web_utils.private_rest_url(CONSTANTS.ORDER_BY_ID_PATH_URL, domain=self._domain)
            
            data = {"orderId": tracked_order.exchange_order_id}
            
            data_string = urlencode(data)
            
            response = await rest_assistant.execute_request(
                url=url,
                method=RESTMethod.POST,
                data=data_string,
                is_auth_required=True,
                throttler_limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.get("error"):
                raise IOError(f"Error fetching order status: {response.get('errorMessage', 'Unknown error')}")
            
            order_data = response.get("data", {})
            order_status = order_data.get("status", "").upper()
            new_state = CONSTANTS.ORDER_STATE.get(order_status, OrderState.OPEN)
            
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=new_state,
            )
            
            return order_update
            
        except Exception as e:
            self.logger().error(f"Error requesting order status for {tracked_order.client_order_id}: {e}", exc_info=True)
            raise

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        
        if order.exchange_order_id is not None:
            try:
                rest_assistant = await self._web_assistants_factory.get_rest_assistant()
                url = web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL, domain=self._domain)
                
                data = {
                    "orderId": order.exchange_order_id,
                    "limit": 1000
                }
                
                data_string = urlencode(data)
                
                response = await rest_assistant.execute_request(
                    url=url,
                    method=RESTMethod.POST,
                    data=data_string,
                    is_auth_required=True,
                    throttler_limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if not response.get("error") and response.get("data"):
                    trades = response.get("data", [])
                    
                    for trade in trades:
                        if str(trade.get("orderId", "")) == order.exchange_order_id:
                            fill_amount = Decimal(str(trade.get("amount", "0")))
                            fill_price = Decimal(str(trade.get("price", "0")))
                            fill_timestamp = float(trade.get("createdTimestamp", 
                                                   self.current_timestamp * 1000)) / 1000
                            
                            fill_quote_amount = fill_amount * fill_price
                            fee_amount = Decimal(str(trade.get("fee", "0")))
                            
                            # Determine fee currency
                            base, quote = order.trading_pair.split("-")
                            fee_currency = quote if order.trade_type == TradeType.BUY else base
                            
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=order.trade_type,
                                percent_token=fee_currency,
                                flat_fees=[TokenAmount(amount=fee_amount, token=fee_currency)]
                            )
                            
                            trade_update = TradeUpdate(
                                trade_id=str(trade.get("transactionId", "")),
                                client_order_id=order.client_order_id,
                                exchange_order_id=order.exchange_order_id,
                                trading_pair=order.trading_pair,
                                fee=fee,
                                fill_base_amount=fill_amount,
                                fill_quote_amount=fill_quote_amount,
                                fill_price=fill_price,
                                fill_timestamp=fill_timestamp,
                            )
                            trade_updates.append(trade_update)
                            
            except Exception as e:
                self.logger().error(f"Error getting trade updates for order {order.client_order_id}: {e}", exc_info=True)
        
        return trade_updates

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self._api_get(
            path_url=self.trading_rules_request_path,
            limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID
        )
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_get(
            path_url=self.trading_pairs_request_path,
            limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID
        )
        return exchange_info

    async def _make_network_check_request(self):
        await self._api_get(
            path_url=self.check_network_request_path,
            limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID
        )
