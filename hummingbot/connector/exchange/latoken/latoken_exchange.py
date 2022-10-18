import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

import ujson
from bidict import bidict

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
import hummingbot.connector.exchange.latoken.latoken_web_utils as web_utils
from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.latoken.latoken_api_order_book_data_source import LatokenAPIOrderBookDataSource
from hummingbot.connector.exchange.latoken.latoken_api_user_stream_data_source import LatokenAPIUserStreamDataSource
from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from hummingbot.connector.exchange.latoken.latoken_utils import LatokenCommissionType, LatokenFeeSchema, LatokenTakeType
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import (
    AddedToCostTradeFee,
    DeductedFromReturnsTradeFee,
    TokenAmount,
    TradeFeeBase,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class LatokenExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 latoken_api_key: str,
                 latoken_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN
                 ):

        self._domain = domain  # it is required to have this placed before calling super (why not as params to ctor?)
        self._api_key = latoken_api_key
        self._secret_key = latoken_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._authenticator = None
        super().__init__(client_config_map)

    @staticmethod
    def latoken_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(latoken_type: str) -> OrderType:
        return OrderType[latoken_type]

    @property
    def authenticator(self):
        if self._authenticator is None:
            self._authenticator = LatokenAuth(
                api_key=self._api_key, secret_key=self._secret_key, time_provider=self._time_synchronizer)
        return self._authenticator

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def name(self) -> str:
        return "latoken" if self.domain == CONSTANTS.DEFAULT_DOMAIN else f"latoken_{self.domain}"

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.PAIR_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.TICKER_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self) -> Optional[List[str]]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # API documentation does not clarify the error message for timestamp related problems
        return False

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        cancel_result = await self._api_post(
            path_url=CONSTANTS.ORDER_CANCEL_PATH_URL, params={"id": exchange_order_id}, is_auth_required=True)
        return cancel_result["status"] == "SUCCESS"

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        """
        Creates a an order in the exchange using the parameters to configure it
        :param trade_type: the side of the order (BUY of SELL)
        :param order_id: the id that should be assigned to the order (the client id)
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        quantized_price = self.quantize_order_price(trading_pair=trading_pair, price=price)
        quantize_amount_price = Decimal("0") if quantized_price.is_nan() else quantized_price
        quantized_amount = self.quantize_order_amount(
            trading_pair=trading_pair, amount=amount, price=quantize_amount_price)
        price_str = f"{quantized_price:f}"
        amount_str = f"{quantized_amount:f}"
        type_str = self.latoken_order_type(order_type=order_type)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL

        if type_str == OrderType.LIMIT_MAKER.name:
            self.logger().error('LIMIT_MAKER order not supported by Latoken, use LIMIT instead')

        base, quote = symbol.split('/')
        api_params = {
            'baseCurrency': base,
            'quoteCurrency': quote,
            "side": side_str,
            "clientOrderId": order_id,
            "quantity": amount_str,
            "type": OrderType.LIMIT.name,
            "price": price_str,
            "timestamp": int(self.current_timestamp * 1000),
            'condition': CONSTANTS.TIME_IN_FORCE_GTC
        }

        order_result = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params=api_params,
            is_auth_required=True)

        if order_result["status"] == "SUCCESS":
            exchange_order_id = str(order_result["id"])
            return exchange_order_id, self.current_timestamp
        else:
            raise ValueError(f"Place order failed, no SUCCESS message {order_result}")

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        """
        Calculates the estimated fee an order would pay based on the connector configuration
        :param base_currency: the order base currency
        :param quote_currency: the order quote currency
        :param order_type: the type of order (MARKET, LIMIT, LIMIT_MAKER)
        :param order_side: if the order is for buying or selling
        :param amount: the order amount
        :param price: the order price
        :param is_maker: if we take into account maker fee (True) or taker fee (None, False)
        :return: the estimated fee for the order
        """
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        fee_schema = self._trading_fees.get(trading_pair, None)
        if fee_schema is None:
            self.logger().warning(f"For trading pair = {trading_pair} there is no fee schema loaded, using presets!")
            fee = build_trade_fee(
                exchange=self.name,
                is_maker=is_maker,
                base_currency=base_currency,
                quote_currency=quote_currency,
                order_type=order_type,
                order_side=order_side,
                amount=amount,
                price=price)
        else:
            if fee_schema.type == LatokenTakeType.PROPORTION or fee_schema.take == LatokenCommissionType.PERCENT:
                pass  # currently not implemented but is nice to have in next release(s)
            percent = fee_schema.maker_fee if order_type is OrderType.LIMIT_MAKER or (
                is_maker is not None and is_maker) else fee_schema.taker_fee
            fee = AddedToCostTradeFee(
                percent=percent) if order_side == TradeType.BUY else DeductedFromReturnsTradeFee(percent=percent)
        return fee

    async def _update_trading_fees(self):
        fee_requests = [self._api_get(
            path_url=f"{CONSTANTS.FEES_PATH_URL}/{trading_pair.replace('-', '/')}",
            is_auth_required=True, limit_id=CONSTANTS.FEES_PATH_URL) for trading_pair in self.trading_pairs]
        responses = zip(self.trading_pairs, await safe_gather(*fee_requests, return_exceptions=True))
        for trading_pair, response in responses:
            self._trading_fees[trading_pair] = None if isinstance(response, Exception) else LatokenFeeSchema(fee_schema=response)

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                cmd = event_message.get('cmd', None)
                if cmd and cmd == 'MESSAGE':
                    subscription_id = int(event_message['headers']['subscription'].split('_')[0])
                    payload = ujson.loads(event_message["body"])["payload"]

                    if subscription_id == CONSTANTS.SUBSCRIPTION_ID_ACCOUNT:
                        await self._process_account_balance_update(balances=payload)
                    elif subscription_id == CONSTANTS.SUBSCRIPTION_ID_ORDERS:
                        for update in payload:
                            await self._process_order_update(order=update)
                    elif subscription_id == CONSTANTS.SUBSCRIPTION_ID_TRADE_UPDATE:
                        for update in payload:
                            await self._process_trade_update(trade=update)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _format_trading_rules(self, pairs_list: List[Any]) -> List[TradingRule]:
        """
        Example: https://api.latoken.com/doc/v2/#tag/Pair
        [
            {
            "id": "263d5e99-1413-47e4-9215-ce4f5dec3556",
            "status": "PAIR_STATUS_ACTIVE",
            "baseCurrency": "6ae140a9-8e75-4413-b157-8dd95c711b23",
            "quoteCurrency": "23fa548b-f887-4f48-9b9b-7dd2c7de5ed0",
            "priceTick": "0.010000000",
            "priceDecimals": 2,
            "quantityTick": "0.010000000",
            "quantityDecimals": 2,
            "costDisplayDecimals": 3,
            "created": 1571333313871,
            "minOrderQuantity": "0",
            "maxOrderCostUsd": "999999999999999999",
            "minOrderCostUsd": "0",
            "externalSymbol": ""
            }
        ]
        """

        await self._initialize_trading_pair_symbol_map()  # workaround for trading_rule path in _update_trading_rules

        trading_rules = []
        for rule in pairs_list:
            if rule['status'] != 'PAIR_STATUS_ACTIVE':
                continue

            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                    symbol=f"{rule['baseCurrency']}/{rule['quoteCurrency']}")

                min_order_size = Decimal(rule["minOrderQuantity"])
                price_tick = Decimal(rule["priceTick"])
                quantity_tick = Decimal(rule["quantityTick"])
                min_order_value = Decimal(rule["minOrderCostUsd"])
                min_order_quantity = Decimal(rule["minOrderQuantity"])

                trading_rule = TradingRule(
                    trading_pair,
                    min_order_size=max(min_order_size, quantity_tick),
                    min_price_increment=price_tick,
                    min_base_amount_increment=quantity_tick,
                    min_quote_amount_increment=price_tick,
                    min_notional_size=min_order_quantity,
                    min_order_value=min_order_value,
                    # max_price_significant_digits=len(rule["maxOrderCostUsd"])
                    supports_market_orders=False,
                )

                trading_rules.append(trading_rule)
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return trading_rules

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # This has to be implemented to bring Latoken up to the latest standards
        return []

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        updated_order_data = await self._api_get(
            path_url=f"{CONSTANTS.GET_ORDER_PATH_URL}/{exchange_order_id}",
            is_auth_required=True,
            limit_id=CONSTANTS.GET_ORDER_PATH_URL)

        status = updated_order_data["status"]
        filled = Decimal(updated_order_data["filled"])
        quantity = Decimal(updated_order_data["quantity"])

        new_state = web_utils.get_order_status_rest(status=status, filled=filled, quantity=quantity)

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=updated_order_data["id"],
            trading_pair=tracked_order.trading_pair,
            update_timestamp=float(updated_order_data["timestamp"]) * 1e-3,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        try:
            params = {'zeros': 'false'}  # if not testing this can be set to the default of false
            balances = await self._api_get(path_url=CONSTANTS.ACCOUNTS_PATH_URL, is_auth_required=True, params=params)
            remote_asset_names = await self._process_account_balance_update(balances=balances)
            self._process_full_account_balances_refresh(remote_asset_names=remote_asset_names, balances=balances)
        except IOError:
            self.logger().exception("Error getting account balances from server")

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self.domain,
            auth=self.authenticator)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LatokenAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LatokenAPIUserStreamDataSource(
            auth=self.authenticator,
            trading_pairs=self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _process_account_balance_update(self, balances: List[Dict[str, Any]]) -> Set[str]:
        remote_asset_names = set()

        balance_to_gather = [
            self._api_get(path_url=f"{CONSTANTS.CURRENCY_PATH_URL}/{balance['currency']}",
                          limit_id=CONSTANTS.CURRENCY_PATH_URL) for balance in balances]

        # maybe request every currency if len(account_balance) > 5
        currency_lists = await safe_gather(*balance_to_gather, return_exceptions=True)

        currencies = {currency["id"]: currency["tag"] for currency in currency_lists if
                      isinstance(currency, dict) and currency["status"] != 'FAILURE'}

        for balance in balances:
            if balance['status'] == "FAILURE" and balance['error'] == 'NOT_FOUND':
                self.logger().error(f"Could not resolve currency details for balance={balance}")
                continue
            asset_name = currencies.get(balance["currency"], None)
            if asset_name is None or balance["type"] != "ACCOUNT_TYPE_SPOT":
                if asset_name is None:
                    self.logger().error(f"Could not resolve currency details for balance={balance}")
                continue
            free_balance = Decimal(balance["available"])
            total_balance = free_balance + Decimal(balance["blocked"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        return remote_asset_names

    def _process_full_account_balances_refresh(self, remote_asset_names: Set[str], balances: List[Dict[str, Any]]):
        """ use this for rest call and not ws because ws does not send entire account balance list"""
        local_asset_names = set(self._account_balances.keys())
        if not balances:
            self.logger().warning("Fund your latoken account, no balances in your account!")
        has_spot_balances = any(filter(lambda b: b["type"] == "ACCOUNT_TYPE_SPOT", balances))
        if balances and not has_spot_balances:
            self.logger().warning(
                "No latoken SPOT balance! Account has balances but no SPOT balance! Transfer to Latoken SPOT account!")
        # clean-up balances that are not present anymore
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _process_trade_update(self, trade: Dict[str, Any]):
        symbol = f"{trade['baseCurrency']}/{trade['quoteCurrency']}"
        trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=symbol)

        base_currency, quote_currency = trading_pair.split('-')
        trade_type = TradeType.BUY if trade["makerBuyer"] else TradeType.SELL
        timestamp = float(trade["timestamp"]) * 1e-3
        quantity = Decimal(trade["quantity"])
        price = Decimal(trade["price"])
        trade_id = trade["id"]
        exchange_order_id = trade["order"]
        tracked_order = self._order_tracker.fetch_order(exchange_order_id=exchange_order_id)
        client_order_id = tracked_order.client_order_id if tracked_order else None

        absolute_fee = Decimal(trade["fee"])
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(), trade_type=trade_type, percent_token=quote_currency,
            flat_fees=[TokenAmount(amount=absolute_fee, token=quote_currency)])

        trade_update = TradeUpdate(
            trade_id=trade_id,
            exchange_order_id=exchange_order_id,
            client_order_id=client_order_id,
            trading_pair=trading_pair,  # or tracked_order.trading_pair
            fill_timestamp=timestamp,
            fill_price=price,
            fill_base_amount=quantity,
            fill_quote_amount=Decimal(trade["cost"]),
            fee=fee,
        )

        self._order_tracker.process_trade_update(trade_update=trade_update)

    async def _process_order_update(self, order: Dict[str, Any]):
        symbol = f"{order['baseCurrency']}/{order['quoteCurrency']}"
        trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        client_order_id = order['clientOrderId']

        change_type = order['changeType']
        status = order['status']
        quantity = Decimal(order["quantity"])
        filled = Decimal(order['filled'])
        delta_filled = Decimal(order['deltaFilled'])

        state = web_utils.get_order_status_ws(change_type=change_type, status=status, quantity=quantity,
                                              filled=filled, delta_filled=delta_filled)
        if state is None:
            return

        timestamp = float(order["timestamp"]) * 1e-3

        order_update = OrderUpdate(
            trading_pair=trading_pair,
            update_timestamp=timestamp,
            new_state=state,
            client_order_id=client_order_id,
        )

        self._order_tracker.process_order_update(order_update=order_update)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()

        if not exchange_info:
            return

        for ticker in exchange_info:
            exchange_trading_pair = f"{ticker['baseCurrency']}/{ticker['quoteCurrency']}"
            if 'symbol' not in ticker:
                continue  # don't update with trading_rules data, check format_trading_rules for workaround
            base, quote = ticker["symbol"].split('/')
            mapping[exchange_trading_pair] = combine_to_hb_trading_pair(base=base, quote=quote)

        if mapping:
            self._set_trading_pair_symbol_map(mapping)
