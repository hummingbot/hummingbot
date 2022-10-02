import asyncio
import math
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.coinhub import (
    coinhub_constants as CONSTANTS,
    coinhub_utils,
    coinhub_web_utils as web_utils,
)
from hummingbot.connector.exchange.coinhub.coinhub_api_order_book_data_source import CoinhubAPIOrderBookDataSource
from hummingbot.connector.exchange.coinhub.coinhub_api_user_stream_data_source import CoinhubAPIUserStreamDataSource
from hummingbot.connector.exchange.coinhub.coinhub_auth import CoinhubAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None


class CoinhubExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        coinhub_api_key: str,
        coinhub_api_secret: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        self.api_key = coinhub_api_key
        self.secret_key = coinhub_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_coinhub_timestamp = 1.0
        super().__init__(client_config_map)

    @staticmethod
    def coinhub_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(binance_type: str) -> OrderType:
        return OrderType[binance_type]

    @property
    def authenticator(self):
        return CoinhubAuth(api_key=self.api_key, secret_key=self.secret_key)

    @property
    def name(self) -> str:
        return "coinhub"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.MARKET_LIST_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.MARKET_LIST_PATH_URL

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
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        # FTX API does not include an endpoint to get the server time, thus the TimeSynchronizer is not used
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CoinhubAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return CoinhubAPIUserStreamDataSource(
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
    ) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs
    ) -> Tuple[str, float]:
        order_result = None
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        side = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {
            "amount": amount_str,
            "market": symbol,
            **({'price': price_str} if order_type == OrderType.LIMIT or order_type == OrderType.LIMIT_MAKER is not None else {}),
            "side": side
        }
        self.logger().info(f"Api Params: {api_params}")
        order_resp = await self._api_post(path_url=CONSTANTS.CREATE_ORDER_PATH_URL, data=api_params, is_auth_required=True)
        self.logger().info(f"Api Resp: {order_resp}")
        order_result = order_resp["data"]
        exchange_order_id = str(order_result["id"])
        return (exchange_order_id, self.current_timestamp)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        if not tracked_order.exchange_order_id:
            return True
        api_params = {
            "market": symbol,
            "order_id": tracked_order.exchange_order_id
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.ORDER_CANCEL_PATH_URL, data=api_params, is_auth_required=True
        )
        if not cancel_result.get("data", False) and not cancel_result.get("code", False):
            self.logger().warning(
                f"Failed to cancel order {order_id} ({cancel_result})")

        self.logger().info(f"Cancel request response: {cancel_result}")

        return (cancel_result["data"] is not None and cancel_result["data"]["status"] == "done") or cancel_result.get("code", False) == 10

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "code": 200,
            "message": "success",
            "data": [
                {
                    "market": "CHB/MNT",
                    "money": "MNT",
                    "stock": "CHB",
                    "moneyPrec": 4,
                    "stockPrec": 4,
                    "feePrec": 4,
                    "minAmount": 1,
                    "type": 1,
                    "canTrade": true
                },
                {
                    "market": "WPL/MNT",
                    "money": "MNT",
                    "stock": "WPL",
                    "moneyPrec": 5,
                    "stockPrec": 1,
                    "feePrec": 4,
                    "minAmount": 500,
                    "type": 1,
                    "canTrade": true
                }
            ]
        }
        """
        trading_pair_rules = exchange_info_dict.get("data", [])
        retval = []
        for rule in filter(coinhub_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("market"))
                min_order_size = Decimal(f"{rule.get('minAmount')}")

                price_step = Decimal("1") / Decimal(str(math.pow(10, rule['moneyPrec'])))
                min_base_amount_increment = Decimal("1") / Decimal(str(math.pow(10, rule['stockPrec'])))
                min_notional_size = rule.get("minNotionalSize", price_step)
                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=price_step,
                        min_base_amount_increment=min_base_amount_increment,
                        min_notional_size=min_notional_size
                    )
                )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _status_polling_loop_fetch_updates(self):
        # await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

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
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("method")
                params = event_message.get("params")
                if event_type == "order.update":
                    # clean = params[0]
                    data = params[1]
                    tracked_order = self._order_tracker.fetch_order(exchange_order_id=str(data["id"]))
                    if tracked_order is not None:
                        new_state = CONSTANTS.ORDER_STATE[data["status"]]
                        fill_timestamp = data["mtime"]
                        if "ftime" in data:
                            fill_timestamp = data["ftime"]
                        if (new_state == OrderState.FILLED and Decimal(data["deal_stock"]) == Decimal(data["amount"])) or (new_state == OrderState.OPEN and Decimal(data["deal_stock"]) > Decimal("0.0")):
                            if new_state == OrderState.OPEN:
                                new_state = OrderState.PARTIALLY_FILLED
                            cumulative_filled_amount = Decimal(data["deal_stock"])
                            filled_amount = cumulative_filled_amount - tracked_order.executed_amount_base
                            cumulative_fee = Decimal(data["deal_fee"])
                            fee_token = tracked_order.quote_asset
                            if tracked_order.trade_type == TradeType.BUY:
                                fee_token = tracked_order.base_asset
                            fee_already_paid = tracked_order.cumulative_fee_paid(token=fee_token, exchange=self)
                            if cumulative_fee > fee_already_paid:
                                fee = TradeFeeBase.new_spot_fee(
                                    fee_schema=self.trade_fee_schema(),
                                    trade_type=tracked_order.trade_type,
                                    percent_token=fee_token,
                                    flat_fees=[TokenAmount(amount=cumulative_fee - fee_already_paid, token=fee_token)]
                                )
                            else:
                                fee = TradeFeeBase.new_spot_fee(
                                    fee_schema=self.trade_fee_schema(),
                                    trade_type=tracked_order.trade_type)

                            trade_update = TradeUpdate(
                                trade_id=str(data["mtime"]),
                                exchange_order_id=tracked_order.exchange_order_id,
                                client_order_id=tracked_order.client_order_id,
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=filled_amount,
                                fill_quote_amount=Decimal(data["deal_money"]) - tracked_order.executed_amount_quote,
                                fill_price=Decimal(data["price"]),
                                fill_timestamp=int(fill_timestamp) * 1e-3,
                            )
                            self._order_tracker.process_trade_update(trade_update)
                        elif new_state == OrderState.FILLED and Decimal(data["deal_stock"]) < Decimal(data["amount"]):
                            new_state = OrderState.CANCELED
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=int(fill_timestamp) * 1e-3,
                            new_state=new_state,
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=tracked_order.exchange_order_id,
                        )
                        self._order_tracker.process_order_update(order_update=order_update)
                elif event_type == "asset.update":
                    data = params[0]
                    for asset_name, balance_info in data.items():
                        free_balance = Decimal(balance_info["available"])
                        total_balance = free_balance + Decimal(balance_info["freeze"])
                        self._account_available_balances[asset_name] = free_balance
                        self._account_balances[asset_name] = total_balance
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _update_order_fills_from_trades(self):
        """
        This is intended to be a backup measure to get filled events with trade ID for orders,
        in case Binance's user stream events are not working.
        NOTE: It is not required to copy this functionality in other connectors.
        This is separated from _update_order_status which only updates the order status without producing filled
        events, since Binance's get order endpoint does not return trade IDs.
        The minimum poll interval for order status is 10 seconds.
        """
        small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

        if long_interval_current_tick > long_interval_last_tick or (
            self.in_flight_orders and small_interval_current_tick > small_interval_last_tick
        ):
            # query_time = int(self._last_trades_poll_coinhub_timestamp * 1e3)
            self._last_trades_poll_coinhub_timestamp = self._time_synchronizer.time()
            order_by_exchange_id_map = {}
            for order in self._order_tracker.all_orders.values():
                order_by_exchange_id_map[order.exchange_order_id] = order

            tasks = []
            trading_pairs = self.trading_pairs
            for trading_pair in trading_pairs:
                params = {
                    "limit": 100,
                    "market": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
                    "offset": 0
                }
                # if self._last_poll_timestamp > 0:
                #     params["startTime"] = query_time
                tasks.append(self._api_post(path_url=CONSTANTS.MY_TRADES_PATH_URL, data=params, is_auth_required=True))

            self.logger().debug(f"Polling for order fills of {len(tasks)} trading pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for trades, trading_pair in zip(results, trading_pairs):
                symbol = (await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair))
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}.",
                    )
                    continue
                for trade in trades["data"]["records"]:
                    exchange_order_id = str(trade["id"])
                    if exchange_order_id in order_by_exchange_id_map:
                        # This is a fill for a tracked order
                        tracked_order = order_by_exchange_id_map[exchange_order_id]
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=symbol.split("/")[0] if trade["side"] == 2 else symbol.split("/")[1],
                            flat_fees=[
                                TokenAmount(amount=Decimal(trade["deal_fee"]), token=symbol.split("/")[0] if trade["side"] == 2 else symbol.split("/")[1])
                            ],
                        )
                        trade_update = TradeUpdate(
                            trade_id=str(trade["id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(trade["deal_stock"]),
                            fill_quote_amount=Decimal(trade["deal_money"]),
                            fill_price=Decimal(trade["price"]),
                            fill_timestamp=trade["ftime"] * 1e-3,
                        )
                        self._order_tracker.process_trade_update(trade_update)
                    elif self.is_confirmed_new_order_filled_event(str(trade["id"]), exchange_order_id, trading_pair):
                        # This is a fill of an order registered in the DB but not tracked any more
                        self._current_trade_fills.add(
                            TradeFillOrderDetails(
                                market=self.display_name, exchange_trade_id=str(trade["id"]), symbol=trading_pair
                            )
                        )
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                timestamp=self.current_timestamp,
                                order_id=self._exchange_order_ids.get(str(trade["id"]), None),
                                trading_pair=trading_pair,
                                trade_type=TradeType.BUY if trade["side"] == 2 else TradeType.SELL,
                                order_type=OrderType.LIMIT,
                                price=Decimal(trade["price"]),
                                amount=Decimal(trade["deal_stock"]),
                                trade_fee=DeductedFromReturnsTradeFee(
                                    flat_fees=[TokenAmount(symbol.split("/")[0] if trade["side"] == 2 else symbol.split("/")[1], Decimal(trade["deal_fee"]))]
                                ),
                                exchange_trade_id=str(trade["id"]),
                            ),
                        )
                        self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        try:
            exchange_order_id = int(order.exchange_order_id)
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_post(
                path_url=CONSTANTS.ORDER_FILLS_URL,
                data={
                    "market": trading_pair,
                    "order_id": int(exchange_order_id)
                },
                is_auth_required=True,
                limit_id=CONSTANTS.ORDER_FILLS_URL)
            if not all_fills_response.get("data", False):
                self.logger().error("Unexpected error in all trades updates for order", exc_info=True)
                return []
            for trade_fill in all_fills_response["data"]["records"]:
                trade_update = self._create_trade_update_with_order_fill_data(order_fill_msg=trade_fill, order=order)
                trade_updates.append(trade_update)
        except asyncio.TimeoutError:
            raise IOError(f"Skipped order update with order fills for {order.client_order_id} "
                          "- waiting for exchange order id.")

        return trade_updates

    def _create_trade_update_with_order_fill_data(self, order_fill_msg: Dict[str, Any], order: InFlightOrder):
        #  {
        #     "deal_order_id": 50216,
        #     "amount": "0.001",
        #     "deal": "4000",
        #     "role": 1,
        #     "price": "4000000",
        #     "fee": "0.0000025",
        #     "id": 16941,
        #     "time": 1663897377.2463641,
        #     "user": 7
        # }

        estimated_fee_token = order.quote_asset
        if order.trade_type == TradeType.BUY:
            estimated_fee_token = order.base_asset
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,
            percent_token=estimated_fee_token,
            flat_fees=[TokenAmount(
                amount=Decimal(str(order_fill_msg["fee"])),
                token=estimated_fee_token
            )]
        )
        trade_update = TradeUpdate(
            trade_id=str(order_fill_msg["deal_order_id"]),
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=Decimal(str(order_fill_msg["amount"])),
            fill_quote_amount=Decimal(str(order_fill_msg["amount"])) * Decimal(str(order_fill_msg["price"])),
            fill_price=Decimal(str(order_fill_msg["price"])),
            fill_timestamp=order_fill_msg["time"],
        )
        return trade_update

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._api_post(
            path_url=CONSTANTS.GET_ORDER_PATH_URL,
            data={
                "market": await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair),
                "order_id": tracked_order.exchange_order_id,
            },
            is_auth_required=True
        )

        order_update = self._create_order_update_with_order_status_data(
            order_status_msg=updated_order_data["data"],
            order=tracked_order)

        return order_update

    def _create_order_update_with_order_status_data(self, order_status_msg: Dict[str, Any], order: InFlightOrder):
        # {
        #     "side": 2,
        #     "amount": "0.01",
        #     "deal_stock": "0",
        #     "taker_fee": "0.0025",
        #     "type": 1,
        #     "mtime": 1661487579.9604571,
        #     "client_id": "686042aac1c14927b39c",
        #     "market": "ETH/MNT",
        #     "left": "0.01",
        #     "price": "2200000.01",
        #     "maker_fee": "0.0025",
        #     "ctime": 1661487579.9604571,
        #     "id": 81,
        #     "deal_fee": "0",
        #     "user": 7,
        #     "deal_money": "0",
        #     "status": "opened"
        # }
        state = order.current_state
        new_state = CONSTANTS.ORDER_STATE[order_status_msg["status"]]
        if new_state == OrderState.OPEN and Decimal(order_status_msg["amount"]) != Decimal(order_status_msg["left"]):
            new_state = OrderState.PARTIALLY_FILLED
        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=state,
            client_order_id=order.client_order_id,
            exchange_order_id=str(order_status_msg["id"]),
        )
        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_post(path_url=CONSTANTS.ACCOUNTS_PATH_URL, data={}, is_auth_required=True)

        balances = account_info["data"]
        for asset_name, balance_entry in balances.items():
            free_balance = Decimal(balance_entry["available"])
            total_balance = Decimal(balance_entry["available"]) + Decimal(balance_entry["freeze"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(coinhub_utils.is_exchange_information_valid, exchange_info.get("data", [])):
            mapping[symbol_data["market"]] = combine_to_hb_trading_pair(
                base=symbol_data["stock"], quote=symbol_data["money"]
            )
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        # params = {"symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)}

        resp_json = await self._api_request(
            method=RESTMethod.GET, path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
        )
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        return float(resp_json["data"][symbol]["close"])
