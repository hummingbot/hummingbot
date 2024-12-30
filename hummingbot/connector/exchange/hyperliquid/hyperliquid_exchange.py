import asyncio
import hashlib
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
    HyperliquidAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.hyperliquid.hyperliquid_auth import HyperliquidAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class HyperliquidExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
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
    ):
        self.hyperliquid_api_key = hyperliquid_api_key
        self.hyperliquid_secret_key = hyperliquid_api_secret
        self._use_vault = use_vault
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._last_trade_history_timestamp = None
        self._last_trades_poll_timestamp = 1.0
        self.coin_to_asset: Dict[str, int] = {}
        self.name_to_coin: Dict[str, str] = {}
        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        # Note: domain here refers to the entire exchange name. i.e. hyperliquid_ or hyperliquid_testnet
        return self._domain

    @property
    def authenticator(self) -> Optional[HyperliquidAuth]:
        if self._trading_required:
            return HyperliquidAuth(self.hyperliquid_api_key, self.hyperliquid_secret_key,
                                   self._use_vault)
        return None

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
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        res = []
        response = await self._api_post(
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL,
            data={"type": CONSTANTS.ASSET_CONTEXT_TYPE})
        for token in response[1]:
            result = {}
            price = token['midPx']
            result["symbol"] = token['coin']
            result["price"] = price
            res.append(result)
        return res

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

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Applies trading rule to quantize order price.
        """
        d_price = Decimal(round(float(f"{price:.5g}"), 6))
        return d_price

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
        return HyperliquidAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_trade_history(),
            self._update_order_status(),
            self._update_balances(),
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
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "type": "cancel",
            "cancels": {
                "asset": self.coin_to_asset[symbol],
                "cloid": order_id
            },
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=api_params,
            is_auth_required=True)

        if cancel_result.get("status") == "err" or "error" in cancel_result["response"]["data"]["statuses"][0]:
            self.logger().debug(f"The order {order_id} does not exist on Hyperliquid s. "
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

        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        param_order_type = {"limit": {"tif": "Gtc"}}
        if order_type is OrderType.LIMIT_MAKER:
            param_order_type = {"limit": {"tif": "Alo"}}
        if order_type is OrderType.MARKET:
            param_order_type = {"limit": {"tif": "Ioc"}}

        api_params = {
            "type": "order",
            "grouping": "na",
            "orders": {
                "asset": self.coin_to_asset[symbol],
                "isBuy": True if trade_type is TradeType.BUY else False,
                "limitPx": float(price),
                "sz": float(amount),
                "reduceOnly": False,
                "orderType": param_order_type,
                "cloid": order_id,
            }
        }
        order_result = await self._api_post(
            path_url = CONSTANTS.CREATE_ORDER_URL,
            data = api_params,
            is_auth_required = True)
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
                    path_url = CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                    data = {
                        "type": CONSTANTS.TRADES_TYPE,
                        "user": self.hyperliquid_api_key,
                    })
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                self.logger().warning(
                    f"Failed to fetch trade updates. Error: {request_error}",
                    exc_info = request_error,
                )
            for trade_fill in all_fills_response:
                self._process_trade_rs_event_message(order_fill=trade_fill, all_fillable_order=all_fillable_orders)

    def _process_trade_rs_event_message(self, order_fill: Dict[str, Any], all_fillable_order):
        exchange_order_id = str(order_fill.get("oid"))
        fillable_order = all_fillable_order.get(exchange_order_id)
        if fillable_order is not None:
            fee_asset = order_fill["feeToken"]

            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                trade_type=fillable_order.trade_type,
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
            fee_asset = trade["feeToken"]
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                trade_type=tracked_order.trade_type,
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
        self.coin_to_asset = {}
        self.name_to_coin = {}

        self.coin_to_asset = {asset_info["name"]: asset for (asset, asset_info) in enumerate(exchange_info_dict[0]["universe"])}
        self.name_to_coin = {asset_info["name"]: asset_info["name"] for asset_info in exchange_info_dict[0]["universe"]}

        coin_infos: list = exchange_info_dict[0]["universe"]
        price_infos: list = exchange_info_dict[1]

        for spot_info in filter(web_utils.is_exchange_information_valid, exchange_info_dict[0]["universe"]):
            self.coin_to_asset[spot_info["name"]] = spot_info["index"] + 10000
            self.name_to_coin[spot_info["name"]] = spot_info["name"]

        return_val: list = []
        for coin_info, price_info in zip(coin_infos, price_infos):
            base, quote = coin_info["tokens"]
            try:
                ex_name = f'{exchange_info_dict[0]["tokens"][base]["name"].replace(" ", "").upper()}/{exchange_info_dict[0]["tokens"][quote]["name"].replace(" ", "").upper()}'
                if ex_name not in self.name_to_coin:
                    self.name_to_coin[ex_name] = coin_info["name"]

                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=coin_info["name"])
                step_size = Decimal(str(10 ** -exchange_info_dict[0]["tokens"][base].get("szDecimals")))
                price_size = Decimal(str(10 ** -len(price_info.get("markPx").split('.')[1])))
                return_val.append(
                    TradingRule(
                        trading_pair,
                        min_base_amount_increment=step_size,
                        min_price_increment=price_size
                    )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {exchange_info_dict}. Skipping.",
                                    exc_info=True)
        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List):
        mapping = bidict()
        self.coin_to_asset = {}
        self.name_to_coin = {}

        self.coin_to_asset = {asset_info["name"]: asset for (asset, asset_info) in enumerate(exchange_info[0]["universe"])}

        self.name_to_coin = {asset_info["name"]: asset_info["name"] for asset_info in exchange_info[0]["universe"]}

        for spot_info in filter(web_utils.is_exchange_information_valid, exchange_info[0]["universe"]):
            self.coin_to_asset[spot_info["name"]] = spot_info["index"] + 10000
            self.name_to_coin[spot_info["name"]] = spot_info["name"]
            base, quote = spot_info["tokens"]
            name = f'{exchange_info[0]["tokens"][base]["name"].replace(" ", "").upper()}/{exchange_info[0]["tokens"][quote]["name"].replace(" ", "").upper()}'
            ex_name = spot_info["name"]

            if name not in self.name_to_coin:
                self.name_to_coin[name] = spot_info["name"]

            new_base, new_quote = name.split("/")
            trading_pair = combine_to_hb_trading_pair(new_base, new_quote)
            if trading_pair in mapping.inverse:
                self._resolve_trading_pair_symbols_duplicate(mapping, name, new_base, new_quote)
            else:
                mapping[ex_name] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

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

        account_info = await self._api_post(path_url=CONSTANTS.ACCOUNT_INFO_URL,
                                            data={"type": CONSTANTS.USER_STATE_TYPE,
                                                  "user": self.hyperliquid_api_key},
                                            )
        balances = account_info["balances"]
        for balance_entry in balances:
            asset_name = balance_entry["coin"]
            free_balance = Decimal(balance_entry["total"]) - Decimal(balance_entry["hold"])
            total_balance = Decimal(balance_entry["total"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

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

    async def _update_order_fills_from_trades(self):
        """
        This is intended to be a backup measure to get filled events with trade ID for orders,
        in case hyperliquid's user stream events are not working.
        NOTE: It is not required to copy this functionality in other connectors.
        This is separated from _update_order_status which only updates the order status without producing filled
        events, since hyperliquid's get order endpoint does not return trade IDs.
        The minimum poll interval for order status is 10 seconds.
        """
        small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

        if (long_interval_current_tick > long_interval_last_tick
                or (self.in_flight_orders and small_interval_current_tick > small_interval_last_tick)):
            query_time = int(self._last_trades_poll_timestamp * 1e3)
            self._last_trades_poll_timestamp = self._time_synchronizer.time()
            order_by_exchange_id_map = {}
            for order in self._order_tracker.all_fillable_orders.values():
                order_by_exchange_id_map[order.exchange_order_id] = order

            tasks = []
            trading_pairs = self.trading_pairs
            for trading_pair in trading_pairs:
                params = {
                    'type': CONSTANTS.TRADES_TYPE,
                    'user': self.hyperliquid_api_key,
                }
                if self._last_poll_timestamp > 0:
                    params['type'] = 'userFillsByTime'
                    params["startTime"] = query_time
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
                    exchange_order_id = str(trade["oid"])
                    if exchange_order_id in order_by_exchange_id_map:
                        # This is a fill for a tracked order
                        tracked_order = order_by_exchange_id_map[exchange_order_id]
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=trade["feeToken"],
                            flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=trade["feeToken"])]
                        )
                        trade_update = TradeUpdate(
                            trade_id=str(trade["tid"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(trade["sz"]),
                            fill_quote_amount=Decimal(trade["sz"]) * Decimal(trade["px"]),
                            fill_price=Decimal(trade["px"]),
                            fill_timestamp=trade["time"] * 1e-3,
                        )
                        self._order_tracker.process_trade_update(trade_update)
                    elif self.is_confirmed_new_order_filled_event(str(trade["tid"]), exchange_order_id, trading_pair):
                        # This is a fill of an order registered in the DB but not tracked any more
                        self._current_trade_fills.add(TradeFillOrderDetails(
                            market=self.display_name,
                            exchange_trade_id=str(trade["tid"]),
                            symbol=trading_pair))
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                timestamp=float(trade["time"]) * 1e-3,
                                order_id=self._exchange_order_ids.get(str(trade["oid"]), None),
                                trading_pair=trading_pair,
                                trade_type=TradeType.BUY if trade["side"] == 'B' else TradeType.SELL,
                                order_type=OrderType.LIMIT_MAKER if "Open" in trade["dir"] else OrderType.LIMIT,
                                price=Decimal(trade["px"]),
                                amount=Decimal(trade["sz"]),
                                trade_fee=DeductedFromReturnsTradeFee(
                                    flat_fees=[
                                        TokenAmount(
                                            trade["feeToken"],
                                            Decimal(trade["fee"])
                                        )
                                    ]
                                ),
                                exchange_trade_id=str(trade["tid"])
                            ))
                        self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "type": "userFills",
                    'user': self.hyperliquid_api_key,
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_PATH_URL)

            for trade in all_fills_response:
                exchange_order_id = str(trade["orderId"])
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=trade["feeToken"],
                    flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=trade["feeToken"])]
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade["tid"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["sz"]),
                    fill_quote_amount=Decimal(trade["sz"]) * Decimal(trade["px"]),
                    fill_price=Decimal(trade["px"]),
                    fill_timestamp=trade["time"] * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        response = await self._api_post(path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL,
                                        data={"type": CONSTANTS.ASSET_CONTEXT_TYPE})
        price = 0
        for token in response[1]:
            if token['coin'] == exchange_symbol:
                price = token['markPx']
                break
        return price
