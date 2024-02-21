import asyncio
from abc import abstractmethod
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utilities.oms_connector import (
    oms_connector_constants as CONSTANTS,
    oms_connector_web_utils as ap_web_utils,
)
from hummingbot.connector.utilities.oms_connector.oms_connector_api_order_book_data_source import (
    OMSConnectorAPIOrderBookDataSource,
)
from hummingbot.connector.utilities.oms_connector.oms_connector_api_user_stream_data_source import (
    OMSConnectorAPIUserStreamDataSource,
)
from hummingbot.connector.utilities.oms_connector.oms_connector_auth import OMSConnectorAuth
from hummingbot.connector.utilities.oms_connector.oms_connector_utils import is_exchange_information_valid
from hummingbot.connector.utilities.oms_connector.oms_connector_web_utils import (
    OMSConnectorURLCreatorBase,
    OMSConnectorWebAssistantsFactory,
)
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class OMSExchange(ExchangePyBase):

    web_utils = ap_web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        api_key: str,
        secret_key: str,
        user_id: int,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        url_creator: Optional[OMSConnectorURLCreatorBase] = None,
    ):
        self._api_key = api_key
        self._secret_key = secret_key
        self._user_id = user_id
        self._auth: Optional[OMSConnectorAuth] = None
        self._url_creator = url_creator
        self._nonce_creator = NonceCreator.for_seconds()
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._web_assistants_factory: OMSConnectorWebAssistantsFactory
        self._token_id_map: Dict[int, str] = {}
        self._order_not_found_on_cancel_record: Dict[str, int] = defaultdict(lambda: 0)
        super().__init__(client_config_map)

    @property
    @abstractmethod
    def oms_id(self) -> int:
        raise NotImplementedError

    @property
    def authenticator(self) -> OMSConnectorAuth:
        if self._auth is None:
            self._auth = OMSConnectorAuth(self._api_key, self._secret_key, self._user_id)
        return self._auth

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def client_order_id_max_length(self) -> int:
        return -1

    @property
    def client_order_id_prefix(self) -> str:
        return ""

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.REST_PRODUCTS_ENDPOINT

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.REST_PRODUCTS_ENDPOINT

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.REST_PING_ENDPOINT

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT]

    async def start_network(self):
        await self._authenticate()
        await super().start_network()

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
        order_id = str(
            get_new_numeric_client_order_id(
                nonce_creator=self._nonce_creator, max_id_bit_count=CONSTANTS.MAX_ID_BIT_COUNT
            )
        )
        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price))
        return order_id

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
        order_id = str(
            get_new_numeric_client_order_id(
                nonce_creator=self._nonce_creator, max_id_bit_count=CONSTANTS.MAX_ID_BIT_COUNT
            )
        )
        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price))
        return order_id

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # Not required for OMS connectors
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

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        This implementation specific function is called by _cancel, and returns True if successful
        """
        start_ts = self.current_timestamp
        self.logger().debug(f"Starting cancelation of {tracked_order.client_order_id} at {start_ts}")
        await self._ensure_authenticated()
        params = {
            CONSTANTS.OMS_ID_FIELD: self.oms_id,
            CONSTANTS.ACCOUNT_ID_FIELD: self._auth.account_id,
            CONSTANTS.CL_ORDER_ID_FIELD: int(tracked_order.client_order_id),
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.REST_ORDER_CANCELATION_ENDPOINT,
            data=params,
            is_auth_required=True,
        )
        self.logger().debug(f"Cancelation result of {tracked_order.client_order_id} at {start_ts}: {cancel_result}")
        cancel_success = False
        if cancel_result.get(CONSTANTS.ERROR_CODE_FIELD):
            if cancel_result[CONSTANTS.ERROR_CODE_FIELD] == CONSTANTS.RESOURCE_NOT_FOUND_ERR_CODE:
                await self._order_tracker.process_order_not_found(order_id)
            else:
                raise IOError(cancel_result[CONSTANTS.ERROR_MSG_FIELD])
        cancel_success = cancel_success or cancel_result[CONSTANTS.RESULT_FIELD]

        if not cancel_success:
            self.logger().debug(
                f"Failure to cancel {tracked_order.client_order_id}, attempted at {start_ts}: {cancel_result}"
            )
        elif order_id in self._order_not_found_on_cancel_record:
            del self._order_not_found_on_cancel_record[order_id]

        self.logger().debug(
            f"Cancelation of {tracked_order.client_order_id} at {start_ts} success"
        )

        return cancel_success

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
        is_maker = False
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

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
    ) -> Tuple[str, float]:
        instrument_id = await self.exchange_symbol_associated_to_pair(trading_pair)
        data = {
            CONSTANTS.INSTRUMENT_ID_FIELD: int(instrument_id),
            CONSTANTS.OMS_ID_FIELD: self.oms_id,
            CONSTANTS.ACCOUNT_ID_FIELD: self._auth.account_id,
            CONSTANTS.TIME_IN_FORCE_FIELD: CONSTANTS.GTC_TIF,
            CONSTANTS.CLIENT_ORDER_ID_FIELD: int(order_id),
            CONSTANTS.SIDE_FIELD: CONSTANTS.BUY_ACTION if trade_type == TradeType.BUY else CONSTANTS.SELL_ACTION,
            CONSTANTS.QUANTITY_FIELD: float(amount),
            CONSTANTS.ORDER_TYPE_FIELD: CONSTANTS.ORDER_TYPES[order_type],
            CONSTANTS.LIMIT_PRICE_FIELD: float(price),
        }

        send_order_resp = await self._api_request(
            path_url=CONSTANTS.REST_ORDER_CREATION_ENDPOINT,
            method=RESTMethod.POST,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.REST_ORDER_CREATION_ENDPOINT,
        )
        if send_order_resp.get(CONSTANTS.ERROR_CODE_FIELD):
            raise IOError(f"Error submitting order {order_id}: {send_order_resp[CONSTANTS.ERROR_MSG_FIELD]}")
        return str(send_order_resp[CONSTANTS.ORDER_ID_FIELD]), self.current_timestamp

    async def _update_trading_fees(self):
        pass

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                endpoint = event_message[CONSTANTS.MSG_ENDPOINT_FIELD]
                payload = event_message[CONSTANTS.MSG_DATA_FIELD]

                if endpoint == CONSTANTS.WS_ACC_POS_EVENT:
                    self._process_account_position_event(payload)
                elif endpoint == CONSTANTS.WS_ORDER_STATE_EVENT:
                    order = self._order_tracker.all_updatable_orders.get(str(payload[CONSTANTS.CLIENT_ORDER_ID_FIELD]))
                    if order is not None:
                        order_update = self._create_order_update(order_msg=payload, order=order)
                        self._order_tracker.process_order_update(order_update)
                elif endpoint == CONSTANTS.WS_ORDER_TRADE_EVENT:
                    order = self._order_tracker.all_fillable_orders.get(str(payload[CONSTANTS.CLIENT_ORDER_ID_FIELD]))
                    if order is not None:
                        trade_update = self._create_trade_update(trade_event=payload, order=order)
                        self._order_tracker.process_trade_update(trade_update)
                elif endpoint == CONSTANTS.WS_CANCEL_ORDER_REJECTED_EVENT:
                    pass
                else:
                    self.logger().debug(f"Unknown event received from the connector ({event_message})")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _update_trading_rules(self):
        # This has to be reimplemented because the request requires an extra parameter
        exchange_info = await self._api_get(
            path_url=self.trading_rules_request_path,
            params={CONSTANTS.OMS_ID_FIELD: self.oms_id},
        )
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]):
        trading_rules = []

        for info in raw_trading_pair_info:
            try:
                if is_exchange_information_valid(exchange_info=info):
                    instrument_id = info[CONSTANTS.INSTRUMENT_ID_FIELD]
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(str(instrument_id))
                    trading_rules.append(
                        TradingRule(
                            trading_pair=trading_pair,
                            min_order_size=Decimal(str(info[CONSTANTS.MIN_QUANT_FIELD])),
                            min_price_increment=Decimal(str(info[CONSTANTS.MIN_PRICE_INCR_FIELD])),
                            min_base_amount_increment=Decimal(str(info[CONSTANTS.MIN_QUANT_INCR_FIELD])),
                        )
                    )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {info}. Skipping.")

        return trading_rules

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        instrument_id = await self.exchange_symbol_associated_to_pair(trading_pair)
        params = {
            CONSTANTS.OMS_ID_FIELD: self.oms_id,
            CONSTANTS.INSTRUMENT_ID_FIELD: instrument_id,
        }
        response = await self._api_request(
            path_url=CONSTANTS.REST_GET_L1_ENDPOINT, params=params
        )
        return response[CONSTANTS.LAST_TRADED_PRICE_FIELD]

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        await self._ensure_authenticated()

        params = {
            CONSTANTS.OMS_ID_FIELD: self.oms_id,
            CONSTANTS.ACCOUNT_ID_FIELD: self._auth.account_id,
        }
        account_positions: List[Dict[str, Any]] = await self._api_request(
            path_url=CONSTANTS.REST_ACC_POSITIONS_ENDPOINT,
            params=params,
            is_auth_required=True,
        )
        for position in account_positions:
            self._process_account_position_event(position)
            token = position[CONSTANTS.PRODUCT_SYMBOL_FIELD]
            remote_asset_names.add(token)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)
            params = {
                CONSTANTS.OMS_ID_FIELD: self.oms_id,
                CONSTANTS.ACCOUNT_ID_FIELD: self._auth.account_id,
                CONSTANTS.USER_ID_FIELD: self._auth.user_id,
                CONSTANTS.ORDER_ID_FIELD: exchange_order_id
            }

            all_fills_response = await self._api_request(
                path_url=CONSTANTS.REST_TRADE_HISTORY_ENDPOINT,
                params=params,
                is_auth_required=True,
            )

            for trade in all_fills_response:  # trades must be handled before order status updates
                trade_update = self._create_trade_update(trade_event=trade, order=order)
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        params = {
            CONSTANTS.OMS_ID_FIELD: self.oms_id,
            CONSTANTS.ACCOUNT_ID_FIELD: self._auth.account_id,
            CONSTANTS.ORDER_ID_FIELD: int(exchange_order_id),
        }
        updated_order_data = await self._api_request(
            path_url=CONSTANTS.REST_ORDER_STATUS_ENDPOINT,
            params=params,
            is_auth_required=True,
        )

        order_update = self._create_order_update(order_msg=updated_order_data, order=tracked_order)

        return order_update

    async def _validate_status_responses(
        self, status_responses: List[Dict[str, Any]], associated_orders: List[InFlightOrder]
    ) -> List[Dict[str, Any]]:
        validated_responses: List[Dict[str, Any]] = []
        for resp, order in zip(status_responses, associated_orders):
            if resp.get(CONSTANTS.ERROR_CODE_FIELD):
                self.logger().error(f"Error fetching order status. Response: {resp}")
                await self._order_tracker.process_order_not_found(order.client_order_id)
            else:
                validated_responses.append(resp)
        return validated_responses

    def _process_account_position_event(self, account_position_event: Dict[str, Any]):
        token = account_position_event[CONSTANTS.PRODUCT_SYMBOL_FIELD]
        amount = Decimal(str(account_position_event[CONSTANTS.AMOUNT_FIELD]))
        on_hold = Decimal(str(account_position_event[CONSTANTS.AMOUNT_ON_HOLD_FIELD]))
        self._account_balances[token] = amount
        self._account_available_balances[token] = (amount - on_hold)

    def _create_order_update(self, order_msg: Dict[str, Any], order: InFlightOrder):
        status_from_update = order_msg[CONSTANTS.ORDER_STATE_FIELD]
        if status_from_update == CONSTANTS.ACTIVE_ORDER_STATE:
            filled_amount = order_msg[CONSTANTS.QUANTITY_EXECUTED_FIELD]
            if filled_amount != 0:
                order_status = OrderState.PARTIALLY_FILLED
            else:
                order_status = OrderState.OPEN
        else:
            order_status = CONSTANTS.ORDER_STATE_MAP[status_from_update]
        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=order_msg[CONSTANTS.ORDER_UPDATE_TS_FIELD] * 1e-3,
            new_state=order_status,
            client_order_id=order.client_order_id,
            exchange_order_id=str(order_msg[CONSTANTS.ORDER_ID_FIELD]),
        )
        return order_update

    def _create_trade_update(self, trade_event: Dict[str, Any], order: InFlightOrder):
        order_action = trade_event[CONSTANTS.SIDE_FIELD]
        trade_type = CONSTANTS.ORDER_SIDE_MAP[order_action]
        token_asset_id = trade_event[CONSTANTS.FEE_PRODUCT_ID_FIELD]
        fee_amount = Decimal(str(trade_event[CONSTANTS.FEE_AMOUNT_FIELD]))
        fee_token = self._token_id_map[token_asset_id] if fee_amount else order.quote_asset
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=trade_type,
            percent_token=fee_token,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_token)],
        )
        fill_amount = Decimal(str(trade_event[CONSTANTS.QUANTITY_FIELD.capitalize()]))
        fill_price = Decimal(str(trade_event[CONSTANTS.PRICE_FIELD]))
        trade_time = trade_event[CONSTANTS.TRADE_TIME_MS_FIELD]
        trade_update = TradeUpdate(
            trade_id=str(trade_event[CONSTANTS.TRADE_ID_FIELD]),
            client_order_id=order.client_order_id,
            exchange_order_id=str(trade_event[CONSTANTS.ORDER_ID_FIELD]),
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=fill_amount,
            fill_quote_amount=fill_amount * fill_price,
            fill_price=fill_price,
            fill_timestamp=int(trade_time * 1e-3),
        )
        return trade_update

    def _create_web_assistants_factory(self) -> OMSConnectorWebAssistantsFactory:
        """We create a new authenticator to store the new session token."""
        return ap_web_utils.build_api_factory(
            throttler=self._throttler, auth=self.authenticator
        )

    async def _api_request(
        self,
        path_url,
        method: RESTMethod = RESTMethod.GET,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_auth_required: bool = False,
        return_err: bool = False,
        limit_id: Optional[str] = None,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = self._url_creator.get_rest_url(path_url)
        return await rest_assistant.execute_request(
            url=url,
            params=params,
            data=data,
            method=method,
            is_auth_required=is_auth_required,
            return_err=return_err,
            throttler_limit_id=limit_id if limit_id else path_url,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return OMSConnectorAPIOrderBookDataSource(
            self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            url_provider=self._url_creator,
            oms_id=self.oms_id,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return OMSConnectorAPIUserStreamDataSource(self._web_assistants_factory, self._url_creator, self.oms_id)

    async def _initialize_trading_pair_symbol_map(self):
        try:
            params = {CONSTANTS.OMS_ID_FIELD: self.oms_id}
            exchange_info = await self._api_get(path_url=self.trading_pairs_request_path, params=params)
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[Dict[str, Any]]):
        mapping = bidict()
        for symbol_data in filter(is_exchange_information_valid, exchange_info):
            instrument_id = str(symbol_data[CONSTANTS.INSTRUMENT_ID_FIELD])
            trading_pair = combine_to_hb_trading_pair(
                base=symbol_data[CONSTANTS.BASE_FIELD], quote=symbol_data[CONSTANTS.QUOTE_FIELD]
            )
            if instrument_id in mapping:
                self.logger().error(
                    f"Instrument ID {instrument_id} (trading pair {trading_pair}) already present in the map "
                    f"(with trading pair {mapping[instrument_id]})."
                )
                continue
            elif trading_pair in mapping.inverse:
                self.logger().error(
                    f"Trading pair {trading_pair} (instrument ID {instrument_id}) already present in the map "
                    f"(with ID {mapping.inverse[trading_pair]})."
                )
                continue
            mapping[instrument_id] = trading_pair
            base_id = symbol_data[CONSTANTS.BASE_ID_FIELD]
            base_token = symbol_data[CONSTANTS.BASE_FIELD]
            self._token_id_map[base_id] = base_token
            quote_id = symbol_data[CONSTANTS.QUOTE_ID_FIELD]
            quote_token = symbol_data[CONSTANTS.QUOTE_FIELD]
            self._token_id_map[quote_id] = quote_token
        self._set_trading_pair_symbol_map(mapping)

    async def _ensure_authenticated(self):
        if not self._auth.initialized:
            await self._authenticate()

    async def _authenticate(self):
        auth_headers = self._auth.get_rest_auth_headers()
        url = self._url_creator.get_rest_url(CONSTANTS.REST_AUTH_ENDPOINT)
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()

        auth_response = await rest_assistant.execute_request(
            url,
            throttler_limit_id=CONSTANTS.REST_AUTH_ENDPOINT,
            headers=auth_headers
        )

        auth_success = self._auth.validate_rest_auth(auth_response)
        if auth_success:
            self._auth.update_with_rest_response(auth_response)
        else:
            raise IOError("Failed to authenticate.")
