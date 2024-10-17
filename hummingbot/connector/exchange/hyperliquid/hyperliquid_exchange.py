import asyncio
import hashlib
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.hyperliquid import (
    hyperliquid_constants as CONSTANTS,
    hyperliquid_web_utils as web_utils,
)
from hummingbot.connector.exchange.hyperliquid.hyperliquid_api_order_book_data_source import (
    HyperliquidAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.hyperliquid.hyperliquid_api_user_stream_data_source import (
    HyperliquidUserStreamDataSource,
)
from hummingbot.connector.exchange.hyperliquid.hyperliquid_auth import HyperliquidAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

bpm_logger = None


class HyperliquidExchange(ExchangePyBase):
    web_utils = web_utils

    SHORT_POLL_INTERVL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        hyperliquid_api_secret: str = None,
        use_vault: bool = False,
        hyperliquid_api_key: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
        throttler: Optional[AsyncThrottler] = None,
    ):
        self.hyperliquid_api_key = hyperliquid_api_key
        self.hyperliquid_secret_key = hyperliquid_api_secret
        self._use_vault = use_vault
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        self.coin_to_asset: Dict[str, int] = {}
        self._throttler = throttler
        self.rest_assistant = RESTAssistant(
            connection=RESTConnection(domain),
            throttler=self._throttler,
            auth=self.authenticator,
        )
        super().__init__(client_config_map)


    @property
    def name(self) -> str:
        return self._domain
    
    @property
    def authenticator(self) -> HyperliquidAuth:
        return HyperliquidAuth(self.hyperliquid_api_key, self.hyperliquid_secret_key,
                                        self._use_vault)
    
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
    
    async def _make_network_check_request(self):
        await self._api_post(path_url=self.check_network_request_path, data={"type": CONSTANTS.META_INFO})

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]
    
    def supported_position_modes(self):
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
        exchange_info = await self._api_post(path_url=self.trading_rules_request_path,
                                             data={"type": CONSTANTS.ASSET_CONTEXT_TYPE})
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_post(path_url=self.trading_pairs_request_path,
                                             data={"type": CONSTANTS.ASSET_CONTEXT_TYPE})
        return exchange_info

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)
    
    async def _update_trading_rules(self):
        exchange_info = await self._api_post(path_url=self.trading_rules_request_path,
                                            data={"type": CONSTANTS.ASSET_CONTEXT_TYPE})
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _initialize_trading_pair_symbol_map(self):
        try:
            exchange_info = await self._api_post(path_url=self.trading_pairs_request_path,
                                                data={"type": CONSTANTS.ASSET_CONTEXT_TYPE})
            
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return HyperliquidAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return HyperliquidUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _update_order_status(self):
        await self._update_orders()

    async def _update_lost_orders_status(self):
        await self._update_lost_orders()

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 position_action: PositionAction,
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
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        coin = ex_trading_pair.split("-")[0]

        api_params = {
            "type": "cancel",
            "cancels": {
                "asset": self.coin_to_asset[coin],
                "cloid": order_id
            },
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=api_params,
            is_auth_required=True)

        if cancel_result.get("status") == "err" or "error" in cancel_result["response"]["data"]["statuses"][0]:
            self.logger().debug(f"The order {order_id} does not exist on Hyperliquid. "
                                f"No cancelation needed.")
            await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f'{cancel_result["response"]["data"]["statuses"][0]["error"]}')
        if "success" in cancel_result["response"]["data"]["statuses"][0]:
            return True
        return False
    
    # === Orders placing ===
    
    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.LIMIT,
            price: Decimal = s_decimal_NaN,
            **kwargs) -> str:
        """
        Creates a promise to create a buy order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode('utf-8'))
        hex_order_id = f"0x{md5.hexdigest()}"
        if order_type is OrderType.MARKET:
            mid_price = self.get_mid_price(trading_pair)
            slippage = CONSTANTS.MARKET_ORDER_SLIPPAGE
            market_price = mid_price * Decimal(1 + slippage)
            price = self.quantize_order_price(trading_pair, market_price)

        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

    def sell(self,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType = OrderType.LIMIT,
             price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode('utf-8'))
        hex_order_id = f"0x{md5.hexdigest()}"
        if order_type is OrderType.MARKET:
            mid_price = self.get_mid_price(trading_pair)
            slippage = CONSTANTS.MARKET_ORDER_SLIPPAGE
            market_price = mid_price * Decimal(1 - slippage)
            price = self.quantize_order_price(trading_pair, market_price)

        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id
    
    async def _place_order(self, order_id: str, trading_pair: str, amount: Decimal, trade_type: TradeType, 
                       order_type: OrderType, price: Decimal, position_action: PositionAction = PositionAction.NIL, 
                       **kwargs):
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        coin = ex_trading_pair.split("-")[0]

        param_order_type = {"limit": {"tif": "Gtc"}}
        if order_type is OrderType.LIMIT_MAKER:
            param_order_type = {"limit": {"tif": "Alo"}}
        if order_type is OrderType.MARKET:
            param_order_type = {"limit": {"tif": "Ioc"}}

        api_params = {
            "type": "order",
            "grouping": "na",
            "orders": {
                "asset": self.coin_to_asset[coin],
                "isBuy": True if trade_type is TradeType.BUY else False,
                "limitPx": float(price),
                "sz": float(amount),
                "reduceOnly": False,
                "orderType": param_order_type,
                "cloid": order_id,
            }
        }
        order_result = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_URL,
            data=api_params,
            is_auth_required=True)
        if order_result.get("status") == "err":
            raise IOError(f"Error submitting order {order_id}: {order_result['response']}")
        else:
            o_order_result = order_result['response']["data"]["statuses"][0]
        if "error" in o_order_result:
            raise IOError(f"Error submitting order {order_id}: {o_order_result['error']}")
        o_data = o_order_result.get("resting") or o_order_result.get("filled")
        o_id = str(o_data["oid"])
        return (o_id, self.current_timestamp)
    
    async def _update_trade_history(self):
        orders = list(self._order_tracker.all_fillable_orders.values())
        all_fillable_orders = self._order_tracker.all_fillable_orders_by_exchange_order_id
        all_fills_response = []
        if len(orders) > 0:
            try:
                all_fills_response = await self._api_post(
                    path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                    data={
                        "type": CONSTANTS.TRADES_TYPE,
                        "user": self.hyperliquid_api_key,
                    })
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                self.logger().warning(
                    f"Failed to fetch trade updates. Error: {request_error}",
                    exc_info=request_error,
                )
            for trade_fill in all_fills_response:
                self._process_trade_rs_event_message(order_fill=trade_fill, all_fillable_order=all_fillable_orders)

    def _process_trade_rs_event_message(self, order_fill: Dict[str, Any], all_fillable_order):
        exchange_order_id = str(order_fill.get("oid"))
        fillable_order = all_fillable_order.get(exchange_order_id)
        if fillable_order is not None:
            fee_asset = fillable_order.quote_asset

            position_action = PositionAction.OPEN if order_fill["dir"].split(" ")[0] == "Open" else PositionAction.CLOSE
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=Decimal(order_fill["fee"]), token=fee_asset)]
            )

            trade_update = TradeUpdate(
                trade_id=str(order_fill["tid"]),
                client_order_id=fillable_order.client_order_id,
                exchange_order_id=str(order_fill["oid"]),
                trading_pair=fillable_order.trading_pair,
                fee=fee,
                fill_base_amount=Decimal(order_fill["sz"]),
                fill_quote_amount=Decimal(order_fill["px"]) * Decimal(order_fill["sz"]),
                fill_price=Decimal(order_fill["px"]),
                fill_timestamp=order_fill["time"] * 1e-3,
            )

            self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # Use _update_trade_history instead
        pass

    async def _handle_update_error_for_active_order(self, order: InFlightOrder, error: Exception):
        try:
            raise error
        except (asyncio.TimeoutError, KeyError):
            self.logger().debug(
                f"Tracked order {order.client_order_id} does not have an exchange id. "
                f"Attempting fetch in next polling interval."
            )
            await self._order_tracker.process_order_not_found(order.client_order_id)
        except asyncio.CancelledError:
            raise
        except Exception as request_error:
            self.logger().warning(
                f"Error fetching status update for the active order {order.client_order_id}: {request_error}.",
            )
            self.logger().debug(
                f"Order {order.client_order_id} not found counter: {self._order_tracker._order_not_found_records.get(order.client_order_id, 0)}")
            await self._order_tracker.process_order_not_found(order.client_order_id)

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        client_order_id = tracked_order.client_order_id
        order_update = await self._api_post(
            path_url=CONSTANTS.ORDER_URL,
            data={
                "type": CONSTANTS.ORDER_STATUS_TYPE,
                "user": self.hyperliquid_api_key,
                "oid": int(tracked_order.exchange_order_id) if tracked_order.exchange_order_id else client_order_id
            })
        current_state = order_update["order"]["status"]
        _order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_update["order"]["order"]["timestamp"] * 1e-3,
            new_state=CONSTANTS.ORDER_STATE[current_state],
            client_order_id=order_update["order"]["order"]["cloid"] or client_order_id,
            exchange_order_id=str(tracked_order.exchange_order_id),
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
                    app_warning_msg="Could not fetch user events from Hyperliquid. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        user_channels = [
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            CONSTANTS.USEREVENT_ENDPOINT_NAME,
        ]
        async for event_message in self._iter_user_event_queue():
            try:
                if isinstance(event_message, dict):
                    channel: str = event_message.get("channel", None)
                    results = event_message.get("data", None)
                elif event_message is asyncio.CancelledError:
                    raise asyncio.CancelledError
                else:
                    raise Exception(event_message)
                if channel not in user_channels:
                    self.logger().error(
                        f"Unexpected message in user stream: {event_message}.", exc_info=True)
                    continue
                if channel == CONSTANTS.USER_ORDERS_ENDPOINT_NAME:
                    for order_msg in results:
                        self._process_order_message(order_msg)
                elif channel == CONSTANTS.USEREVENT_ENDPOINT_NAME:
                    if "fills" in results:
                        for trade_msg in results["fills"]:
                            await self._process_trade_message(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _process_trade_message(self, trade: Dict[str, Any], client_order_id: Optional[str] = None):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        Example Trade:
        """
        exchange_order_id = str(trade.get("oid", ""))
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

        if tracked_order is None:
            all_orders = self._order_tracker.all_fillable_orders
            for k, v in all_orders.items():
                await v.get_exchange_order_id()
            _cli_tracked_orders = [o for o in all_orders.values() if exchange_order_id == o.exchange_order_id]
            if not _cli_tracked_orders:
                self.logger().debug(f"Ignoring trade message with id {client_order_id}: not in in_flight_orders.")
                return
            tracked_order = _cli_tracked_orders[0]
        trading_pair_base_coin = tracked_order.base_asset
        if trade["coin"] == trading_pair_base_coin:
            position_action = PositionAction.OPEN if trade["dir"].split(" ")[0] == "Open" else PositionAction.CLOSE
            fee_asset = tracked_order.quote_asset
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=fee_asset)]
            )
            trade_update: TradeUpdate = TradeUpdate(
                trade_id=str(trade["tid"]),
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(trade["oid"]),
                trading_pair=tracked_order.trading_pair,
                fill_timestamp=trade["time"] * 1e-3,
                fill_price=Decimal(trade["px"]),
                fill_base_amount=Decimal(trade["sz"]),
                fill_quote_amount=Decimal(trade["px"]) * Decimal(trade["sz"]),
                fee=fee,
            )
            self._order_tracker.process_trade_update(trade_update)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancelation or failure event if needed.

        :param order_msg: The order response from either REST or web socket API (they are of the same format)

        Example Order:
        """
        client_order_id = str(order_msg["order"].get("cloid", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return
        current_state = order_msg["status"]
        order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_msg["statusTimestamp"] * 1e-3,
            new_state=CONSTANTS.ORDER_STATE[current_state],
            client_order_id=order_msg["order"]["cloid"],
            exchange_order_id=str(order_msg["order"]["oid"]),
        )
        self._order_tracker.process_order_update(order_update=order_update)

    async def _format_trading_rules(self, exchange_info_dict: List) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        Parameters
        ----------
        exchange_info_dict:
            Trading rules dictionary response from the exchange
        """
        # rules: list = exchange_info_dict[0]
        self.coin_to_asset = {asset_info["name"]: asset for (asset, asset_info) in enumerate(exchange_info_dict[0]["universe"])}

        coin_infos: list = exchange_info_dict[0]["universe"]
        token_infos: list = exchange_info_dict[0]["tokens"]
        price_infos: list = exchange_info_dict[1]
        return_val: list = []

        for coin_info, price_info in zip(coin_infos, price_infos):
            try:
                base_token_index = coin_info["tokens"][0]
                quote_token_index = coin_info["tokens"][1]

                # base_token_name = token_infos[base_token_index]["name"]
                quote_token_name = token_infos[quote_token_index]["name"]

                trading_pair = f"@{base_token_index}-@{quote_token_index}"

                step_size = Decimal(str(10 ** -token_infos[base_token_index].get("szDecimals")))
                price_size = Decimal(str(10 ** -len(price_info.get("markPx").split('.')[1])))
                collateral_token = quote_token_name

                return_val.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_base_amount_increment=step_size,
                        min_price_increment=price_size,
                        buy_order_collateral_token=collateral_token,
                        sell_order_collateral_token=collateral_token,
                    )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {coin_info}. Skipping.", exc_info=True)

        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List):
        mapping = bidict()
        tokens = exchange_info[0]["tokens"]
        universe = exchange_info[0]["universe"]

        for coin_info in universe:
            base_token_index = coin_info["tokens"][0]
            quote_token_index = coin_info["tokens"][1]

            base_token_name = tokens[base_token_index]["name"]
            quote_token_name = tokens[quote_token_index]["name"]

            trading_pair = f"@{base_token_index}-@{quote_token_index}"
            ex_symbol = f"{base_token_name}_{base_token_index}-{quote_token_name}_{quote_token_index}"

            mapping[trading_pair] = ex_symbol
            self.logger().debug(f"Mapped {trading_pair} to {ex_symbol}")

        self._set_trading_pair_symbol_map(mapping)
    
    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        coin = f"@{exchange_symbol.split('_')[1].split('-')[0]}"
        response = await self._api_post(path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL,
                                        data={"type": CONSTANTS.ASSET_CONTEXT_TYPE})
        price = 0
        for index, i in enumerate(response[0]['universe']):
            if i['name'] == coin:
                price = float(response[1][index]['markPx'])
        return price
    
    async def _update_balances(self):
        account_info = await self._api_post(
            path_url=CONSTANTS.ACCOUNT_INFO_URL,
            data={"type": CONSTANTS.USER_STATE_TYPE,
                  "user": self.hyperliquid_api_key},
        )

        self._account_balances.clear()
        self._account_available_balances.clear()

        for token_info in account_info["balances"]:
            coin_name = token_info["coin"]
            total_balance = Decimal(token_info["total"])
            hold_balance = Decimal(token_info["hold"])
            
            self._account_balances[coin_name] = total_balance
            self._account_available_balances[coin_name] = total_balance - hold_balance

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        coin = f"@{trading_pair.split('-')[0].split('_')[1]}-@{trading_pair.split('-')[1].split('_')[1]}"
        trading_rule = self._trading_rules[coin]
        return trading_rule.min_price_increment