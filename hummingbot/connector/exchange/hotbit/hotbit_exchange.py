import asyncio
import json
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.hotbit import (
    hotbit_constants as CONSTANTS,
    hotbit_utils,
    hotbit_web_utils as web_utils,
)
from hummingbot.connector.exchange.hotbit.hotbit_api_order_book_data_source import HotbitAPIOrderBookDataSource
from hummingbot.connector.exchange.hotbit.hotbit_api_user_stream_data_source import HotbitAPIUserStreamDataSource
from hummingbot.connector.exchange.hotbit.hotbit_auth import HotbitAuth
from hummingbot.connector.exchange.hotbit.hotbit_order_book_tracker import HotbitOrderBookTracker
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None


class HotbitExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 hotbit_api_key: str,
                 hotbit_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = hotbit_api_key
        self.secret_key = hotbit_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_hotbit_timestamp = 1.0
        super().__init__(client_config_map)
        self._set_order_book_tracker(HotbitOrderBookTracker(
            trading_pairs=self._trading_pairs, connector=self, api_factory=self._web_assistants_factory))

    @staticmethod
    def hotbit_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(hotbit_type: str) -> OrderType:
        return OrderType[hotbit_type]

    @property
    def authenticator(self):
        return HotbitAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "hotbit"

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
        return CONSTANTS.ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.CHECK_NETWORK_PATH_URL

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

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
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
            time_synchronizer=self._time_synchronizer,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return HotbitAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return HotbitAPIUserStreamDataSource(
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
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        self.logger().debug(f"_place_order order_id:{order_id}")
        order_result = None
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        side = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {"market": symbol,
                      "side": str(side),
                      "amount": amount_str,
                      "price": price_str,
                      "isfee": "0"}

        order_result_all = await self._api_post(
            path_url=CONSTANTS.ORDER_LIMIT_PATH_URL,
            data=api_params,
            is_auth_required=True)
        self.logger().debug(f"_place_order order_id:{order_id} res {order_result_all}")
        self.check_response(order_result_all, "_place_order")

        order_result = order_result_all["result"]
        o_id = str(order_result["id"])
        transact_time = order_result["ctime"]
        return (o_id, transact_time)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        self.logger().debug(f"_place_cancel order_id:{order_id} exchange_order_id:{tracked_order.exchange_order_id}")
        if tracked_order.exchange_order_id is None:
            await self._sleep(1)
            tracked_order = self._order_tracker.fetch_tracked_order(order_id)
            if tracked_order is None or tracked_order.exchange_order_id is None:
                raise asyncio.TimeoutError
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "market": symbol,
            "order_id": tracked_order.exchange_order_id,
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.ORDER_CANCEL_PATH_URL,
            data=api_params,
            is_auth_required=True)
        self.logger().debug(f"_place_cancel res {cancel_result}")
        if cancel_result["error"] is None:
            return True
        return False

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        order.update status code:
            1: new order or (new order and filled immediately)
            2: order partially filled, but not include complete filled
            3: order complete filled or canceled (canceled if [deal_stock] is zero)
            deal_stock is cumulative value
        """
        async for stream_message in self._iter_user_event_queue():
            try:
                channel = stream_message.get("method")
                self.logger().debug(f"_user_stream_event_listener {stream_message}")
                if channel == CONSTANTS.ORDER_EVENT_TYPE:
                    order_type = stream_message.get("params")[0]
                    data = stream_message.get("params")[1]
                    exchange_id = str(data['id'])
                    updatable_order = self.find_updatable_order(exchange_id)
                    fillable_order = self.find_fillable_order(exchange_id)

                    order_state = OrderState.OPEN
                    update_timestamp = int(data["mtime"])
                    has_fill = False

                    if order_type == CONSTANTS.ORDER_STATE_CREATED:
                        if not self.is_zero(data["deal_stock"]):
                            order_state = OrderState.PARTIALLY_FILLED
                            has_fill = True
                        else:
                            order_state = OrderState.OPEN
                    elif order_type == CONSTANTS.ORDER_STATE_UPDATED:
                        order_state = OrderState.PARTIALLY_FILLED
                        has_fill = True
                    elif order_type == CONSTANTS.ORDER_STATE_FINISHED:
                        if Decimal(data["deal_stock"]) == Decimal(data["amount"]):
                            order_state = OrderState.FILLED
                            has_fill = True
                        else:
                            order_state = OrderState.CANCELED

                    if fillable_order is not None and has_fill:
                        trade_update = self.create_trade_update(fillable_order, data)
                        if trade_update is not None:
                            self._order_tracker.process_trade_update(trade_update)

                    if updatable_order is not None:
                        order_update = OrderUpdate(
                            trading_pair=updatable_order.trading_pair,
                            update_timestamp=update_timestamp,
                            new_state=order_state,
                            client_order_id=updatable_order.client_order_id,
                            exchange_order_id=updatable_order.exchange_order_id,
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif channel == CONSTANTS.ASSET_EVENT_TYPE:
                    assets = stream_message.get("params")
                    for asset in assets:
                        for asset_name in asset:
                            asset_balance = asset[asset_name]
                            free_balance = Decimal(asset_balance["available"])
                            total_balance = Decimal(asset_balance["available"]) + Decimal(asset_balance["freeze"])
                            self._account_available_balances[asset_name] = free_balance
                            self._account_balances[asset_name] = total_balance
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    def find_updatable_order(self, exchange_order_id: str):
        for o in self._order_tracker.all_updatable_orders.values():
            if o.exchange_order_id == exchange_order_id:
                return o

    def find_fillable_order(self, exchange_order_id: str):
        for o in self._order_tracker.all_fillable_orders.values():
            if o.exchange_order_id == exchange_order_id:
                return o

    def create_trade_update(self, fillable_order: InFlightOrder, update_data: Any) -> TradeUpdate:
        order_fills = fillable_order.order_fills
        executed_fee = Decimal(0)
        for order_fill in order_fills.values():
            for flat_fee in order_fill.fee.flat_fees:
                executed_fee += flat_fee.amount

        current_fee = Decimal(update_data["deal_fee"]) - executed_fee
        base, quote = split_hb_trading_pair(fillable_order.trading_pair)
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=fillable_order.trade_type,
            percent_token=quote,
            flat_fees=[TokenAmount(amount=Decimal(current_fee), token=quote)]
        )

        current_deal_stock = Decimal(update_data["deal_stock"]) - fillable_order.executed_amount_base
        current_deal_money = Decimal(update_data["deal_money"]) - fillable_order.executed_amount_quote
        trade_id = str(fillable_order.exchange_order_id) + "_" + str(len(fillable_order.order_fills.values()) + 1)
        self.logger().info(f"create_trade_update fill order_id:{fillable_order.client_order_id}, trade_id:{trade_id}, \
            current_deal_stock:{current_deal_stock}, current_deal_stock:{current_deal_money}, current_fee:{current_fee}")
        if current_deal_stock.is_zero():
            return None
        return TradeUpdate(
            trade_id=trade_id,
            client_order_id=fillable_order.client_order_id,
            exchange_order_id=fillable_order.exchange_order_id,
            trading_pair=fillable_order.trading_pair,
            fee=fee,
            fill_base_amount=current_deal_stock,
            fill_quote_amount=current_deal_money,
            fill_price=Decimal(update_data["price"]),
            fill_timestamp=int(update_data["mtime"]),
        )

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        There are some problems with the interface of hotbot about fetching order detail.
        pass
        """
        self.logger().debug("_all_trade_updates_for_order")
        trade_updates = []
        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        self.logger().debug(f"_request_order_status client_order_id:{tracked_order.client_order_id} exchange_order_id:{tracked_order.exchange_order_id}")
        if not tracked_order.exchange_order_id:
            await self._sleep(1)
            tracked_order = self._order_tracker.fetch_tracked_order(tracked_order.client_order_id)
            if tracked_order is None or tracked_order.exchange_order_id is None:
                raise asyncio.TimeoutError

        """ pending state: OPEN / PARTIALLY_FILLED, PARTIALLY_FILLED if data["deal_stock"] is not zero """
        pending_orders = {}
        pending_offset = 0
        pending_limit = 100
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        while True:
            params = {
                "market": trading_pair,
                "offset": str(pending_offset),
                "limit": str(pending_limit)}
            pending_order_data = await self._api_post(
                path_url=CONSTANTS.PENDING_ORDER_PATH_URL,
                data=params,
                is_auth_required=True,
                limit_id=CONSTANTS.PENDING_ORDER_PATH_URL)
            self.logger().debug(f"_request_order_status {CONSTANTS.PENDING_ORDER_PATH_URL} res {pending_order_data}")
            self.check_response(pending_order_data, "_request_order_status")

            pending_records = pending_order_data["result"][trading_pair]["records"] if trading_pair in pending_order_data["result"] else []
            for pending_order in pending_records:
                pending_orders[str(pending_order["id"])] = pending_order
            if len(pending_records) < pending_limit:
                break
            pending_offset += 1

        pending_order = pending_orders.get(tracked_order.exchange_order_id)
        if pending_order is not None:
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=int(pending_order["mtime"]),
                new_state=OrderState.OPEN if self.is_zero(pending_order["deal_stock"]) else OrderState.PARTIALLY_FILLED
            )
            return order_update

        """ finish state: FILLED / CANCELED(PARTIALLY_FILLED then cancel), CANCELED if data["status"] == 8 """
        params = {
            "offset": "0",
            "order_id": tracked_order.exchange_order_id}
        finished_response = await self._api_post(
            path_url=CONSTANTS.MY_TRADES_PATH_URL,
            data=params,
            is_auth_required=True,
            limit_id=CONSTANTS.MY_TRADES_PATH_URL)
        self.logger().debug(f"_request_order_status {CONSTANTS.MY_TRADES_PATH_URL} res {finished_response}")
        self.check_response(finished_response, "_request_order_status")

        finished_orders = finished_response["result"]["records"] if "records" in finished_response["result"] else []
        if len(finished_orders) > 0:
            finished_order = finished_orders[0]
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=int(finished_order["finish_time"]),
                new_state=CONSTANTS.FINISHED_STATE[finished_order["status"]],
            )
            return order_update

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.CANCELED,
        )
        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_post(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            data={
                "assets": json.dumps([])
            },
            is_auth_required=True)
        self.logger().debug(f"_update_balances res {account_info}")
        self.check_response(account_info, "_update_balances")

        balances = account_info["result"]
        for asset_name in balances:
            asset = balances[asset_name]
            free_balance = Decimal(asset["available"])
            total_balance = Decimal(asset["available"]) + Decimal(asset["freeze"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "market": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "period": 86400
        }

        resp_json = (await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            params=params
        ))["result"]

        return float(resp_json["last"])

    async def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        trading_rules = []

        for info in raw_trading_pair_info["result"]:
            try:
                trading_rules.append(
                    TradingRule(
                        trading_pair=await self.trading_pair_associated_to_exchange_symbol(symbol=info["name"]),
                        min_order_size=Decimal(info["min_amount"]),
                        min_price_increment=Decimal(10).__pow__(Decimal(-1).__mul__(info["money_prec"])),
                        # min_base_amount_increment=Decimal(10).__pow__(Decimal(-1).__mul__(info["stock_prec"])),
                        min_base_amount_increment=Decimal(info["min_amount"])
                    )
                )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {info}. Skipping.")
        return trading_rules

    async def _initialize_trading_pair_symbol_map(self):
        # This has to be reimplemented because the request requires an extra parameter
        try:
            exchange_info = await self._api_get(
                path_url=self.trading_pairs_request_path
            )
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(hotbit_utils.is_exchange_information_valid, exchange_info["result"]):
            mapping[symbol_data["name"]] = combine_to_hb_trading_pair(base=symbol_data["stock"], quote=symbol_data["money"])
        self._set_trading_pair_symbol_map(mapping)

    def is_zero(self, num: str):
        return num is None or num == "" or Decimal(num).is_zero()

    def check_response(self, res: Any, type: str):
        if "error" in res and res["error"] is not None:
            errorMsg = ""
            if "message" in res["error"] and res["error"]["message"] is not None:
                errorMsg = res["error"]["message"]
            elif "message" in res and res["message"] is not None:
                errorMsg = res["message"]
            self.logger().error(f"{type} error {errorMsg}")
            raise RuntimeError(f"{type} error {errorMsg}")
