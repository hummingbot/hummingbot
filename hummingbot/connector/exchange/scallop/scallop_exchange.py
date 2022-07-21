import asyncio
import copy
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.scallop import (
    scallop_constants as CONSTANTS,
    scallop_utils,
    scallop_web_utils as web_utils,
)
from hummingbot.connector.exchange.scallop.scallop_api_order_book_data_source import ScallopAPIOrderBookDataSource
from hummingbot.connector.exchange.scallop.scallop_api_user_stream_data_source import ScallopAPIUserStreamDataSource
from hummingbot.connector.exchange.scallop.scallop_auth import ScallopAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None


class ScallopExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 scallop_api_key: str,
                 scallop_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = scallop_api_key
        self.secret_key = scallop_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._real_time_balance_update = False
        super().__init__(client_config_map)

    @staticmethod
    def scallop_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(scallop_type: str) -> OrderType:
        return OrderType[scallop_type]

    @property
    def authenticator(self):
        return ScallopAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "scallop"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return ScallopAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return ScallopAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal) -> Tuple[str, float]:
        order_result = None
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        type_str = ScallopExchange.scallop_order_type(order_type)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {
            "symbol": symbol,
            "side": side_str,
            "volume": amount_str,
            "type": type_str,
            "newClientOrderId": order_id,
            "price": price_str
        }

        order_result = await self._api_post(
            path_url=CONSTANTS.CREAT_ORDER_PATH_URL,
            data=api_params,
            is_auth_required=True,
            limit_id=CONSTANTS.CREAT_ORDER_PATH_URL,
        )
        o_id = str(order_result["orderId"])
        transact_time = order_result["transactTime"] * 1e-3
        return (o_id, transact_time)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "symbol": symbol,
            "newClientOrderId": order_id,
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            params=api_params,
            is_auth_required=True,
            limit_id=CONSTANTS.CANCEL_ORDER_PATH_URL,
        )
        if cancel_result.get("status") == "CANCELED":
            return True
        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            quantityPrecision: '6',
            symbol: 'btcusdt',
            pricePrecision: '2',
            baseAsset: 'BTC',
            quoteAsset: 'USDT'
        }
        """
        trading_pair_rules = exchange_info_dict.get("symbols", [])
        retval = []
        for rule in filter(scallop_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule["symbol"])

                min_amount_inc = Decimal(f"1e-{rule['quantityPrecision']}")
                min_price_inc = Decimal(f"1e-{rule['pricePrecision']}")
                retval.append(
                    TradingRule(
                        trading_pair,
                        min_price_increment=min_price_inc,
                        min_base_amount_increment=min_amount_inc,
                    )
                )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.

        Currently, Scallop does not support private channels.
        """
        pass

    async def _update_order_fills_from_trades(self):
        """
        This is intended to be a backup measure to get filled events with trade ID for orders,
        as Scallop's user stream events are not available.
        This is separated from _update_order_status which only updates the order status without producing filled
        events, since Scallop's get order endpoint does not return trade IDs.
        The minimum poll interval for order status is 10 seconds.
        """
        small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

        if (long_interval_current_tick > long_interval_last_tick
                or (self.in_flight_orders and small_interval_current_tick > small_interval_last_tick)):
            order_by_exchange_id_map = {}
            for order in self._order_tracker.all_orders.values():
                order_by_exchange_id_map[order.exchange_order_id] = order

            tasks = []
            trading_pairs = self.trading_pairs
            for trading_pair in trading_pairs:
                params = {
                    "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                }
                tasks.append(self._api_get(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    params=params,
                    is_auth_required=True))

            self.logger().debug(f"Polling for order fills of {len(tasks)} trading pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for trades, trading_pair in zip(results, trading_pairs):

                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    exchange_order_id = str(trade["bidId"]) if trade["isBuyer"] else str(trade["askId"])
                    if exchange_order_id in order_by_exchange_id_map:
                        # This is a fill for a tracked order
                        tracked_order = order_by_exchange_id_map[exchange_order_id]
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=trade["feeCoin"],
                            flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=trade["feeCoin"])]
                        )
                        fill_price = Decimal(trade["price"])
                        fill_base_amount = Decimal(trade["qty"])
                        fill_quote_amount = fill_base_amount * fill_price
                        trade_update = TradeUpdate(
                            trade_id=str(trade["id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fee=fee,
                            fill_base_amount=fill_base_amount,
                            fill_quote_amount=fill_quote_amount,
                            fill_price=fill_price,
                            fill_timestamp=trade["time"] * 1e-3,
                        )
                        self._order_tracker.process_trade_update(trade_update)
                    elif self.is_confirmed_new_order_filled_event(str(trade["id"]), exchange_order_id, trading_pair):
                        # This is a fill of an order registered in the DB but not tracked any more
                        self._current_trade_fills.add(TradeFillOrderDetails(
                            market=self.display_name,
                            exchange_trade_id=str(trade["id"]),
                            symbol=trading_pair))
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                timestamp=float(trade["time"]) * 1e-3,
                                order_id=self._exchange_order_ids.get(str(trade["orderId"]), None),
                                trading_pair=trading_pair,
                                trade_type=TradeType.BUY if trade["isBuyer"] else TradeType.SELL,
                                order_type=OrderType.LIMIT_MAKER if trade["isMaker"] else OrderType.LIMIT,
                                price=Decimal(trade["price"]),
                                amount=Decimal(trade["qty"]),
                                trade_fee=AddedToCostTradeFee(
                                    flat_fees=[
                                        TokenAmount(
                                            trade["feeCoin"],
                                            Decimal(trade["fee"])
                                        )
                                    ]
                                ),
                                exchange_trade_id=str(trade["id"])
                            ))
                        self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _update_order_status(self):
        # This is intended to be a backup measure to close straggler orders, as Scallop's user stream events
        # are not available.
        # The minimum poll interval for order status is 10 seconds.
        last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL

        tracked_orders: List[InFlightOrder] = list(self.in_flight_orders.values())
        if current_tick > last_tick and len(tracked_orders) > 0:

            tasks = [self._api_get(
                path_url=CONSTANTS.ORDER_PATH_URL,
                params={
                    "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=o.trading_pair),
                    "newClientOrderId": o.client_order_id},
                is_auth_required=True) for o in tracked_orders]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id

                # If the order has already been canceled or has failed do nothing
                if client_order_id not in self.in_flight_orders:
                    continue

                if isinstance(order_update, Exception):
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: {order_update}.",
                        app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                    )
                    await self._order_tracker.process_order_not_found(client_order_id)

                else:
                    # Update order execution status
                    new_state = CONSTANTS.ORDER_STATE[order_update["status"]]

                    update = OrderUpdate(
                        client_order_id=client_order_id,
                        exchange_order_id=str(order_update["orderId"]),
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=order_update["transactTime"] * 1e-3,
                        new_state=new_state,
                    )
                    self._order_tracker.process_order_update(update)

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_PATH_URL,
            is_auth_required=True)

        balances = account_info["balances"]
        for balance_entry in balances:
            asset_name = balance_entry["asset"]
            free_balance = Decimal(balance_entry["free"])
            total_balance = Decimal(balance_entry["free"]) + Decimal(balance_entry["locked"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]
        self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self.in_flight_orders.items()}
        self._in_flight_orders_snapshot_timestamp = self.current_timestamp

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(scallop_utils.is_exchange_information_valid, exchange_info["symbols"]):
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=symbol_data["baseAsset"],
                                                                        quote=symbol_data["quoteAsset"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PATH_URL,
            params=params
        )

        return float(resp_json["last"])
