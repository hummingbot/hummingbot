import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

import pandas as pd
from bidict import bidict

from hummingbot.connector.constants import s_decimal_0, s_decimal_NaN
from hummingbot.connector.derivative.hashkey_perpetual import (
    hashkey_perpetual_constants as CONSTANTS,
    hashkey_perpetual_utils as hashkey_utils,
    hashkey_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.hashkey_perpetual.hashkey_perpetual_api_order_book_data_source import (
    HashkeyPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.hashkey_perpetual.hashkey_perpetual_auth import HashkeyPerpetualAuth
from hummingbot.connector.derivative.hashkey_perpetual.hashkey_perpetual_user_stream_data_source import (
    HashkeyPerpetualUserStreamDataSource,
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
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

bpm_logger = None


class HashkeyPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            hashkey_perpetual_api_key: str = None,
            hashkey_perpetual_secret_key: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.hashkey_perpetual_api_key = hashkey_perpetual_api_key
        self.hashkey_perpetual_secret_key = hashkey_perpetual_secret_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = PositionMode.HEDGE
        self._last_trade_history_timestamp = None
        super().__init__(client_config_map)
        self._perpetual_trading.set_position_mode(PositionMode.HEDGE)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> HashkeyPerpetualAuth:
        return HashkeyPerpetualAuth(self.hashkey_perpetual_api_key, self.hashkey_perpetual_secret_key,
                                    self._time_synchronizer)

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
        return 600

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self):
        """
        This method needs to be overridden to provide the accurate information depending on the exchange.
        """
        return [PositionMode.HEDGE]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(
            status_update_exception
        ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return HashkeyPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return HashkeyPerpetualUserStreamDataSource(
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
                 position_action: PositionAction,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker or False
        fee = build_perpetual_trade_fee(
            self.name,
            is_maker,
            position_action=position_action,
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

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_fills_from_trades(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        api_params = {"type": "LIMIT"}
        if tracked_order.exchange_order_id:
            api_params["orderId"] = tracked_order.exchange_order_id
        else:
            api_params["clientOrderId"] = tracked_order.client_order_id
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_URL,
            params=api_params,
            is_auth_required=True)
        if cancel_result.get("code") == -2011 and "Unknown order sent." == cancel_result.get("msg", ""):
            self.logger().debug(f"The order {order_id} does not exist on Hashkey Perpetuals. "
                                f"No cancelation needed.")
            await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f"{cancel_result.get('code')} - {cancel_result['msg']}")
        if cancel_result.get("status") == "CANCELED":
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

        price_str = f"{price:f}"
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        side = f"BUY_{position_action.value}" if trade_type is TradeType.BUY else f"SELL_{position_action.value}"
        api_params = {"symbol": symbol,
                      "side": side,
                      "quantity": self.get_quantity_of_contracts(trading_pair, amount),
                      "type": "LIMIT",
                      "priceType": "MARKET" if order_type is OrderType.MARKET else "INPUT",
                      "clientOrderId": order_id
                      }
        if order_type.is_limit_type():
            api_params["price"] = price_str
        if order_type == OrderType.LIMIT:
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC
        if order_type == OrderType.LIMIT_MAKER:
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_MAKER
        try:
            order_result = await self._api_post(
                path_url=CONSTANTS.ORDER_URL,
                params=api_params,
                is_auth_required=True)
            o_id = str(order_result["orderId"])
            transact_time = int(order_result["time"]) * 1e-3
        except IOError as e:
            error_description = str(e)
            is_server_overloaded = ("status is 503" in error_description
                                    and "Unknown error, please check your request or try again later." in error_description)
            if is_server_overloaded:
                o_id = "UNKNOWN"
                transact_time = time.time()
            else:
                raise
        return o_id, transact_time

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)
            fills_data = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                params={
                    "clientOrderId": order.client_order_id,
                },
                is_auth_required=True,
                limit_id=CONSTANTS.ACCOUNT_TRADE_LIST_URL)
            if fills_data is not None:
                for trade in fills_data:
                    exchange_order_id = str(trade["orderId"])
                    if exchange_order_id != str(order.exchange_order_id):
                        continue
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent_token=trade["commissionAsset"],
                        flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
                    )
                    amount = self.get_amount_of_contracts(order.trading_pair, int(trade["quantity"]))
                    trade_update = TradeUpdate(
                        trade_id=str(trade["tradeId"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=order.trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(amount),
                        fill_quote_amount=Decimal(trade["price"]) * amount,
                        fill_price=Decimal(trade["price"]),
                        fill_timestamp=int(trade["time"]) * 1e-3,
                    )
                    trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.ORDER_URL,
            params={
                "clientOrderId": tracked_order.client_order_id},
            is_auth_required=True)

        new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["orderId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=int(updated_order_data["updateTime"]) * 1e-3,
            new_state=new_state,
        )

        return order_update

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
                    app_warning_msg="Could not fetch user events from Hashkey. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_messages in self._iter_user_event_queue():
            if isinstance(event_messages, dict) and "ping" in event_messages:
                continue

            for event_message in event_messages:
                try:
                    event_type = event_message.get("e")
                    if event_type == "contractExecutionReport":
                        execution_type = event_message.get("X")
                        client_order_id = event_message.get("c")
                        updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                        if updatable_order is not None:
                            if execution_type in ["PARTIALLY_FILLED", "FILLED"]:
                                fee = TradeFeeBase.new_perpetual_fee(
                                    fee_schema=self.trade_fee_schema(),
                                    position_action=PositionAction.CLOSE if event_message["C"] else PositionAction.OPEN,
                                    percent_token=event_message["N"],
                                    flat_fees=[TokenAmount(amount=Decimal(event_message["n"]), token=event_message["N"])]
                                )
                                base_amount = Decimal(self.get_amount_of_contracts(updatable_order.trading_pair, int(event_message["l"])))
                                trade_update = TradeUpdate(
                                    trade_id=str(event_message["d"]),
                                    client_order_id=client_order_id,
                                    exchange_order_id=str(event_message["i"]),
                                    trading_pair=updatable_order.trading_pair,
                                    fee=fee,
                                    fill_base_amount=base_amount,
                                    fill_quote_amount=base_amount * Decimal(event_message["L"] or event_message["p"]),
                                    fill_price=Decimal(event_message["L"]),
                                    fill_timestamp=int(event_message["E"]) * 1e-3,
                                )
                                self._order_tracker.process_trade_update(trade_update)

                            order_update = OrderUpdate(
                                trading_pair=updatable_order.trading_pair,
                                update_timestamp=int(event_message["E"]) * 1e-3,
                                new_state=CONSTANTS.ORDER_STATE[event_message["X"]],
                                client_order_id=client_order_id,
                                exchange_order_id=str(event_message["i"]),
                            )
                            self._order_tracker.process_order_update(order_update=order_update)

                    elif event_type == "outboundContractAccountInfo":
                        balances = event_message["B"]
                        for balance_entry in balances:
                            asset_name = balance_entry["a"]
                            free_balance = Decimal(balance_entry["f"])
                            total_balance = Decimal(balance_entry["f"]) + Decimal(balance_entry["l"])
                            self._account_available_balances[asset_name] = free_balance
                            self._account_balances[asset_name] = total_balance

                    elif event_type == "outboundContractPositionInfo":
                        ex_trading_pair = event_message["s"]
                        hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(ex_trading_pair)
                        position_side = PositionSide(event_message["S"])
                        unrealized_pnl = Decimal(str(event_message["up"]))
                        entry_price = Decimal(str(event_message["p"]))
                        amount = Decimal(self.get_amount_of_contracts(hb_trading_pair, int(event_message["P"])))
                        leverage = Decimal(event_message["v"])
                        pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
                        if amount != s_decimal_0:
                            position = Position(
                                trading_pair=hb_trading_pair,
                                position_side=position_side,
                                unrealized_pnl=unrealized_pnl,
                                entry_price=entry_price,
                                amount=amount * (Decimal("-1.0") if position_side == PositionSide.SHORT else Decimal("1.0")),
                                leverage=leverage,
                            )
                            self._perpetual_trading.set_position(pos_key, position)
                        else:
                            self._perpetual_trading.remove_position(pos_key)

                except asyncio.CancelledError:
                    raise
                except Exception:
                    self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                    await self._sleep(5.0)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "timezone": "UTC",
            "serverTime": "1703696385826",
            "brokerFilters": [],
            "symbols": [],
            "options": [],
            "contracts": [
                {
                    "filters": [
                        {
                            "minPrice": "0.1",
                            "maxPrice": "100000.00000000",
                            "tickSize": "0.1",
                            "filterType": "PRICE_FILTER"
                        },
                        {
                            "minQty": "0.001",
                            "maxQty": "10",
                            "stepSize": "0.001",
                            "marketOrderMinQty": "0",
                            "marketOrderMaxQty": "0",
                            "filterType": "LOT_SIZE"
                        },
                        {
                            "minNotional": "0",
                            "filterType": "MIN_NOTIONAL"
                        },
                        {
                            "maxSellPrice": "999999",
                            "buyPriceUpRate": "0.05",
                            "sellPriceDownRate": "0.05",
                            "maxEntrustNum": 200,
                            "maxConditionNum": 200,
                            "filterType": "LIMIT_TRADING"
                        },
                        {
                            "buyPriceUpRate": "0.05",
                            "sellPriceDownRate": "0.05",
                            "filterType": "MARKET_TRADING"
                        },
                        {
                            "noAllowMarketStartTime": "0",
                            "noAllowMarketEndTime": "0",
                            "limitOrderStartTime": "0",
                            "limitOrderEndTime": "0",
                            "limitMinPrice": "0",
                            "limitMaxPrice": "0",
                            "filterType": "OPEN_QUOTE"
                        }
                    ],
                    "exchangeId": "301",
                    "symbol": "BTCUSDT-PERPETUAL",
                    "symbolName": "BTCUSDT-PERPETUAL",
                    "status": "TRADING",
                    "baseAsset": "BTCUSDT-PERPETUAL",
                    "baseAssetPrecision": "0.001",
                    "quoteAsset": "USDT",
                    "quoteAssetPrecision": "0.1",
                    "icebergAllowed": false,
                    "inverse": false,
                    "index": "USDT",
                    "marginToken": "USDT",
                    "marginPrecision": "0.0001",
                    "contractMultiplier": "0.001",
                    "underlying": "BTC",
                    "riskLimits": [
                        {
                            "riskLimitId": "200000722",
                            "quantity": "1000.00",
                            "initialMargin": "0.10",
                            "maintMargin": "0.005",
                            "isWhite": false
                        }
                    ]
                }
            ],
            "coins": []
        }
        """
        trading_pair_rules = exchange_info_dict.get("contracts", [])
        retval = []
        for rule in trading_pair_rules:
            try:
                if not hashkey_utils.is_exchange_information_valid(rule):
                    continue

                trading_pair = f"{rule['underlying']}-{rule['quoteAsset']}"

                trading_filter_info = {item["filterType"]: item for item in rule.get("filters", [])}

                min_order_size = trading_filter_info.get("LOT_SIZE", {}).get("minQty")
                min_price_increment = trading_filter_info.get("PRICE_FILTER", {}).get("minPrice")
                min_base_amount_increment = rule.get("baseAssetPrecision")
                min_notional_size = trading_filter_info.get("MIN_NOTIONAL", {}).get("minNotional")

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=Decimal(min_order_size),
                                min_price_increment=Decimal(min_price_increment),
                                min_base_amount_increment=Decimal(min_base_amount_increment),
                                min_notional_size=Decimal(min_notional_size)))

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule.get('symbol')}. Skipping.")
        return retval

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(hashkey_utils.is_exchange_information_valid, exchange_info["contracts"]):
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=symbol_data["underlying"],
                                                                        quote=symbol_data["quoteAsset"])
        self._set_trading_pair_symbol_map(mapping)

    async def exchange_index_symbol_associated_to_pair(self, trading_pair: str):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        return symbol[:-10]

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        }
        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PRICE_URL,
            params=params,
        )

        return float(resp_json[0]["p"])

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        balances = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.ACCOUNT_INFO_URL,
            is_auth_required=True)

        for balance_entry in balances:
            asset_name = balance_entry["asset"]
            total_balance = Decimal(balance_entry["balance"])
            free_balance = Decimal(balance_entry["availableBalance"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        position_tasks = []

        for trading_pair in self._trading_pairs:
            ex_trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair)
            body_params = {"symbol": ex_trading_pair}
            position_tasks.append(
                asyncio.create_task(self._api_get(
                    path_url=CONSTANTS.POSITION_INFORMATION_URL,
                    params=body_params,
                    is_auth_required=True,
                    trading_pair=trading_pair,
                ))
            )

        raw_responses: List[Dict[str, Any]] = await safe_gather(*position_tasks, return_exceptions=True)

        # Initial parsing of responses. Joining all the responses
        parsed_resps: List[Dict[str, Any]] = []
        for resp, trading_pair in zip(raw_responses, self._trading_pairs):
            if not isinstance(resp, Exception):
                if resp:
                    position_entries = resp if isinstance(resp, list) else [resp]
                    parsed_resps.extend(position_entries)
            else:
                self.logger().error(f"Error fetching positions for {trading_pair}. Response: {resp}")

        for position in parsed_resps:
            ex_trading_pair = position["symbol"]
            hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(ex_trading_pair)
            position_side = PositionSide(position["side"])
            unrealized_pnl = Decimal(str(position["unrealizedPnL"]))
            entry_price = Decimal(str(position["avgPrice"]))
            amount = Decimal(self.get_amount_of_contracts(hb_trading_pair, int(position["position"])))
            leverage = Decimal(position["leverage"])
            pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
            if amount != s_decimal_0:
                position = Position(
                    trading_pair=hb_trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount * (Decimal("-1.0") if position_side == PositionSide.SHORT else Decimal("1.0")),
                    leverage=leverage,
                )
                self._perpetual_trading.set_position(pos_key, position)
            else:
                self._perpetual_trading.remove_position(pos_key)

    async def _update_order_fills_from_trades(self):
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            trading_pairs_to_order_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {})
            for order in self._order_tracker.active_orders.values():
                trading_pairs_to_order_map[order.trading_pair][order.exchange_order_id] = order
            trading_pairs = list(trading_pairs_to_order_map.keys())
            tasks = [
                self._api_get(
                    path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                    params={"symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)},
                    is_auth_required=True,
                )
                for trading_pair in trading_pairs
            ]
            self.logger().debug(f"Polling for order fills of {len(tasks)} trading_pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for trades, trading_pair in zip(results, trading_pairs):
                order_map = trading_pairs_to_order_map.get(trading_pair)
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    order_id = str(trade.get("orderId"))
                    if order_id in order_map:
                        tracked_order: InFlightOrder = order_map.get(order_id)
                        position_side = trade["side"]
                        position_action = (PositionAction.OPEN
                                           if (tracked_order.trade_type is TradeType.BUY and position_side == "LONG"
                                               or tracked_order.trade_type is TradeType.SELL and position_side == "SHORT")
                                           else PositionAction.CLOSE)
                        fee = TradeFeeBase.new_perpetual_fee(
                            fee_schema=self.trade_fee_schema(),
                            position_action=position_action,
                            percent_token=trade["commissionAsset"],
                            flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
                        )
                        amount = self.get_amount_of_contracts(trading_pair, int(trade["quantity"]))
                        trade_update: TradeUpdate = TradeUpdate(
                            trade_id=str(trade["tradeId"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=trade["orderId"],
                            trading_pair=tracked_order.trading_pair,
                            fill_timestamp=int(trade["time"]) * 1e-3,
                            fill_price=Decimal(trade["price"]),
                            fill_base_amount=Decimal(amount),
                            fill_quote_amount=Decimal(trade["price"]) * amount,
                            fee=fee,
                        )
                        self._order_tracker.process_trade_update(trade_update)

    async def _update_order_status(self):
        """
        Calls the REST API to get order/trade updates for each in-flight order.
        """
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            tracked_orders = list(self._order_tracker.active_orders.values())
            tasks = [
                self._api_get(
                    path_url=CONSTANTS.ORDER_URL,
                    params={
                        "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair),
                        "clientOrderId": order.client_order_id
                    },
                    is_auth_required=True,
                    return_err=True,
                )
                for order in tracked_orders
            ]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if client_order_id not in self._order_tracker.all_orders:
                    continue
                if isinstance(order_update, Exception) or order_update is None or "code" in order_update:
                    if not isinstance(order_update, Exception) and \
                            (not order_update or (order_update["code"] == -2013 or order_update["msg"] == "Order does not exist.")):
                        await self._order_tracker.process_order_not_found(client_order_id)
                    else:
                        self.logger().network(
                            f"Error fetching status update for the order {client_order_id}: " f"{order_update}."
                        )
                    continue

                new_order_update: OrderUpdate = OrderUpdate(
                    trading_pair=await self.trading_pair_associated_to_exchange_symbol(order_update['symbol']),
                    update_timestamp=int(order_update["updateTime"]) * 1e-3,
                    new_state=CONSTANTS.ORDER_STATE[order_update["status"]],
                    client_order_id=order_update["clientOrderId"],
                    exchange_order_id=order_update["orderId"],
                )

                self._order_tracker.process_order_update(new_order_update)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        return self._position_mode

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        return False, "Not support to set position mode"

    def get_quantity_of_contracts(self, trading_pair: str, amount: float) -> int:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        num_contracts = int(amount / trading_rule.min_base_amount_increment)
        return num_contracts

    def get_amount_of_contracts(self, trading_pair: str, number: int) -> Decimal:
        if len(self._trading_rules) > 0:
            trading_rule: TradingRule = self._trading_rules[trading_pair]
            contract_value = Decimal(number * trading_rule.min_base_amount_increment)
        else:
            contract_value = Decimal(number * 0.001)
        return contract_value

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        params = {'symbol': symbol, 'leverage': leverage}
        resp = await self._api_post(
            path_url=CONSTANTS.SET_LEVERAGE_URL,
            params=params,
            is_auth_required=True,
        )
        success = False
        msg = ""
        if "leverage" in resp and int(resp["leverage"]) == leverage:
            success = True
        elif "msg" in resp:
            msg = resp["msg"]
        else:
            msg = 'Unable to set leverage'
        return success, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

        params = {
            "symbol": exchange_symbol,
            "timestamp": int(self._time_synchronizer.time() * 1e3)
        }
        result = (await self._api_get(
            path_url=CONSTANTS.FUNDING_INFO_URL,
            params=params,
            is_auth_required=True,
            trading_pair=trading_pair,
        ))[0]

        if not result:
            # An empty funding fee/payment is retrieved.
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
        else:
            funding_rate: Decimal = Decimal(str(result["rate"]))
            position_size: Decimal = Decimal(0.0)
            payment: Decimal = funding_rate * position_size
            timestamp: int = int(pd.Timestamp(int(result["nextSettleTime"]), unit="ms", tz="UTC").timestamp())

        return timestamp, funding_rate, payment

    async def _api_request(self,
                           path_url,
                           method: RESTMethod = RESTMethod.GET,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           return_err: bool = False,
                           limit_id: Optional[str] = None,
                           trading_pair: Optional[str] = None,
                           **kwargs) -> Dict[str, Any]:
        last_exception = None
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.rest_url(path_url, domain=self.domain)
        local_headers = {
            "Content-Type": "application/x-www-form-urlencoded"}
        for _ in range(2):
            try:
                request_result = await rest_assistant.execute_request(
                    url=url,
                    params=params,
                    data=data,
                    method=method,
                    is_auth_required=is_auth_required,
                    return_err=return_err,
                    headers=local_headers,
                    throttler_limit_id=limit_id if limit_id else path_url,
                )
                return request_result
            except IOError as request_exception:
                last_exception = request_exception
                if self._is_request_exception_related_to_time_synchronizer(request_exception=request_exception):
                    self._time_synchronizer.clear_time_offset_ms_samples()
                    await self._update_time_synchronizer()
                else:
                    raise

        # Failed even after the last retry
        raise last_exception
