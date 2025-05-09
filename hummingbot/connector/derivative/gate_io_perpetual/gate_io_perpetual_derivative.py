import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.gate_io_perpetual import (
    gate_io_perpetual_constants as CONSTANTS,
    gate_io_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_api_order_book_data_source import (
    GateIoPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_auth import GateIoPerpetualAuth
from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_user_stream_data_source import (
    GateIoPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class GateIoPerpetualDerivative(PerpetualDerivativePyBase):
    """
    GateIoPerpetualExchange connects with Gate.io Derivative and provides order book pricing, user account tracking and
    trading functionality.
    """
    DEFAULT_DOMAIN = ""

    # Using 120 seconds here as Gate.io websocket is quiet
    TICK_INTERVAL_LIMIT = 120.0

    web_utils = web_utils

    # ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3
    # ORDER_NOT_EXIST_CANCEL_COUNT = 2

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 gate_io_perpetual_api_key: str,
                 gate_io_perpetual_secret_key: str,
                 gate_io_perpetual_user_id: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = DEFAULT_DOMAIN):
        """
        :param gate_io_perpetual_api_key: The API key to connect to private Gate.io APIs.
        :param gate_io_perpetual_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        self._gate_io_perpetual_api_key = gate_io_perpetual_api_key
        self._gate_io_perpetual_secret_key = gate_io_perpetual_secret_key
        self._gate_io_perpetual_user_id = gate_io_perpetual_user_id
        self._domain = domain
        self._position_mode = None
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs

        super().__init__(client_config_map)

        self._real_time_balance_update = False

    @property
    def authenticator(self):
        return GateIoPerpetualAuth(
            api_key=self._gate_io_perpetual_api_key,
            secret_key=self._gate_io_perpetual_secret_key)

    @property
    def name(self) -> str:
        return "gate_io_perpetual"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.NETWORK_CHECK_PATH_URL

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

    def _format_amount_to_size(self, trading_pair, amount: Decimal) -> Decimal:
        trading_rule = self._trading_rules[trading_pair]
        quanto_multiplier = Decimal(trading_rule.min_base_amount_increment)
        size = amount / quanto_multiplier
        return size

    def _format_size_to_amount(self, trading_pair, size: Decimal) -> Decimal:
        trading_rule = self._trading_rules[trading_pair]
        quanto_multiplier = Decimal(trading_rule.min_base_amount_increment)
        amount = size * quanto_multiplier
        return amount

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self):
        """
        This method needs to be overridden to provide the accurate information depending on the exchange.
        """
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def start(self, clock: Clock, timestamp: float):
        """
        This function is called automatically by the clock.
        """
        super().start(clock, timestamp)

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # API documentation does not clarify the error message for timestamp related problems
        return False

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

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GateIoPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GateIoPerpetualAPIUserStreamDataSource(
            auth=self._auth,
            user_id=self._gate_io_perpetual_user_id,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def start_network(self):
        """
        Start all required tasks to update the status of the connector.
        """
        await self._update_trading_rules()
        await super().start_network()

    async def _format_trading_rules(self, raw_trading_pair_info) -> List[TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param symbols_info: The json API response
        :return A dictionary of trading rules.
        Response Example:
        [
            {
                "name": "BTC_USDT",
                "type": "direct",
                "quanto_multiplier": "0.0001",
                "ref_discount_rate": "0",
                "order_price_deviate": "0.5",
                "maintenance_rate": "0.005",
                "mark_type": "index",
                "last_price": "38026",
                "mark_price": "37985.6",
                "index_price": "37954.92",
                "funding_rate_indicative": "0.000219",
                "mark_price_round": "0.01",
                "funding_offset": 0,
                "in_delisting": false,
                "risk_limit_base": "1000000",
                "interest_rate": "0.0003",
                "order_price_round": "0.1",
                "order_size_min": 1,
                "ref_rebate_rate": "0.2",
                "funding_interval": 28800,
                "risk_limit_step": "1000000",
                "leverage_min": "1",
                "leverage_max": "100",
                "risk_limit_max": "8000000",
                "maker_fee_rate": "-0.00025",
                "taker_fee_rate": "0.00075",
                "funding_rate": "0.002053",
                "order_size_max": 1000000,
                "funding_next_apply": 1610035200,
                "short_users": 977,
                "config_change_time": 1609899548,
                "trade_size": 28530850594,
                "position_size": 5223816,
                "long_users": 455,
                "funding_impact_value": "60000",
                "orders_limit": 50,
                "trade_id": 10851092,
                "orderbook_id": 2129638396
              }
        ]
        """
        result = {}

        for rule in raw_trading_pair_info:
            try:
                if not web_utils.is_exchange_information_valid(rule):
                    continue

                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule["name"])

                min_amount_inc = Decimal(f"{rule['quanto_multiplier']}")
                min_price_inc = Decimal(f"{rule['order_price_round']}")
                min_amount = min_amount_inc
                min_notional = Decimal(str(1))
                result[trading_pair] = TradingRule(trading_pair,
                                                   min_order_size=min_amount,
                                                   min_price_increment=min_price_inc,
                                                   min_base_amount_increment=min_amount_inc,
                                                   min_notional_size=min_notional,
                                                   min_order_value=min_notional,
                                                   )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return list(result.values())

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        size = self._format_amount_to_size(trading_pair, amount)
        data = {
            "text": order_id,
            "contract": symbol,
            "size": float(-size) if trade_type.name.lower() == 'sell' else float(size),
        }
        if order_type.is_limit_type():
            data.update({
                "price": f"{price:f}",
                "tif": "gtc",
            })
            if order_type is OrderType.LIMIT_MAKER:
                data.update({"tif": "poc"})
        else:
            data.update({
                "price": "0",
                "tif": "ioc",
            })

        # RESTRequest does not support json, and if we pass a dict
        # the underlying aiohttp will encode it to params
        data = data
        endpoint = CONSTANTS.ORDER_CREATE_PATH_URL
        order_result = await self._api_post(
            path_url=endpoint,
            data=data,
            is_auth_required=True,
            limit_id=endpoint,
        )
        if order_result.get('finish_as') in {"cancelled", "expired", "failed", "ioc"}:
            raise IOError({"label": "ORDER_REJECTED", "message": "Order rejected."})
        exchange_order_id = str(order_result["id"])
        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        This implementation-specific method is called by _cancel
        returns True if successful
        """
        canceled = False
        exchange_order_id = await tracked_order.get_exchange_order_id()
        resp = await self._api_delete(
            path_url=CONSTANTS.ORDER_DELETE_PATH_URL.format(id=exchange_order_id),
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_DELETE_LIMIT_ID,
        )
        canceled = resp.get("finish_as") == "cancelled"
        return canceled

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        account_info = ""
        try:
            account_info = await self._api_get(
                path_url=CONSTANTS.USER_BALANCES_PATH_URL,
                is_auth_required=True,
                limit_id=CONSTANTS.USER_BALANCES_PATH_URL
            )
            self._process_balance_message(account_info)
        except Exception as e:
            self.logger().network(
                f"Unexpected error while fetching balance update - {str(e)}", exc_info=True,
                app_warning_msg=(f"Could not fetch balance update from {self.name_cap}"))
            raise e
        return account_info

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(
                method=RESTMethod.GET,
                path_url=CONSTANTS.NETWORK_CHECK_PATH_URL,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def _process_balance_message(self, account):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        asset_name = account["currency"]
        self._account_available_balances[asset_name] = Decimal(str(account["available"]))
        self._account_balances[asset_name] = Decimal(str(account["total"]))
        remote_asset_names.add(asset_name)
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _process_balance_message_ws(self, balance_update):
        for account in balance_update:
            asset_name = "USDT"
            self._account_available_balances[asset_name] = Decimal(str(account["balance"])) - Decimal(
                str(account["change"]))
            self._account_balances[asset_name] = Decimal(str(account["balance"]))

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        try:
            exchange_order_id = await order.get_exchange_order_id()
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "contract": trading_pair,
                    "order": exchange_order_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_PATH_URL)

            for trade_fill in all_fills_response:
                trade_update = self._create_trade_update_with_order_fill_data(
                    order_fill=trade_fill,
                    order=order)
                trade_updates.append(trade_update)

        except asyncio.TimeoutError:
            raise IOError(f"Skipped order update with order fills for {order.client_order_id} "
                          "- waiting for exchange order id.")

        return trade_updates

    def _create_trade_update_with_order_fill_data(
            self,
            order_fill: Dict[str, Any],
            order: InFlightOrder):
        fee_asset = order.quote_asset
        # no "position_action" in return, should use AddedToCostTradeFee, same as new_spot_fee
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,
            percent_token=fee_asset,
            flat_fees=[TokenAmount(
                amount=Decimal(order_fill["fee"]),
                token=fee_asset
            )]
        )

        trade_update = TradeUpdate(
            trade_id=str(order_fill["id"]),
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=abs(self._format_size_to_amount(order.trading_pair, (Decimal(str(order_fill["size"]))))),
            fill_quote_amount=abs(
                self._format_size_to_amount(order.trading_pair, (Decimal(str(order_fill["size"])))) * Decimal(
                    order_fill["price"])),
            fill_price=Decimal(order_fill["price"]),
            fill_timestamp=order_fill["create_time"],
        )
        return trade_update

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        try:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            updated_order_data = await self._api_get(
                path_url=CONSTANTS.ORDER_STATUS_PATH_URL.format(id=exchange_order_id),
                is_auth_required=True,
                limit_id=CONSTANTS.ORDER_STATUS_LIMIT_ID)

            order_update = self._create_order_update_with_order_status_data(
                order_status=updated_order_data,
                order=tracked_order)
        except asyncio.TimeoutError:
            raise IOError(f"Skipped order status update for {tracked_order.client_order_id}"
                          f" - waiting for exchange order id.")

        return order_update

    def _create_order_update_with_order_status_data(self, order_status: Dict[str, Any], order: InFlightOrder):
        client_order_id = str(order_status.get("text", ""))
        state = self._normalise_order_message_state(order_status, order) or order.current_state

        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=int(order_status["create_time"]),
            new_state=state,
            client_order_id=client_order_id,
            exchange_order_id=str(order_status["id"]),
        )
        return order_update

    def _normalise_order_message_state(self, order_msg: Dict[str, Any], tracked_order):
        state = None
        # we do not handle:
        #   "failed" because it is handled by create order
        #   "put" as the exchange order id is returned in the create order response
        #   "open" for same reason

        # same field for both WS and REST
        amount_left = Decimal(str(order_msg.get("left")))
        status = order_msg.get("status")
        finish_as = order_msg.get("finish_as")
        size = Decimal(str(order_msg.get("size")))
        if status == "finished":
            if finish_as == 'filled':
                state = OrderState.FILLED
            else:
                state = OrderState.CANCELED
        else:
            if amount_left > 0 and amount_left != size:
                state = OrderState.PARTIALLY_FILLED
        return state

    # use bybitperpetual sample,not gateio sample

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

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        user_channels = [
            CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            CONSTANTS.USER_BALANCE_ENDPOINT_NAME,
            CONSTANTS.USER_POSITIONS_ENDPOINT_NAME,
        ]
        async for event_message in self._iter_user_event_queue():
            try:
                if isinstance(event_message, dict):
                    channel: str = event_message.get("channel", None)
                    results: List[Dict[str, Any]] = event_message.get("result", None)
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
                elif channel == CONSTANTS.USER_BALANCE_ENDPOINT_NAME:
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
        https://www.gate.io/docs/apiv4/en/#retrieve-market-trades
        """
        client_order_id = client_order_id or str(trade.get("text", ""))
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)

        if tracked_order is None:
            self.logger().debug(f"Ignoring trade message with id {client_order_id}: not in in_flight_orders.")
        else:
            trade_update = self._create_trade_update_with_order_fill_data(
                order_fill=trade,
                order=tracked_order)
            self._order_tracker.process_trade_update(trade_update)

    async def _process_account_position_message(self, position_msg: Dict[str, Any]):
        """
        Updates position
        :param position_msg: The position event message payload
        """
        ex_trading_pair = position_msg["contract"]
        trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=ex_trading_pair)
        amount = Decimal(str(position_msg["size"]))
        trading_rule = self._trading_rules[trading_pair]
        amount_precision = Decimal(trading_rule.min_base_amount_increment)
        position_side = PositionSide.LONG if Decimal(position_msg.get("size")) > 0 else PositionSide.SHORT
        pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
        entry_price = Decimal(str(position_msg["entry_price"]))
        position = self._perpetual_trading.get_position(trading_pair, position_side)
        if position is not None:
            if amount == Decimal("0"):
                self._perpetual_trading.remove_position(pos_key)
            else:
                position.update_position(position_side=position_side,
                                         unrealized_pnl=None,
                                         entry_price=entry_price,
                                         amount=amount * amount_precision)
        else:
            await self._update_positions()

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancelation or failure event if needed.

        :param order_msg: The order response from either REST or web socket API (they are of the same format)

        Example Order:
        https://www.gate.io/docs/apiv4/en/#list-orders
        """
        client_order_id = str(order_msg.get("text", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return

        order_update = self._create_order_update_with_order_status_data(order_status=order_msg, order=tracked_order)
        self._order_tracker.process_order_update(order_update=order_update)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(web_utils.is_exchange_information_valid, exchange_info):
            exchange_symbol = symbol_data["name"]
            base = symbol_data["name"].split('_')[0]
            quote = symbol_data["name"].split('_')[1]
            trading_pair = combine_to_hb_trading_pair(base, quote)
            if trading_pair in mapping.inverse:
                self._resolve_trading_pair_symbols_duplicate(mapping, exchange_symbol, base, quote)
            else:
                mapping[exchange_symbol] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    def _resolve_trading_pair_symbols_duplicate(self, mapping: bidict, new_exchange_symbol: str, base: str, quote: str):
        """Resolves name conflicts provoked by futures contracts.

        If the expected BASEQUOTE combination matches one of the exchange symbols, it is the one taken, otherwise,
        the trading pair is removed from the map and an error is logged.
        """
        expected_exchange_symbol = f"{base}_{quote}"
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

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "contract": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PATH_URL,
            params=params
        )

        return float(resp_json[0]["last"])

    async def _update_positions(self):
        """
        Retrieves all positions using the REST API.
        """

        positions = await self._api_get(
            path_url=CONSTANTS.POSITION_INFORMATION_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.POSITION_INFORMATION_URL
        )

        for position in positions:
            ex_trading_pair = position.get("contract")
            hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(ex_trading_pair)

            amount = Decimal(position.get("size"))
            ex_mode = position.get("mode")
            if ex_mode == 'single':
                mode = PositionMode.ONEWAY
                position_side = PositionSide.LONG if Decimal(position.get("size")) > 0 else PositionSide.SHORT
            else:
                mode = PositionMode.HEDGE
                position_side = PositionSide.LONG if ex_mode == "dual_long" else PositionSide.SHORT
            pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side, mode)

            if amount != 0:
                trading_rule = self._trading_rules[hb_trading_pair]
                amount_precision = Decimal(trading_rule.min_base_amount_increment)

                unrealized_pnl = Decimal(position.get("unrealised_pnl"))
                entry_price = Decimal(position.get("entry_price"))
                leverage = Decimal(position.get("leverage"))
                position = Position(
                    trading_pair=hb_trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount * amount_precision,
                    leverage=leverage,
                )
                self._perpetual_trading.set_position(pos_key, position)

            else:
                self._perpetual_trading.remove_position(pos_key)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        if self._position_mode is None:
            response = await self._api_get(
                path_url=CONSTANTS.POSITION_INFORMATION_URL,
                is_auth_required=True,
                limit_id=CONSTANTS.POSITION_INFORMATION_URL
            )
            self._position_mode = PositionMode.ONEWAY if response[0]["mode"] == 'single' else PositionMode.HEDGE
        return self._position_mode

    async def _execute_set_position_mode_for_pairs(
            # To-do: ensure there's no active order or contract before changing position mode
            self, mode: PositionMode, trading_pairs: List[str]
    ) -> Tuple[bool, List[str], str]:
        successful_pairs = []
        success = True
        msg = ""

        for trading_pair in trading_pairs:
            initial_mode = await self._get_position_mode()
            if mode != initial_mode:
                success, msg = await self._trading_pair_position_mode_set(mode, trading_pair)
                self._position_mode = mode
            if success:
                successful_pairs.append(trading_pair)
            else:
                self.logger().network(f"Error switching {trading_pair} mode to {mode}: {msg}")
                break

        return success, successful_pairs, msg

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        msg = ""
        success = True

        dual_mode = 'true' if mode is PositionMode.HEDGE else 'false'

        data = {"dual_mode": dual_mode}

        response = await self._api_post(
            path_url=CONSTANTS.SET_POSITION_MODE_URL,
            params=data,
            is_auth_required=True,
            limit_id=CONSTANTS.SET_POSITION_MODE_URL,
        )
        if 'detail' in response:
            success = False
            msg = response['detail']
        return success, msg

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        success = True
        msg = ""
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        if self.position_mode is PositionMode.ONEWAY:
            endpoint = CONSTANTS.ONEWAY_SET_LEVERAGE_PATH_URL.format(contract=exchange_symbol)
        else:
            endpoint = CONSTANTS.HEDGE_SET_LEVERAGE_PATH_URL.format(contract=exchange_symbol)
        data = {
            "leverage": leverage,
        }
        resp = await self._api_post(
            path_url=endpoint,
            params=data,
            is_auth_required=True,
            limit_id=CONSTANTS.ONEWAY_SET_LEVERAGE_PATH_URL,
        )
        if isinstance(resp, dict):
            return_leverage = resp['leverage']
        else:
            return_leverage = resp[0]['leverage']
        if int(return_leverage) != leverage:
            success = False
            msg = "leverage is diff"
        return success, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        pass

    async def _update_funding_payment(self, trading_pair: str, fire_event_on_new: bool) -> bool:
        return True
