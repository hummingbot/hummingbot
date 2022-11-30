import asyncio
import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from bidict import bidict

from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS, lbank_web_utils as web_utils
from hummingbot.connector.exchange.lbank.lbank_api_order_book_data_source import LbankAPIOrderBookDataSource
from hummingbot.connector.exchange.lbank.lbank_api_user_stream_data_source import LbankAPIUserStreamDataSource
from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class LbankExchange(ExchangePyBase):

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        lbank_api_key: str,
        lbank_secret_key: str,
        lbank_auth_method: str = "RSA",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        self.lbank_api_key = lbank_api_key
        self.lbank_secret_key = lbank_secret_key
        self.lbank_auth_method = lbank_auth_method
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        super().__init__(client_config_map)

    @property
    def authenticator(self):
        return LbankAuth(
            api_key=self.lbank_api_key, secret_key=self.lbank_secret_key, auth_method=self.lbank_auth_method
        )

    @property
    def name(self):
        return "lbank"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return ""

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.CLIENT_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.LBANK_TRADING_PAIRS_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.LBANK_TRADING_PAIRS_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.LBANK_GET_TIMESTAMP_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # Exchange does not have a particular error for incorrect timestamps
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(auth=self._auth,
                                           throttler=self._throttler,
                                           time_synchronizer=self._time_synchronizer)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LbankAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs, connector=self, api_factory=self._web_assistants_factory
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LbankAPIUserStreamDataSource(
            auth=self._auth, connector=self, api_factory=self._web_assistants_factory, trading_pairs=self._trading_pairs
        )

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        if exchange_info.get("result") == "false":
            err_code: int = exchange_info.get("error_code")
            err_msg: str = f"Error Code: {err_code} - {CONSTANTS.ERROR_CODES.get(err_code, '')}"
            self.logger().error(
                f"Error initializing trading pair symbols with exchange info response. {err_msg} Response: {exchange_info}"
            )
            return

        mapping = bidict()
        data_list: List[Dict[str, Any]] = exchange_info.get("data")

        for symbol_data in data_list:
            exchange_symbol: str = symbol_data["symbol"]
            base_asset, quote_asset = exchange_symbol.split("_")
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base_asset.upper(), quote_asset.upper())
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        trading_rules: List[TradingRule] = []

        data_list: List[Dict[str, Any]] = exchange_info_dict.get("data")
        for symbol_data in data_list:
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol_data["symbol"])
                if trading_pair in self._trading_pairs:
                    trading_rules.append(
                        TradingRule(
                            trading_pair=trading_pair,
                            min_order_size=Decimal(symbol_data["minTranQua"]),
                            min_base_amount_increment=Decimal(f"1e-{symbol_data['quantityAccuracy']}"),
                            min_price_increment=Decimal(f"1e-{symbol_data['priceAccuracy']}"),
                        )
                    )
            except Exception:
                self.logger().exception(f"Error parsing trading pair rule {symbol_data}. Skipping.")
        return trading_rules

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
        data = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "type": trade_type.name.lower(),
            "price": str(price),
            "amount": str(amount),
            "custom_id": order_id,
        }

        response = await self._api_post(
            path_url=CONSTANTS.LBANK_CREATE_ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.LBANK_CREATE_ORDER_PATH_URL,
        )

        if not response.get("result", False):
            err_code: int = response.get("error_code")
            err_msg: str = f"Error Code: {err_code} - {CONSTANTS.ERROR_CODES.get(err_code, '')}"
            raise ValueError(f"Error submitting order: {order_id} {err_msg} Response: {response}")
        return str(response["data"]["order_id"]), self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        data = {
            "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
            "customer_id": order_id,
        }

        response = await self._api_post(
            path_url=CONSTANTS.LBANK_CANCEL_ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.LBANK_CANCEL_ORDER_PATH_URL,
        )

        if not response.get("result", False):
            err_code: int = response.get("error_code")
            err_msg: str = f"Error Code: {err_code} - {CONSTANTS.ERROR_CODES.get(err_code, '')}"
            raise ValueError(f"Error canceling order: {order_id} {err_msg} Response: {response}")
        return True

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = is_maker or (order_type in (OrderType.LIMIT_MAKER, OrderType.LIMIT))
        return build_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {"symbol": await self.exchange_symbol_associated_to_pair(trading_pair)}
        response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.LBANK_CURRENT_MARKET_DATA_PATH_URL,
            params=params,
            limit_id=CONSTANTS.LBANK_CURRENT_MARKET_DATA_PATH_URL,
        )
        ticker_data: Optional[List[Dict[str, Any]]] = response.get("data", None)
        if ticker_data:
            symbol_data: Dict[str, Any] = ticker_data[0]["ticker"]
            return float(symbol_data["latest"])

    async def _update_balances(self):
        response: Union[str, Dict[str, Any]] = await self._api_post(path_url=CONSTANTS.LBANK_USER_ASSET_PATH_URL,
                                                                    is_auth_required=True)

        if isinstance(response, str):  # Error responses are in text/html
            response: Dict[str, Any] = json.loads(response)
        err_code: Optional[int] = response.get("error_code", 0)
        if err_code > 0:
            err_msg: str = CONSTANTS.ERROR_CODES.get(err_code, "")
            raise ValueError(f"Error retrieving account balance. {err_msg}. Response: {response}")

        balance_info: Optional[Dict[str, Any]] = response.get("data", None)

        if balance_info:
            self._account_available_balances.clear()
            self._account_balances.clear()
            total_asset_info: Dict[str, Any] = balance_info.get("asset", {})
            available_asset_info: Dict[str, Any] = balance_info.get("free", {})

            for asset, total_balance in total_asset_info.items():
                self._account_balances[asset.upper()] = Decimal(total_balance)
            for asset, available_balance in available_asset_info.items():
                self._account_available_balances[asset.upper()] = Decimal(available_balance)

    async def _request_order_update(self, order: InFlightOrder):
        data = {
            "symbol": await self.exchange_symbol_associated_to_pair(order.trading_pair),
            "order_id": await order.get_exchange_order_id(),
        }

        response = await self._api_post(
            path_url=CONSTANTS.LBANK_ORDER_UPDATES_PATH_URL,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.LBANK_ORDER_UPDATES_PATH_URL,
        )
        if isinstance(response, str):  # Error responses are in text/html
            response: Dict[str, Any] = json.loads(response)
            err_code: Optional[int] = response.get("error_code", 0)
            if err_code > 0:
                err_msg: str = CONSTANTS.ERROR_CODES.get(err_code, "")
                raise ValueError(f"{err_msg}. Response: {response}")

        return response

    async def _request_order_fills(self, order: InFlightOrder):
        data = {
            "symbol": await self.exchange_symbol_associated_to_pair(order.trading_pair),
            "order_id": await order.get_exchange_order_id(),
        }

        response = await self._api_post(
            path_url=CONSTANTS.LBANK_TRADE_UPDATES_PATH_URL,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.LBANK_TRADE_UPDATES_PATH_URL,
        )
        if isinstance(response, str):  # Error responses are in text/html
            response: Dict[str, Any] = json.loads(response)
            err_code: Optional[int] = response.get("error_code", 0)
            if err_code > 0:
                err_msg: str = CONSTANTS.ERROR_CODES.get(err_code, "")
                raise ValueError(f"{err_msg}. Response: {response}")

        return response

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            all_fills_response = await self._request_order_fills(order=order)

            order_fill_data: Optional[List[Any]] = all_fills_response.get("data", [])
            for tx in order_fill_data:
                fee_token = order.base_asset if order.trade_type == TradeType.BUY else order.quote_asset
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    flat_fees=[TokenAmount(token=fee_token, amount=Decimal(str(tx["tradeFee"])))],
                )
                trade_update = TradeUpdate(
                    trade_id=str(tx["txUuid"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=tx["orderUuid"],
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(str(tx["dealQuantity"])),
                    fill_quote_amount=Decimal(str(tx["dealPrice"])) * Decimal(str(tx["dealQuantity"])),
                    fill_price=Decimal(str(tx["dealPrice"])),
                    fill_timestamp=int(tx["dealTime"]) * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._request_order_update(order=tracked_order)

        order_data: Optional[List[Dict[str, Any]]] = updated_order_data.get("data", None)
        if order_data:
            order_data: Dict[str, Any] = order_data[0]
            new_state: OrderState = CONSTANTS.ORDER_STATUS[order_data["status"]]
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=order_data["order_id"],
                trading_pair=tracked_order.trading_pair,
                update_timestamp=updated_order_data.get("ts", self._time() * 1e3) * 1e-3,
                new_state=new_state,
            )
        else:
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=tracked_order.current_state)

        return order_update

    async def _update_trading_fees(self):
        pass

    async def _user_stream_event_listener(self):
        async for message in self._iter_user_event_queue():
            try:
                channel: str = message.get("type")

                if channel == CONSTANTS.LBANK_USER_ORDER_UPDATE_CHANNEL:
                    data: Dict[str, Any] = message.get(CONSTANTS.LBANK_USER_ORDER_UPDATE_CHANNEL)

                    updatable_order = self._order_tracker.all_updatable_orders.get(data["customerID"])
                    fillable_order = self._order_tracker.all_fillable_orders.get(data["customerID"])

                    new_state: OrderState = CONSTANTS.ORDER_STATUS[data["orderStatus"]]

                    if fillable_order is not None:
                        is_fill_candidate_by_state = new_state in [OrderState.PARTIALLY_FILLED, OrderState.FILLED]
                        is_fill_candidate_by_amount = fillable_order.executed_amount_base < Decimal(data["accAmt"])

                        if is_fill_candidate_by_state and is_fill_candidate_by_amount:
                            try:
                                order_fill_data: Dict[str, Any] = await self._request_order_fills(fillable_order)
                                if "data" in order_fill_data:
                                    for tx in order_fill_data["data"]:
                                        fee_token = (fillable_order.base_asset
                                                     if fillable_order.trade_type == TradeType.BUY
                                                     else fillable_order.quote_asset)
                                        fee = TradeFeeBase.new_spot_fee(
                                            fee_schema=self.trade_fee_schema(),
                                            trade_type=fillable_order.trade_type,
                                            flat_fees=[TokenAmount(token=fee_token,
                                                                   amount=Decimal(str(tx["tradeFee"])))],
                                        )
                                        trade_update = TradeUpdate(
                                            trade_id=str(tx["txUuid"]),
                                            client_order_id=fillable_order.client_order_id,
                                            exchange_order_id=tx["orderUuid"],
                                            trading_pair=fillable_order.trading_pair,
                                            fee=fee,
                                            fill_base_amount=Decimal(str(tx["dealQuantity"])),
                                            fill_quote_amount=Decimal(str(tx["dealPrice"])) * Decimal(str(tx["dealQuantity"])),
                                            fill_price=Decimal(str(tx["dealPrice"])),
                                            fill_timestamp=int(tx["dealTime"]) * 1e-3,
                                        )
                                        self._order_tracker.process_trade_update(trade_update)

                            except asyncio.CancelledError:
                                raise
                            except Exception as e:
                                self.logger().exception("Unexpected error processing order fills for "
                                                        f"{fillable_order.client_order_id}. Error: {str(e)}")
                    if updatable_order is not None:
                        order_update = OrderUpdate(
                            trading_pair=updatable_order.trading_pair,
                            update_timestamp=int(data["updateTime"]) * 1e-3,
                            new_state=new_state,
                            client_order_id=data["customerID"],
                            exchange_order_id=data["uuid"],
                        )
                        self._order_tracker.process_order_update(order_update)

                elif channel == CONSTANTS.LBANK_USER_BALANCE_UPDATE_CHANNEL:
                    data: Dict[str, Any] = message.get("data")
                    asset: str = data["assetCode"].upper()

                    self._account_balances[asset] = Decimal(data["asset"])
                    self._account_available_balances[asset] = Decimal(data["free"])
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)
