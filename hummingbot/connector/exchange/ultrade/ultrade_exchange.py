import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict
from ultrade import Client as UltradeClient

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.ultrade import (
    ultrade_constants as CONSTANTS,
    ultrade_utils,
    ultrade_web_utils as web_utils,
)
from hummingbot.connector.exchange.ultrade.ultrade_api_order_book_data_source import UltradeAPIOrderBookDataSource
from hummingbot.connector.exchange.ultrade.ultrade_api_user_stream_data_source import UltradeAPIUserStreamDataSource
from hummingbot.connector.exchange.ultrade.ultrade_auth import UltradeAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class UltradeExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 ultrade_trading_key: str,
                 ultrade_wallet_address: str,
                 ultrade_mnemonic_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.ultrade_trading_key = ultrade_trading_key
        self.ultrade_wallet_address = ultrade_wallet_address
        self.ultrade_mnemonic_key = ultrade_mnemonic_key
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_ultrade_timestamp = 1.0

        self.available_trading_pairs = None
        self.ultrade_client = self.create_ultrade_client()
        self._ultrade_conversion_rules: Optional[Dict[str, int]] = {}
        self._ultrade_token_address_asset_map: Optional[Dict[str, str]] = {}
        self._ultrade_token_id_asset_map: Optional[Dict[int, str]] = {}
        self._ultrade_pair_symbol_to_pair_id_map: Optional[Dict[str, int]] = {}
        super().__init__(client_config_map)

    def create_ultrade_client(self) -> UltradeClient:
        client = UltradeClient(network=self._domain)
        client.set_trading_key(
            trading_key=self.ultrade_trading_key,
            address=self.ultrade_wallet_address,
            trading_key_mnemonic=self.ultrade_mnemonic_key
        )
        return client

    @staticmethod
    def ultrade_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(ultrade_type: str) -> OrderType:
        return OrderType[ultrade_type]

    @property
    def authenticator(self):
        return UltradeAuth(
            trading_key=self.ultrade_trading_key,
            wallet_address=self.ultrade_wallet_address,
            mnemonic_key=self.ultrade_mnemonic_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "mainnet":
            return "ultrade"
        else:
            return f"ultrade_{self._domain}"

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
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_BOOK_PATH_URL)
        return pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return any(msg in str(status_update_exception) for msg in CONSTANTS.ORDER_NOT_EXIST_MESSAGES)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return any(msg in str(cancelation_exception) for msg in CONSTANTS.UNKNOWN_ORDER_MESSAGES)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return UltradeAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return UltradeAPIUserStreamDataSource(
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
        order_result = None
        base, quote = list(map(lambda x: x, trading_pair.split("-")))

        # this is for ensuring we have conversion rules for the amount and price
        await self.trading_pair_symbol_map()

        amount_int = self.to_fixed_point(base, amount)
        price_int = self.to_fixed_point(quote, price)
        if order_type == OrderType.LIMIT:
            type_str = "L"
        elif order_type == OrderType.LIMIT_MAKER:
            type_str = "P"  # this is hummingsim's limit maker order type
        elif order_type == OrderType.MARKET:
            type_str = "M"
        else:
            raise ValueError(f"Unsupported order type {order_type}")

        side_str = "B" if trade_type is TradeType.BUY else "S"
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        pair_id = self._ultrade_pair_symbol_to_pair_id_map[symbol]

        try:
            order_result = await self.ultrade_client.create_order(
                pair_id=pair_id,
                order_side=side_str,
                order_type=type_str,
                amount=amount_int,
                price=price_int
            )
            exchange_order_id = str(order_result["id"])
            transact_time = self._time_synchronizer.time()
        except IOError as e:
            raise IOError(f"Error placing order on Ultrade: {e}")

        return exchange_order_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = await tracked_order.get_exchange_order_id()
        try:
            cancel_result = await self.ultrade_client.cancel_order(int(exchange_order_id))
        except Exception as e:
            raise e

        if cancel_result is None:
            return True

        self.logger().error(f"Error cancelling order {exchange_order_id} on Ultrade: {cancel_result}")
        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        [
            {
                "base_chain_id": 6,
                "base_currency": "amax",
                "base_decimal": 18,
                "base_id": "0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "base_token_id": 11,
                "created_at": "2024-05-17T12:21:31.997Z",
                "id": 55,
                "is_active": true,
                "min_order_size": "5000000000000000000",
                "min_price_increment": "1000000000000000",
                "min_size_increment": "1000000000000000000",
                "pair_key": "amax_usdc",
                "pair_name": "AMAX_USDC",
                "pairId": 55,
                "price_chain_id": 65537,
                "price_currency": "usdc",
                "price_decimal": 6,
                "price_id": "0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "price_token_id": 20,
                "updated_at": "2024-11-22T17:33:56.000Z",
                "inuseWithPartners":
                [
                    1,
                    63,
                    77
                ],
                "restrictedCountries": [],
                "pairSettings": {},
                "partner_id": 210179851,
                "delisting_date": null
            },
            ...
        ]
        """
        trading_pair_rules = exchange_info_dict.get("symbols", [])
        retval = []
        for rule in filter(ultrade_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("pair_key"))

                base_decimal = int(rule.get("base_decimal"))
                min_order_size = Decimal(rule.get("min_order_size")) / Decimal(10 ** base_decimal)
                min_base_amount_increment = Decimal(rule.get("min_size_increment")) / Decimal(10 ** base_decimal)
                # TODO: get clarification on this. for now, 18 is the default
                min_price_increment = Decimal(rule.get("min_price_increment")) / Decimal(10 ** 18)

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=min_price_increment,
                                min_base_amount_increment=min_base_amount_increment))

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
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("event")
                # Refer to https://github.com/ultrade-org/ultrade-python-sdk/blob/master/ultrade/socket_client.py
                if event_type == CONSTANTS.USER_ORDER_EVENT_TYPE:
                    update_type, order_data = event_message.get("data")
                    exchange_order_id = str(order_data[3])
                    tracked_order = next((order for order in self._order_tracker.all_updatable_orders.values() if order.exchange_order_id == exchange_order_id), None)

                    if tracked_order is None:
                        continue
                    if update_type == "add":
                        new_state = OrderState.OPEN
                    elif update_type == "update":
                        status_code = int(order_data[4])
                        if status_code == 1:
                            new_state = OrderState.OPEN
                        elif status_code == 2:
                            new_state = OrderState.CANCELED
                        elif status_code == 3 or status_code == 4:
                            new_state = OrderState.FILLED
                    elif update_type == "cancel":
                        new_state = OrderState.CANCELED
                    order_update = OrderUpdate(
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=self._time_synchronizer.time(),
                        new_state=new_state,
                        client_order_id=exchange_order_id,
                        exchange_order_id=exchange_order_id,
                    )
                    self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == CONSTANTS.USER_TRADE_EVENT_TYPE:
                    trade_data = event_message.get("data")

                    if trade_data[11].upper() != "CONFIRMED" or Decimal(trade_data[7]) == 0:
                        continue
                    exchange_order_id = str(trade_data[3])
                    tracked_order = next((order for order in self._order_tracker.all_fillable_orders.values() if order.exchange_order_id == exchange_order_id), None)

                    if tracked_order is None:
                        continue
                    fee_token = self._ultrade_token_id_asset_map.get(int(trade_data[13]))
                    fee_amount = Decimal(str(int(trade_data[12]))) / Decimal(str(10 ** int(trade_data[14])))
                    trade_type = TradeType.BUY if trade_data[4] else TradeType.SELL
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=trade_type,
                        percent_token=fee_token,
                        flat_fees=[TokenAmount(amount=fee_amount, token=fee_token)]
                    )
                    base, quote = tracked_order.trading_pair.split("-")
                    fill_price = self.from_fixed_point(quote, int(trade_data[7]))
                    fill_base_amount = self.from_fixed_point(base, int(trade_data[8]))
                    fill_quote_amount = fill_base_amount * fill_price
                    trade_update = TradeUpdate(
                        trade_id=str(trade_data[6]),
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=tracked_order.trading_pair,
                        fee=fee,
                        fill_base_amount=fill_base_amount,
                        fill_quote_amount=fill_quote_amount,
                        fill_price=fill_price,
                        fill_timestamp=self._time_synchronizer.time(),
                    )
                    self._order_tracker.process_trade_update(trade_update)

                elif event_type == CONSTANTS.USER_BALANCE_EVENT_TYPE:
                    balance_data = event_message.get("data", {}).get("data")
                    if balance_data is None:
                        continue
                    asset_name = self._ultrade_token_address_asset_map.get(balance_data.get("tokenAddress").upper())
                    total_balance = self.from_fixed_point(asset=asset_name, value=int(balance_data.get("amount")))
                    locked_balance = self.from_fixed_point(asset=asset_name, value=int(balance_data.get("lockedAmount")))
                    free_balance = total_balance - locked_balance
                    self._account_available_balances[asset_name] = free_balance
                    self._account_balances[asset_name] = total_balance

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)
            trading_pair = order.trading_pair
            all_fills_response = await self.ultrade_client.get_order_by_id(exchange_order_id)

            base, quote = trading_pair.split("-")

            for trade in all_fills_response["trades"]:
                if Decimal(trade.get("price", "0")) == 0 or trade.get("status", "").upper() != "CONFIRMED":
                    continue    # Skip trades with zero price - they are canceled orders
                fee_token = base if trade["isBuyer"] else quote
                fee_amount = self.from_fixed_point(fee_token, int(trade["fee"]))
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=fee_token,
                    flat_fees=[TokenAmount(amount=fee_amount, token=fee_token)]
                )
                fill_base_amount = self.from_fixed_point(base, int(trade["amount"]))
                fill_price = self.from_fixed_point(quote, int(trade["price"]))
                fill_quote_amount = fill_base_amount * fill_price
                trade_update = TradeUpdate(
                    trade_id=str(trade["tradeId"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=fill_base_amount,
                    fill_quote_amount=fill_quote_amount,
                    fill_price=fill_price,
                    fill_timestamp=self._time_synchronizer.time(),
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        updated_order_data = await self.ultrade_client.get_order_by_id(int(exchange_order_id))

        new_state = tracked_order.current_state
        order_status = updated_order_data["status"]
        if order_status == 1:
            if Decimal(updated_order_data.get("filledAmount", "0")) > 0:
                new_state = OrderState.PARTIALLY_FILLED
            else:
                new_state = OrderState.OPEN
        elif order_status == 2:
            new_state = OrderState.CANCELED
        elif order_status == 3 or order_status == 4:
            new_state = OrderState.FILLED

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self._time_synchronizer.time(),
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self.ultrade_client.get_balances()
        await self.trading_pair_symbol_map()

        for balance_entry in account_info:
            asset_name = self._ultrade_token_address_asset_map.get(balance_entry["tokenAddress"].upper())
            total_balance = self.from_fixed_point(asset=asset_name, value=int(balance_entry["amount"]))
            locked_balance = self.from_fixed_point(asset=asset_name, value=int(balance_entry["lockedAmount"]))
            free_balance = total_balance - locked_balance
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        trading_pair_mapping = bidict()
        token_address_asset_mapping = {}
        token_id_asset_mapping = {}
        conversion_rules = {}
        pair_symbol_to_pair_id_map = {}
        for symbol_data in filter(ultrade_utils.is_exchange_information_valid, exchange_info["symbols"]):
            trading_pair_mapping[symbol_data["pair_key"]] = combine_to_hb_trading_pair(base=symbol_data["base_currency"].upper(),
                                                                                       quote=symbol_data["price_currency"].upper())
            token_address_asset_mapping[str(symbol_data["base_id"]).upper()] = symbol_data["base_currency"].upper()
            token_address_asset_mapping[str(symbol_data["price_id"]).upper()] = symbol_data["price_currency"].upper()
            token_id_asset_mapping[int(symbol_data["base_token_id"])] = symbol_data["base_currency"].upper()
            token_id_asset_mapping[int(symbol_data["price_token_id"])] = symbol_data["price_currency"].upper()
            conversion_rules[str(symbol_data["base_currency"]).upper()] = int(symbol_data["base_decimal"])
            conversion_rules[str(symbol_data["price_currency"]).upper()] = int(symbol_data["price_decimal"])
            pair_symbol_to_pair_id_map[symbol_data["pair_key"]] = int(symbol_data["id"])
        self._set_trading_pair_symbol_map(trading_pair_mapping)
        self._ultrade_token_address_asset_map.update(token_address_asset_mapping)
        self._ultrade_token_id_asset_map.update(token_id_asset_mapping)
        self._ultrade_conversion_rules.update(conversion_rules)
        self._ultrade_pair_symbol_to_pair_id_map.update(pair_symbol_to_pair_id_map)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        resp_json = await self.ultrade_client.get_price(symbol)

        return float(resp_json.get("lastPrice", 0))

    def from_fixed_point(self, asset: str, value: int) -> Decimal:
        if asset is None:
            return Decimal(0)
        value = Decimal(str(value)) / Decimal(str(10 ** self._ultrade_conversion_rules[asset]))

        return value

    def to_fixed_point(self, asset: str, value: Decimal) -> int:
        if asset is None:
            return 0
        value = int(Decimal(str(value)) * Decimal(str(10 ** self._ultrade_conversion_rules[asset])))

        return value

    async def _make_network_check_request(self):
        await self.ultrade_client.ping()

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self.ultrade_client.get_pair_list()
        exchange_info = {
            "symbols": exchange_info
        }
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self.ultrade_client.get_pair_list()
        exchange_info = {
            "symbols": exchange_info
        }
        return exchange_info

    async def process_ultrade_order_book(self, order_book: Dict[str, Any]) -> Dict[str, Any]:
        trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=order_book["pair"])

        base, quote = trading_pair.split("-")

        bids = order_book.get("buy", [])
        asks = order_book.get("sell", [])
        for bid in bids:
            bid[0] = float(self.from_fixed_point(quote, int(bid[0])))
            bid[1] = float(self.from_fixed_point(base, int(bid[1])))
        for ask in asks:
            ask[0] = float(self.from_fixed_point(quote, int(ask[0])))
            ask[1] = float(self.from_fixed_point(base, int(ask[1])))

        order_book["bids"] = bids
        order_book["asks"] = asks
        order_book["trading_pair"] = trading_pair

        return order_book
