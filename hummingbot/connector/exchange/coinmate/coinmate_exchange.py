import asyncio
import math
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

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
        return CONSTANTS.SERVER_TIME_PATH_URL

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
                total_quote = float(amount * price)
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

        response = await self._api_post(
            path_url=path_url,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
        )

        if response.get("error"):
            raise IOError(f"Error placing order: {response['errorMessage']}")

        exchange_order_id = str(response.get("data", ""))

        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        data = {"orderId": tracked_order.exchange_order_id}

        response = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
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
                
                # Validate that we have both currencies
                first_currency = pair_info.get("firstCurrency", "")
                second_currency = pair_info.get("secondCurrency", "")
                if not first_currency or not second_currency:
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
                
                # Validate that we have both currencies
                first_currency = pair_info.get("firstCurrency", "")
                second_currency = pair_info.get("secondCurrency", "")
                if not first_currency or not second_currency:
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
            for trading_pair in self._trading_pairs:
                coinmate_symbol = web_utils.convert_to_exchange_trading_pair(trading_pair)
                data = {"currencyPair": coinmate_symbol}

                response = await self._api_post(
                    path_url=CONSTANTS.TRADER_FEES_PATH_URL,
                    data=data,
                    is_auth_required=True,
                    limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
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

    def _create_fee_for_trade(self, tracked_order: InFlightOrder, fee_amount: Decimal) -> TradeFeeBase:
        """Helper to create fee object for a trade"""
        base, quote = tracked_order.trading_pair.split("-")
        fee_currency = quote if tracked_order.trade_type == TradeType.BUY else base
        
        return TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=tracked_order.trade_type,
            percent_token=fee_currency,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_currency)]
        )

    def _create_trade_update_from_trade_data(
        self,
        trade_data: Dict[str, Any],
        tracked_order: InFlightOrder
    ) -> TradeUpdate:
        """
        Helper to create TradeUpdate from trade data dict.
        
        Handles two different formats:
        1. REST API (/tradeHistory): has "orderId" field
        2. WebSocket: has "buyOrderId" and "sellOrderId", use "orderType" to determine which is ours
        """
        fill_amount = Decimal(str(trade_data.get("amount", "0")))
        fill_price = Decimal(str(trade_data.get("price", "0")))
        fill_timestamp = float(trade_data.get("date", trade_data.get("createdTimestamp", self.current_timestamp * 1000))) / 1000
        fee_amount = Decimal(str(trade_data.get("fee", "0")))
        
        # Determine exchange_order_id based on source format
        if "orderId" in trade_data:
            # REST API format
            exchange_order_id = str(trade_data.get("orderId"))
        else:
            # WebSocket format - use orderType to pick correct ID
            order_type = trade_data.get("orderType", "")
            if order_type == "BUY":
                exchange_order_id = str(trade_data.get("buyOrderId", ""))
            elif order_type == "SELL":
                exchange_order_id = str(trade_data.get("sellOrderId", ""))
            else:
                exchange_order_id = str(tracked_order.exchange_order_id)
        
        fee = self._create_fee_for_trade(tracked_order, fee_amount)
        
        return TradeUpdate(
            trade_id=str(trade_data.get("transactionId", "")),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fee=fee,
            fill_base_amount=fill_amount,
            fill_quote_amount=fill_amount * fill_price,
            fill_price=fill_price,
            fill_timestamp=fill_timestamp,
        )

    def _create_order_update(
        self,
        tracked_order: InFlightOrder,
        new_state: OrderState
    ) -> OrderUpdate:
        """Helper to create OrderUpdate from tracked order"""
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=new_state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
        )

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("event")

                if event_type == "data":
                    channel = event_message.get("channel")
                    payload = event_message.get("payload")
                    if "private-open_orders" in channel:
                        await self._process_order_events(payload)
                    elif "private-user_balances" in channel:
                        await self._process_balance_event(payload)
                    elif "private-user-trades" in channel:
                        await self._process_trade_events(payload)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True
                )
                await self._sleep(5.0)

    async def _process_order_events(self, payload):
        if isinstance(payload, list):
            for order_data in payload:
                await self._process_order_event(order_data)
        else:
            await self._process_order_event(payload)

    async def _process_order_event(self, order_data):
        try:
            order_id = str(order_data.get("id", ""))
            change_event = order_data.get("orderChangePushEvent", "")
            amount = Decimal(str(order_data.get("amount", "0")))
            original = Decimal(str(order_data.get("original", "0")))

            tracked_order = None
            for tracked in self._order_tracker.all_fillable_orders.values():
                if tracked.exchange_order_id == order_id:
                    tracked_order = tracked
                    break

            if tracked_order is None:
                self.logger().debug(f"Order {order_id} not found in tracked orders")
                return

            if change_event == "CREATION":
                new_state = OrderState.OPEN
                
            elif change_event == "SNAPSHOT":
                new_state = OrderState.OPEN
                
            elif change_event == "UPDATE":
                if 0 < amount < original:
                    new_state = OrderState.PARTIALLY_FILLED
                elif amount == 0:
                    new_state = OrderState.FILLED
                else:
                    new_state = OrderState.OPEN
                    
            elif change_event == "REMOVAL":
                if amount == 0 and original > 0:
                    new_state = OrderState.FILLED
                else:
                    new_state = OrderState.CANCELED
                    
            else:
                self.logger().warning(f"Unknown orderChangePushEvent: {change_event} for order {order_id}")
                return

            order_update = self._create_order_update(tracked_order, new_state)
            self._order_tracker.process_order_update(order_update)

        except Exception as e:
            self.logger().error(f"Error processing order event: {e}", exc_info=True)

    async def _process_balance_event(self, payload):
        try:
            balances = payload.get("balances", {})

            for currency, balance_data in balances.items():
                if isinstance(balance_data, dict):
                    total_balance = Decimal(str(balance_data.get("balance", "0")))
                    available_balance = Decimal(str(balance_data.get("available", "0")))
                    reserved_balance = Decimal(str(balance_data.get("reserved", "0")))

                    self._account_balances[currency] = total_balance
                    self._account_available_balances[currency] = available_balance

        except Exception as e:
            self.logger().error(f"Error processing balance event: {e}", exc_info=True)

    async def _process_trade_events(self, payload):
        if isinstance(payload, list):
            for trade_data in payload:
                await self._process_trade_event(trade_data)
        else:
            await self._process_trade_event(payload)

    async def _process_trade_event(self, trade_data):
        try:
            order_type = trade_data.get("orderType", "")
            if order_type == "BUY":
                order_id = str(trade_data.get("buyOrderId", ""))
            elif order_type == "SELL":
                order_id = str(trade_data.get("sellOrderId", ""))
            else:
                self.logger().warning(f"Unknown orderType in trade event: {order_type}")
                return

            tracked_order = None
            for order in self._order_tracker.all_fillable_orders.values():
                if order.exchange_order_id == order_id:
                    tracked_order = order
                    break

            if tracked_order is None:
                self.logger().debug(f"Trade for untracked order {order_id}, ignoring")
                return

            trade_update = self._create_trade_update_from_trade_data(trade_data, tracked_order)
            self._order_tracker.process_trade_update(trade_update)

        except Exception as e:
            self.logger().error(f"Error processing trade event: {e}", exc_info=True)

    async def _update_balances(self):
        try:
            response = await self._api_post(
                path_url=CONSTANTS.ACCOUNTS_PATH_URL,
                data={},
                is_auth_required=True,
                limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
            )

            if response.get("error"):
                error_message = response.get("errorMessage", "Unknown error")
                self.logger().error(f"Error fetching balances: {error_message}")
                return

            balances_data = response.get("data", {})

            self._account_balances.clear()
            self._account_available_balances.clear()

            for currency, balance_info in balances_data.items():
                if isinstance(balance_info, dict):
                    total_balance = Decimal(str(balance_info.get("balance", "0")))
                    available_balance = Decimal(str(balance_info.get("available", "0")))

                    self._account_balances[currency] = total_balance
                    self._account_available_balances[currency] = available_balance
                else:
                    balance = Decimal(str(balance_info))
                    if balance > 0:
                        self._account_balances[currency] = balance
                        self._account_available_balances[currency] = balance


        except Exception as e:
            self.logger().error(f"Exception during balance update: {e}", exc_info=True)

    async def _update_order_fills_from_trades(self):
        if len(self._order_tracker.all_orders) == 0:
            return

        order_by_exchange_id_map: Dict[str, InFlightOrder] = {}
        for tracked_order in self._order_tracker.all_orders.values():
            if tracked_order.exchange_order_id is not None:
                order_by_exchange_id_map[tracked_order.exchange_order_id] = tracked_order

        if len(order_by_exchange_id_map) == 0:
            return

        try:
            data = {
                "limit": 100,
                "sort": "DESC",
                "timestampFrom": int((self.current_timestamp - 24 * 60 * 60) * 1000)
            }

            response = await self._api_post(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                data=data,
                is_auth_required=True,
                limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
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
                        tracked_order = order_by_exchange_id_map[exchange_order_id]
                        trade_update = self._create_trade_update_from_trade_data(trade, tracked_order)
                        self._order_tracker.process_trade_update(trade_update)

                except Exception as e:
                    self.logger().error(f"Error processing trade update: {e}", exc_info=True)
                    continue

        except Exception as e:
            self.logger().error(f"Error fetching trade history for order fills: {e}", exc_info=True)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        try:
            coinmate_symbol = web_utils.convert_to_exchange_trading_pair(trading_pair)

            response = await self._api_get(
                path_url=CONSTANTS.TICKER_PATH_URL,
                params={"currencyPair": coinmate_symbol},
                limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
            )

            if response.get("error"):
                raise IOError(f"Error fetching ticker: {response.get('errorMessage', 'Unknown error')}")

            data = response.get("data", {})
            last_price = float(data.get("last", 0))
            return last_price

        except Exception as e:
            self.logger().error(f"Error getting last traded price for {trading_pair}: {e}", exc_info=True)
            return 0.0

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        try:
            data = {"orderId": tracked_order.exchange_order_id}

            response = await self._api_post(
                path_url=CONSTANTS.ORDER_BY_ID_PATH_URL,
                data=data,
                is_auth_required=True,
                limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
            )

            if response.get("error"):
                raise IOError(f"Error fetching order status: {response.get('errorMessage', 'Unknown error')}")

            order_data = response.get("data")
            order_status = order_data.get("status")
            new_state = CONSTANTS.ORDER_STATE.get(order_status, OrderState.OPEN)

            return self._create_order_update(tracked_order, new_state)

        except Exception as e:
            self.logger().error(f"Error requesting order status for {tracked_order.client_order_id}: {e}", exc_info=True)
            raise

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            try:
                data = {
                    "orderId": order.exchange_order_id,
                    "limit": 1000
                }

                response = await self._api_post(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    data=data,
                    is_auth_required=True,
                    limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
                )

                if not response.get("error") and response.get("data"):
                    trades = response.get("data", [])

                    for trade in trades:
                        if str(trade.get("orderId", "")) == order.exchange_order_id:
                            trade_update = self._create_trade_update_from_trade_data(trade, order)
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
    
    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "currencyPair": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }
        
        resp_json = await self._api_get(
            path_url=CONSTANTS.TICKER_PATH_URL,
            params=params,
            limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID
        )
        
        if resp_json.get("error"):
            return 0.0
            
        return float(resp_json.get("data", {}).get("last", 0.0))
