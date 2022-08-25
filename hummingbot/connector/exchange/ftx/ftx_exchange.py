import asyncio
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_0, s_decimal_NaN
from hummingbot.connector.exchange.ftx import ftx_constants as CONSTANTS, ftx_utils, ftx_web_utils as web_utils
from hummingbot.connector.exchange.ftx.ftx_api_order_book_data_source import FtxAPIOrderBookDataSource
from hummingbot.connector.exchange.ftx.ftx_api_user_stream_data_source import FtxAPIUserStreamDataSource
from hummingbot.connector.exchange.ftx.ftx_auth import FtxAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class FtxExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 ftx_api_key: str,
                 ftx_secret_key: str,
                 ftx_subaccount_name: str = None,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):

        self._api_key = ftx_api_key
        self._secret_key = ftx_secret_key
        self._subaccount_name = ftx_subaccount_name
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__(client_config_map)

        self._real_time_balance_update = False

    @property
    def name(self) -> str:
        return "ftx"

    @property
    def authenticator(self) -> AuthBase:
        return FtxAuth(
            api_key=self._api_key,
            secret_key=self._secret_key,
            subaccount_name=self._subaccount_name)

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.FTX_MARKETS_PATH

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.FTX_MARKETS_PATH

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.FTX_NETWORK_STATUS_PATH

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        # FTX API does not include an endpoint to get the server time, thus the TimeSynchronizer is not used
        return False

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.FTX_ORDER_WITH_CLIENT_ID_PATH.format(order_id),
            is_auth_required=True,
            limit_id=CONSTANTS.FTX_CANCEL_ORDER_LIMIT_ID)

        if not cancel_result.get("success", False):
            self.logger().warning(
                f"Failed to cancel order {order_id} ({cancel_result})")

        return cancel_result.get("success", False)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:

        api_params = {
            "market": await self.exchange_symbol_associated_to_pair(trading_pair),
            "side": trade_type.name.lower(),
            "price": float(price),
            "type": "market" if trade_type == OrderType.MARKET else "limit",
            "size": float(amount),
            "clientId": order_id,
        }
        order_result = await self._api_post(
            path_url=CONSTANTS.FTX_PLACE_ORDER_PATH,
            data=api_params,
            is_auth_required=True)
        exchange_order_id = str(order_result["result"]["id"])

        return exchange_order_id, self.current_timestamp

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
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
        pass

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                channel: str = event_message["channel"]
                data: Dict[str, Any] = event_message["data"]
                if channel == CONSTANTS.WS_PRIVATE_FILLS_CHANNEL:
                    exchange_order_id = str(data["orderId"])
                    order = next((order for order in self._order_tracker.all_fillable_orders.values()
                                  if order.exchange_order_id == exchange_order_id),
                                 None)
                    if order is not None:
                        trade_update = self._create_trade_update_with_order_fill_data(
                            order_fill_msg=data,
                            order=order)
                        self._order_tracker.process_trade_update(trade_update=trade_update)
                elif channel == CONSTANTS.WS_PRIVATE_ORDERS_CHANNEL:
                    client_order_id = data["clientId"]
                    order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if order is not None:
                        order_update = self._create_order_update_with_order_status_data(
                            order_status_msg=data,
                            order=order)
                        self._order_tracker.process_order_update(order_update=order_update)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
            Example:
            {{
              "success": true,
              "result": [
                {
                  "name": "BTC-PERP",
                  "baseCurrency": null,
                  "quoteCurrency": null,
                  "quoteVolume24h": 28914.76,
                  "change1h": 0.012,
                  "change24h": 0.0299,
                  "changeBod": 0.0156,
                  "highLeverageFeeExempt": false,
                  "minProvideSize": 0.001,
                  "type": "future",
                  "underlying": "BTC",
                  "enabled": true,
                  "ask": 3949.25,
                  "bid": 3949,
                  "last": 10579.52,
                  "postOnly": false,
                  "price": 10579.52,
                  "priceIncrement": 0.25,
                  "sizeIncrement": 0.0001,
                  "restricted": false,
                  "volumeUsd24h": 28914.76,
                  "largeOrderThreshold": 5000.0,
                  "isEtfMarket": false,
                }
              ]
            }
            """
        trading_pair_rules = exchange_info_dict.get("result", [])
        retval = []
        for rule in filter(ftx_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("name"))
                min_trade_size = Decimal(str(rule.get("minProvideSize")))
                price_increment = Decimal(str(rule.get("priceIncrement")))
                size_increment = Decimal(str(rule.get("sizeIncrement")))
                min_quote_amount_increment = price_increment * size_increment
                min_order_value = min_trade_size * price_increment

                retval.append(TradingRule(trading_pair,
                                          min_order_size=min_trade_size,
                                          min_price_increment=price_increment,
                                          min_base_amount_increment=size_increment,
                                          min_quote_amount_increment=min_quote_amount_increment,
                                          min_order_value=min_order_value,
                                          min_notional_size=min_order_value
                                          ))
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _update_balances(self):
        msg = await self._api_request(
            path_url=CONSTANTS.FTX_BALANCES_PATH,
            is_auth_required=True)

        if msg.get("success", False):
            balances = msg["result"]
        else:
            raise Exception(msg['msg'])

        self._account_available_balances.clear()
        self._account_balances.clear()

        for balance in balances:
            self._account_balances[balance["coin"]] = Decimal(str(balance["total"]))
            self._account_available_balances[balance["coin"]] = Decimal(str(balance["free"]))

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        try:
            exchange_order_id = await order.get_exchange_order_id()
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.FTX_ORDER_FILLS_PATH,
                params={
                    "market": trading_pair,
                    "orderId": int(exchange_order_id)
                },
                is_auth_required=True)

            for trade_fill in all_fills_response.get("result", []):
                trade_update = self._create_trade_update_with_order_fill_data(order_fill_msg=trade_fill, order=order)
                trade_updates.append(trade_update)

        except asyncio.TimeoutError:
            raise IOError(f"Skipped order update with order fills for {order.client_order_id} "
                          "- waiting for exchange order id.")

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.FTX_ORDER_WITH_CLIENT_ID_PATH.format(tracked_order.client_order_id),
            is_auth_required=True,
            limit_id=CONSTANTS.FTX_GET_ORDER_LIMIT_ID)

        order_update = self._create_order_update_with_order_status_data(
            order_status_msg=updated_order_data["result"],
            order=tracked_order)

        return order_update

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return FtxAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return FtxAPIUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(ftx_utils.is_exchange_information_valid, exchange_info["result"]):
            mapping[symbol_data["name"]] = combine_to_hb_trading_pair(base=symbol_data["baseCurrency"],
                                                                      quote=symbol_data["quoteCurrency"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        resp_json = await self._api_get(
            path_url=CONSTANTS.FTX_SINGLE_MARKET_PATH.format(symbol),
            limit_id=CONSTANTS.FTX_MARKETS_PATH
        )

        return float(resp_json["result"][0]["last"])

    def _create_trade_update_with_order_fill_data(self, order_fill_msg: Dict[str, Any], order: InFlightOrder):

        # Estimated fee token implemented according to https://help.ftx.com/hc/en-us/articles/360024479432-Fees
        is_maker = order_fill_msg["liquidity"] == "maker"
        if is_maker:
            estimated_fee_token = order.base_asset if order.trade_type == TradeType.BUY else order.quote_asset
        else:
            estimated_fee_token = order.quote_asset

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,
            percent_token=order_fill_msg.get("feeCurrency", estimated_fee_token),
            flat_fees=[TokenAmount(
                amount=Decimal(str(order_fill_msg["fee"])),
                token=order_fill_msg.get("feeCurrency", estimated_fee_token)
            )]
        )
        trade_update = TradeUpdate(
            trade_id=str(order_fill_msg["tradeId"]),
            client_order_id=order.client_order_id,
            exchange_order_id=str(order_fill_msg.get("orderId", order.exchange_order_id)),
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=Decimal(str(order_fill_msg["size"])),
            fill_quote_amount=Decimal(str(order_fill_msg["size"])) * Decimal(str(order_fill_msg["price"])),
            fill_price=Decimal(str(order_fill_msg["price"])),
            fill_timestamp=datetime.fromisoformat(order_fill_msg["time"]).timestamp(),
        )
        return trade_update

    def _create_order_update_with_order_status_data(self, order_status_msg: Dict[str, Any], order: InFlightOrder):
        state = order.current_state
        msg_status = order_status_msg["status"]
        if msg_status == "new":
            state = OrderState.OPEN
        elif msg_status == "open" and (Decimal(str(order_status_msg["filledSize"])) > s_decimal_0):
            state = OrderState.PARTIALLY_FILLED
        elif msg_status == "closed":
            state = (OrderState.CANCELED
                     if Decimal(str(order_status_msg["filledSize"])) == s_decimal_0
                     else OrderState.FILLED)

        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=state,
            client_order_id=order.client_order_id,
            exchange_order_id=str(order_status_msg["id"]),
        )
        return order_update
