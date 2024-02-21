import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.bit_com_perpetual import (
    bit_com_perpetual_constants as CONSTANTS,
    bit_com_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_api_order_book_data_source import (
    BitComPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_auth import BitComPerpetualAuth
from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_user_stream_data_source import (
    BitComPerpetualUserStreamDataSource,
)
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
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

bpm_logger = None


class BitComPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            bit_com_perpetual_api_key: str = None,
            bit_com_perpetual_api_secret: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self.bit_com_perpetual_api_key = bit_com_perpetual_api_key
        self.bit_com_perpetual_secret_key = bit_com_perpetual_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> BitComPerpetualAuth:
        return BitComPerpetualAuth(self.bit_com_perpetual_api_key, self.bit_com_perpetual_secret_key)

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
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self):
        """
        This method needs to be overridden to provide the accurate information depending on the exchange.
        """
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth)

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path,
                                            params={"currency": CONSTANTS.CURRENCY})
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_pairs_request_path,
                                            params={"currency": CONSTANTS.CURRENCY})
        return exchange_info

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_cancel_order_not_found_in_the_exchange when replacing the
        # dummy implementation
        return False

    async def _update_trading_rules(self):
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path,
                                            params={"currency": CONSTANTS.CURRENCY})
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _initialize_trading_pair_symbol_map(self):
        try:
            exchange_info = await self._api_get(path_url=self.trading_pairs_request_path,
                                                params={"currency": CONSTANTS.CURRENCY})

            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BitComPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BitComPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker or False
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

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        api_params = {
            "label": order_id,
            "currency": CONSTANTS.CURRENCY,
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=api_params,
            is_auth_required=True)
        if cancel_result['data']['num_cancelled'] == 1:
            return True
        return False

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

        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {"instrument_id": symbol,
                      "price": price_str,
                      "qty": amount_str,
                      "side": "buy" if trade_type is TradeType.BUY else "sell",
                      "order_type": "market" if order_type is OrderType.MARKET else "limit",
                      "label": order_id
                      }
        if order_type == OrderType.MARKET:
            del api_params["price"]
        if order_type == OrderType.LIMIT_MAKER:
            api_params["post_only"] = False
            api_params["reject_post_only"] = True

        order_result = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_URL,
            data=api_params,
            is_auth_required=True)
        o_id = str(order_result['data']["order_id"])
        transact_time = order_result['data']["updated_at"]
        return (o_id, transact_time)

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        # This method in the base ExchangePyBase, makes an API call for each order.
        # Given the rate limit of the API method and the breadth of info provided by the method
        # the mitigation proposal is to collect all orders in one shot, then parse them
        # Note that this is limited to 100 orders (pagination)
        all_trades_updates: List[TradeUpdate] = []
        if len(orders) > 0:
            try:
                all_trades_updates: List[TradeUpdate] = await self._all_trade_updates(orders=orders)
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                self.logger().warning(
                    f"Failed to fetch trade updates. Error: {request_error}",
                    exc_info=request_error,
                )
            for trade_update in all_trades_updates:
                self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates(self, orders: List[InFlightOrder]) -> List[TradeUpdate]:
        trade_updates = []
        if len(orders) > 0:
            trading_pairs_to_order_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {})
            for order in orders:
                trading_pairs_to_order_map[order.trading_pair][order.exchange_order_id] = order
            trading_pairs = list(trading_pairs_to_order_map.keys())
            tasks = [
                self._api_get(
                    path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                    params={
                        "currency": CONSTANTS.CURRENCY,
                        "instrument_id": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
                    },
                    is_auth_required=True)
                for trading_pair in trading_pairs
            ]
            self.logger().debug(f"Polling for order fills of {len(tasks)} trading_pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for trades, trading_pair in zip(results, trading_pairs):
                order_map = trading_pairs_to_order_map.get(trading_pair)
                if isinstance(trades, Exception) or trades.get("code") != 0:
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades.get("data", []):
                    order_id = str(trade.get("order_id"))
                    if order_id in order_map:
                        tracked_order: InFlightOrder = order_map.get(order_id)
                        position_side = "LONG" if trade["side"] == "buy" else "SHORT"
                        position_action = (PositionAction.OPEN
                                           if (tracked_order.trade_type is TradeType.BUY and position_side == "LONG"
                                               or tracked_order.trade_type is TradeType.SELL and position_side == "SHORT")
                                           else PositionAction.CLOSE)
                        fee_asset = tracked_order.quote_asset
                        fee = TradeFeeBase.new_perpetual_fee(
                            fee_schema=self.trade_fee_schema(),
                            position_action=position_action,
                            percent_token=fee_asset,
                            flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=fee_asset)]
                        )
                        trade_update: TradeUpdate = TradeUpdate(
                            trade_id=str(trade["trade_id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=trade["order_id"],
                            trading_pair=tracked_order.trading_pair,
                            fill_timestamp=trade["created_at"] * 1e-3,
                            fill_price=Decimal(trade["price"]),
                            fill_base_amount=Decimal(trade["qty"]),
                            fill_quote_amount=Decimal(trade["price"]) * Decimal(trade["qty"]),
                            fee=fee,
                        )
                        trade_updates.append(trade_update)

        return trade_updates

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        raise Exception("Developer: This method should not be called, it is obsoleted for bit_com")
        trade_updates = []
        try:
            exchange_order_id = await order.get_exchange_order_id()
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                params={
                    "currency": CONSTANTS.CURRENCY,
                    "instrument_id": trading_pair,
                },
                is_auth_required=True)

            for trade in all_fills_response["data"]:
                order_id = str(trade.get("order_id"))
                if order_id == exchange_order_id:
                    position_side = "LONG" if trade["side"] == "buy" else "SHORT"
                    position_action = (PositionAction.OPEN
                                       if (order.trade_type is TradeType.BUY and position_side == "LONG"
                                           or order.trade_type is TradeType.SELL and position_side == "SHORT")
                                       else PositionAction.CLOSE)
                    fee_asset = order.quote_asset
                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema(),
                        position_action=position_action,
                        percent_token=fee_asset,
                        flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=fee_asset)]
                    )
                    trade_update: TradeUpdate = TradeUpdate(
                        trade_id=str(trade["trade_id"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=trade["order_id"],
                        trading_pair=order.trading_pair,
                        fill_timestamp=trade["created_at"] * 1e-3,
                        fill_price=Decimal(trade["price"]),
                        fill_base_amount=Decimal(trade["qty"]),
                        fill_quote_amount=Decimal(trade["price"]) * Decimal(trade["qty"]),
                        fee=fee,
                    )
                    trade_updates.append(trade_update)

        except asyncio.TimeoutError:
            raise IOError(f"Skipped order update with order fills for {order.client_order_id} "
                          "- waiting for exchange order id.")

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        order_update = await self._api_get(
            path_url=CONSTANTS.ORDER_URL,
            params={
                "currency": CONSTANTS.CURRENCY,
                "instrument_id": trading_pair,
                "label": tracked_order.client_order_id
            },
            is_auth_required=True)
        current_state = order_update["data"][0]["status"]
        _order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_update["data"][0]["updated_at"] * 1e-3,
            new_state=CONSTANTS.ORDER_STATE[current_state],
            client_order_id=order_update["data"][0]["label"],
            exchange_order_id=order_update["data"][0]["order_id"],
        )
        return _order_update

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Bit. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        user_channels = [
            CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            CONSTANTS.USER_POSITIONS_ENDPOINT_NAME,
            CONSTANTS.USER_BALANCES_ENDPOINT_NAME,
        ]
        async for event_message in self._iter_user_event_queue():
            try:
                if isinstance(event_message, dict):
                    channel: str = event_message.get("channel", None)
                    results: List[Dict[str, Any]] = event_message.get("data", None)
                elif event_message is asyncio.CancelledError:
                    raise asyncio.CancelledError
                else:
                    raise Exception(event_message)
                if channel not in user_channels:
                    self.logger().error(
                        f"Unexpected message in user stream: {event_message}.", exc_info=True)
                    continue

                if channel == CONSTANTS.USER_TRADES_ENDPOINT_NAME:
                    for trade_msg in results:
                        self._process_trade_message(trade_msg)
                elif channel == CONSTANTS.USER_ORDERS_ENDPOINT_NAME:
                    for order_msg in results:
                        self._process_order_message(order_msg)
                elif channel == CONSTANTS.USER_POSITIONS_ENDPOINT_NAME:
                    for position_msg in results:
                        await self._process_account_position_message(position_msg)
                elif channel == CONSTANTS.USER_BALANCES_ENDPOINT_NAME:
                    self._process_balance_message_ws(results)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    def _process_trade_message(self, trade: Dict[str, Any], client_order_id: Optional[str] = None):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        Example Trade:
        """
        client_order_id = client_order_id or str(trade.get("label", ""))
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)

        if tracked_order is None:
            self.logger().debug(f"Ignoring trade message with id {client_order_id}: not in in_flight_orders.")
        else:
            position_side = "LONG" if trade["side"] == "buy" else "SHORT"
            position_action = (PositionAction.OPEN
                               if (tracked_order.trade_type is TradeType.BUY and position_side == "LONG"
                                   or tracked_order.trade_type is TradeType.SELL and position_side == "SHORT")
                               else PositionAction.CLOSE)
            fee_asset = tracked_order.quote_asset
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=fee_asset)]
            )
            trade_update: TradeUpdate = TradeUpdate(
                trade_id=str(trade["trade_id"]),
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=trade["order_id"],
                trading_pair=tracked_order.trading_pair,
                fill_timestamp=trade["created_at"] * 1e-3,
                fill_price=Decimal(trade["price"]),
                fill_base_amount=Decimal(trade["qty"]),
                fill_quote_amount=Decimal(trade["price"]) * Decimal(trade["qty"]),
                fee=fee,
            )
            self._order_tracker.process_trade_update(trade_update)

    async def _process_account_position_message(self, position_msg: Dict[str, Any]):
        """
        Updates position
        :param position_msg: The position event message payload
        """
        ex_trading_pair = position_msg["instrument_id"]
        trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=ex_trading_pair)
        amount = Decimal(position_msg["qty"])
        position_side = PositionSide.LONG if Decimal(position_msg.get("qty")) > 0 else PositionSide.SHORT

        pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
        entry_price = Decimal(str(position_msg["avg_price"]))
        position = self._perpetual_trading.get_position(trading_pair, position_side)
        if position is not None:
            if amount == Decimal("0"):
                self._perpetual_trading.remove_position(pos_key)
            else:
                position.update_position(position_side=position_side,
                                         unrealized_pnl=Decimal(position_msg['position_session_upl']),
                                         entry_price=entry_price,
                                         amount=amount)
        else:
            await self._update_positions()

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancelation or failure event if needed.

        :param order_msg: The order response from either REST or web socket API (they are of the same format)

        Example Order:
        """
        client_order_id = str(order_msg.get("label", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return
        # order_update = self._create_order_update_with_order_status_data(order_status=order_msg, order=tracked_order)
        current_state = order_msg["status"]
        order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_msg["updated_at"] * 1e-3,
            new_state=CONSTANTS.ORDER_STATE[current_state],
            client_order_id=order_msg["label"],
            exchange_order_id=order_msg["order_id"],
        )
        self._order_tracker.process_order_update(order_update=order_update)

    def _process_balance_message_ws(self, balance_update):
        for account in balance_update["details"]:
            asset_name = account["currency"]
            self._account_available_balances[asset_name] = Decimal(str(account["available_balance"]))
            self._account_balances[asset_name] = Decimal(str(account["equity"]))

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        Parameters
        ----------
        exchange_info_dict:
            Trading rules dictionary response from the exchange
        """
        rules: list = exchange_info_dict.get("data", [])
        return_val: list = []
        for rule in rules:
            try:
                if web_utils.is_exchange_information_valid(rule):
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule["instrument_id"])
                    min_order_size = Decimal(rule.get("min_size"))
                    step_size = Decimal(rule.get("size_step"))
                    tick_size = Decimal(rule.get("price_step"))
                    collateral_token = rule["quote_currency"]

                    return_val.append(
                        TradingRule(
                            trading_pair,
                            min_order_size=min_order_size,
                            min_price_increment=tick_size,
                            min_base_amount_increment=step_size,
                            buy_order_collateral_token=collateral_token,
                            sell_order_collateral_token=collateral_token,
                        )
                    )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(web_utils.is_exchange_information_valid, exchange_info.get("data", [])):
            exchange_symbol = symbol_data["instrument_id"]
            base = symbol_data["base_currency"]
            quote = symbol_data["quote_currency"]
            trading_pair = combine_to_hb_trading_pair(base, quote)
            if trading_pair in mapping.inverse:
                self._resolve_trading_pair_symbols_duplicate(mapping, exchange_symbol, base, quote)
            else:
                mapping[exchange_symbol] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {"instrument_id": exchange_symbol}
        response = await self._api_get(
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL,
            params=params)
        price = float(response["data"]["last_price"])
        return price

    def _resolve_trading_pair_symbols_duplicate(self, mapping: bidict, new_exchange_symbol: str, base: str, quote: str):
        """Resolves name conflicts provoked by futures contracts.

        If the expected BASEQUOTE combination matches one of the exchange symbols, it is the one taken, otherwise,
        the trading pair is removed from the map and an error is logged.
        """
        expected_exchange_symbol = f"{base}{quote}"
        trading_pair = combine_to_hb_trading_pair(base, quote)
        current_exchange_symbol = mapping.inverse[trading_pair]
        if current_exchange_symbol == expected_exchange_symbol:
            pass
        elif new_exchange_symbol == expected_exchange_symbol:
            mapping.pop(current_exchange_symbol)
            mapping[new_exchange_symbol] = trading_pair
        else:
            self.logger().error(
                f"Could not resolve the exchange symbols {new_exchange_symbol} and {current_exchange_symbol}")
            mapping.pop(current_exchange_symbol)

    async def _update_balances(self):
        """
        Calls the REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(path_url=CONSTANTS.ACCOUNT_INFO_URL,
                                           is_auth_required=True,
                                           )
        assets = account_info["data"].get("details")
        for asset in assets:
            asset_name = asset.get("currency")
            available_balance = Decimal(asset.get("available_balance"))
            wallet_balance = Decimal(asset.get("equity"))
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = wallet_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        positions = await self._api_get(path_url=CONSTANTS.POSITION_INFORMATION_URL,
                                        params={"currency": CONSTANTS.CURRENCY},
                                        is_auth_required=True,
                                        )
        for position in positions["data"]:
            ex_trading_pair = position.get("instrument_id")
            hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(ex_trading_pair)

            position_side = PositionSide.LONG if Decimal(position.get("qty")) > 0 else PositionSide.SHORT
            unrealized_pnl = Decimal(position.get("position_session_upl"))
            entry_price = Decimal(position.get("avg_price"))
            amount = Decimal(position.get("qty"))
            leverage = Decimal(position.get("leverage"))
            pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
            if amount != 0:
                _position = Position(
                    trading_pair=hb_trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=leverage
                )
                self._perpetual_trading.set_position(pos_key, _position)
            else:
                self._perpetual_trading.remove_position(pos_key)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        # To-do: ensure there's no active order or contract before changing position mode
        return PositionMode.ONEWAY

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        msg = ""
        success = True
        initial_mode = await self._get_position_mode()
        if initial_mode != mode:
            msg = "bit_com only supports the ONEWAY position mode."
            success = False
        return success, msg

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        pair = trading_pair
        params = {'pair': pair, 'leverage_ratio': str(leverage)}
        try:
            set_leverage = await self._api_request(
                path_url=CONSTANTS.SET_LEVERAGE_URL,
                data=params,
                method=RESTMethod.POST,
                is_auth_required=True,
            )
            success = False
            msg = ""
            if Decimal(set_leverage["data"]["leverage_ratio"]) == Decimal(str(leverage)):
                success = True
            else:
                msg = 'Unable to set leverage'
            return success, msg
        except Exception as exception:
            success = False
            msg = f"There was an error setting the leverage for {trading_pair} ({exception})"

        return success, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        payment_response = await self._api_request(
            path_url=CONSTANTS.POSITION_INFORMATION_URL,
            params={
                "currency": CONSTANTS.CURRENCY,
                "instrument_id": exchange_symbol,
            },
            method=RESTMethod.GET,
            is_auth_required=True,
        )
        funding_info_response = await self._api_request(
            path_url=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL,
            params={
                "instrument_id": exchange_symbol,
            },
            method=RESTMethod.GET,
        )
        # todo
        # if len(sorted_payment_response) < 1:
        # TypeError: object of type 'NoneType' has no len()
        sorted_payment_response = payment_response["data"] if payment_response["data"] else []
        if len(sorted_payment_response) < 1:
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
            return timestamp, funding_rate, payment
        funding_payment = sorted_payment_response[0]
        _payment = Decimal(funding_payment["session_funding"])
        funding_rate = Decimal(funding_info_response["data"]["funding_rate"])
        timestamp = funding_info_response["data"]["time"] * 1e-3
        if _payment != Decimal("0"):
            payment = _payment
        else:
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
        return timestamp, funding_rate, payment
