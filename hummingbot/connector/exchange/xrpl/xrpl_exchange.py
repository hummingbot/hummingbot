import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple, Union

from bidict import bidict

# XRPL Imports
from xrpl.asyncio.clients import AsyncWebsocketClient

# from xrpl.transaction import autofill_and_sign
from xrpl.asyncio.transaction import autofill_and_sign, submit
from xrpl.clients import WebsocketClient
from xrpl.models import (
    XRP,
    AccountInfo,
    AccountObjects,
    AccountTx,
    IssuedCurrency,
    Memo,
    OfferCancel,
    OfferCreate,
    Ping,
)
from xrpl.models.amounts import Amount
from xrpl.models.response import ResponseStatus
from xrpl.utils import drops_to_xrp, get_order_book_changes, hex_to_str, ripple_time_to_posix, xrp_to_drops

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source import XRPLAPIOrderBookDataSource
from hummingbot.connector.exchange.xrpl.xrpl_api_user_stream_data_source import XRPLAPIUserStreamDataSource
from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.connector.exchange.xrpl.xrpl_utils import convert_string_to_hex
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class XrplExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    # web_utils = web_utils

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            xrpl_secret_key: str,
            wss_node_url: str,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
    ):
        self._xrpl_secret_key = xrpl_secret_key
        self._wss_node_url = wss_node_url
        self._xrpl_client = AsyncWebsocketClient(self._wss_node_url)
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._auth: XRPLAuth = self.authenticator
        self._trading_pair_symbol_map: Optional[Mapping[str, str]] = None
        self._open_client_lock = asyncio.Lock()

        super().__init__(client_config_map)

    @staticmethod
    def xrpl_order_type(order_type: OrderType) -> str:
        return CONSTANTS.XRPL_ORDER_TYPE[order_type]

    @staticmethod
    def to_hb_order_type(order_type: str) -> OrderType:
        return OrderType[order_type]

    @property
    def authenticator(self) -> XRPLAuth:
        return XRPLAuth(xrpl_secret_key=self._xrpl_secret_key)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return "Not Supported"

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return ""

    @property
    def trading_pairs_request_path(self):
        return ""

    @property
    def check_network_request_path(self):
        return ""

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def node_url(self) -> str:
        return self._wss_node_url

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # API documentation does not clarify the error message for timestamp related problems
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
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        # return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)
        pass

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return XRPLAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return XRPLAPIUserStreamDataSource(
            auth=self._auth,
            connector=self
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
        # TODO: Implement get fee, use the below implementation
        # is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        # trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        # if trading_pair in self._trading_fees:
        #     fees_data = self._trading_fees[trading_pair]
        #     fee_value = Decimal(fees_data["makerFeeRate"]) if is_maker else Decimal(fees_data["takerFeeRate"])
        #     fee = AddedToCostTradeFee(percent=fee_value)

        # TODO: Remove this fee implementation
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
            **kwargs,
    ) -> Tuple[str, float]:
        base_currency, quote_currency = await self.get_currencies_from_trading_pair(trading_pair)

        if order_type is OrderType.MARKET:
            # If price is none or nan, get last_traded_price
            if price is None or price.is_nan():
                price = await self._get_last_traded_price(trading_pair)
            # Increase price by MARKET_ORDER_MAX_SLIPPAGE if it is buy order
            # Decrease price by MARKET_ORDER_MAX_SLIPPAGE if it is sell order
            if trade_type is TradeType.BUY:
                price *= 1 + CONSTANTS.MARKET_ORDER_MAX_SLIPPAGE
            else:
                price *= 1 - CONSTANTS.MARKET_ORDER_MAX_SLIPPAGE

        account = self._auth.get_account()
        total_amount = amount * price

        if trade_type is TradeType.SELL:
            if base_currency.currency == XRP().currency:
                we_pay = xrp_to_drops(amount)
            else:
                we_pay = Amount(
                    currency=base_currency.currency,
                    issuer=base_currency.issuer,
                    value=str(amount)
                )

            if quote_currency.currency == XRP().currency:
                we_get = xrp_to_drops(total_amount)
            else:
                we_get = Amount(
                    currency=quote_currency.currency,
                    issuer=quote_currency.issuer,
                    value=str(total_amount))
        else:
            if quote_currency.currency == XRP().currency:
                we_pay = xrp_to_drops(total_amount)
            else:
                we_pay = Amount(
                    currency=quote_currency.currency,
                    issuer=quote_currency.issuer,
                    value=str(total_amount)
                )

            if base_currency.currency == XRP().currency:
                we_get = xrp_to_drops(amount)
            else:
                we_get = Amount(
                    currency=base_currency.currency,
                    issuer=base_currency.issuer,
                    value=str(amount))

        flags = CONSTANTS.XRPL_ORDER_TYPE[order_type]
        memo = Memo(
            memo_data=convert_string_to_hex(order_id, padding=False),
        )
        request = OfferCreate(
            account=account,
            flags=flags,
            taker_gets=we_pay,
            taker_pays=we_get,
            memos=[memo]
        )

        try:
            async with self._open_client_lock:
                async with self._xrpl_client as client:
                    signed_tx = await autofill_and_sign(request, client, self._auth.get_wallet())
                    o_id = f"{signed_tx.sequence}-{signed_tx.last_ledger_sequence}"
                    await submit(signed_tx, client)
                    transact_time = time.time()
                    # Temp fix to wait for order to be processed
                    await self.sleep(0.3)
        except Exception as e:
            new_state = OrderState.FAILED
            o_id = "UNKNOWN"

            order_update = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=time.time(),
                new_state=new_state,
                client_order_id=order_id,
            )
            self._order_tracker.process_order_update(order_update=order_update)
            self.logger().error(
                f"Order ({order_id}) creation failed: {e}")
            return o_id, order_update.update_timestamp

        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = tracked_order.exchange_order_id
        sequence, _ = exchange_order_id.split('-')

        request = OfferCancel(
            account=self._auth.get_account(),
            sequence=int(sequence),
        )

        try:
            async with self._open_client_lock:
                async with self._xrpl_client as client:
                    signed_tx = await autofill_and_sign(request, client, self._auth.get_wallet())
                    await submit(signed_tx, client)
                    # Temp fix to wait for order to be processed
                    await self.sleep(0.3)
        except Exception as e:
            self.logger().error(f"Order cancellation failed: {e}")
            return False

        return True

    async def _format_trading_rules(self, trading_rules_info: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []
        for trading_pair, trading_pair_info in trading_rules_info.items():
            base_tick_size = trading_pair_info["base_tick_size"]
            quote_tick_size = trading_pair_info["quote_tick_size"]
            minimum_order_size = trading_pair_info["minimum_order_size"]

            trading_rule = TradingRule(
                trading_pair=trading_pair,
                min_order_size=Decimal(f"1e-{minimum_order_size}"),
                min_price_increment=Decimal(f"1e-{quote_tick_size}"),
                min_quote_amount_increment=Decimal(f"1e-{quote_tick_size}"),
                min_base_amount_increment=Decimal(f"1e-{base_tick_size}"),
                min_notional_size=Decimal(f"1e-{quote_tick_size}"))

            trading_rules.append(trading_rule)

        return trading_rules

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
                # TODO: Implement user stream event listener
                pass
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # TODO: Implement trade updates for order
        pass

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        async with self._open_client_lock:
            async with self._xrpl_client as client:
                new_order_state = tracked_order.current_state
                latest_status = "UNKNOWN"

                sequence, ledger_index = tracked_order.exchange_order_id.split('-')

                request = AccountTx(
                    account=self._auth.get_account(),
                    ledger_index="validated",
                    ledger_index_min=int(ledger_index),
                    forward=True,
                )

                resp = await client.request(request)
                transactions = resp.result.get("transactions", [])
                latest_transaction = transactions[0]
                meta = latest_transaction.get("meta", {})
                changes_array = get_order_book_changes(meta)
                # Filter out change that is not from this account
                changes_array = [x for x in changes_array if
                                 x.get("maker_account") == self._auth.get_account()]

                for offer_change in changes_array:
                    changes = offer_change.get("offer_changes", [])

                    for change in changes:
                        if change.get("sequence") == sequence:
                            tx = latest_transaction.get("tx")
                            update_time = tx.get("date")
                            update_timestamp = ripple_time_to_posix(update_time)
                            latest_status = change.get('status')

                if latest_status == "UNKNOWN":
                    new_order_state = OrderState.FAILED
                    update_timestamp = time.time()
                    self.logger().error(
                        f"Order status not found for order {tracked_order.client_order_id} ({sequence})")
                elif latest_status == "filled":
                    new_order_state = OrderState.FILLED
                elif latest_status == "partially-filled":
                    new_order_state = OrderState.PARTIALLY_FILLED
                elif latest_status == "canceled":
                    new_order_state = OrderState.CANCELED
                elif latest_status == "created":
                    new_order_state = OrderState.OPEN

                order_update = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=update_timestamp,
                    new_state=new_order_state,
                )

                return order_update

    async def _update_balances(self):
        account_address = self._auth.get_account()

        async with self._xrpl_client as client:
            account_info = await client.request(AccountInfo(
                account=account_address,
                ledger_index="validated",
            ))
            objects = await client.request(AccountObjects(
                account=account_address,
            ))
            open_offers = [x for x in objects.result.get("account_objects", []) if x.get("LedgerEntryType") == "Offer"]
            balances = [x.get('Balance') for x in objects.result.get("account_objects", []) if
                        x.get("LedgerEntryType") == "RippleState"]

            xrp_balance = account_info.result.get("account_data", {}).get("Balance", '0')
            total_xrp = drops_to_xrp(xrp_balance)
            total_ledger_objects = len(objects.result.get("account_objects", []))
            fixed_wallet_reserve = 10
            available_xrp = total_xrp - fixed_wallet_reserve - total_ledger_objects * 2

            account_balances = {
                "XRP": Decimal(total_xrp),
            }

            # update balance for each token
            for balance in balances:
                currency = balance.get("currency")
                if len(currency) > 3:
                    currency = hex_to_str(currency)

                token = currency.strip('\x00')
                amount = balance.get("value")
                account_balances[token] = Decimal(amount)

            account_available_balances = account_balances.copy()
            account_available_balances["XRP"] = Decimal(available_xrp)

            for offer in open_offers:
                taker_gets = offer.get("TakerGets")
                if isinstance(taker_gets, dict):
                    token = taker_gets.get("currency")
                    if len(token) > 3:
                        token = hex_to_str(token).strip('\x00')
                    amount = Decimal(taker_gets.get("value"))
                else:
                    amount = drops_to_xrp(taker_gets)
                    token = 'XRP'

                account_available_balances[token] -= amount

            self._account_balances = account_balances
            self._account_available_balances = account_available_balances

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        markets = exchange_info.get("markets", {})
        mapping_symbol = bidict()

        for market, info in markets.items():
            self.logger().debug(f"Processing market {market}")
            mapping_symbol[market.upper()] = combine_to_hb_trading_pair(
                base=info["base"].upper(), quote=info["quote"].upper()
            )
        self._set_trading_pair_symbol_map(mapping_symbol)

    def _set_trading_pair_symbol_map(self, trading_pair_and_symbol_map: Optional[Mapping[str, str]]):
        """
        Method added to allow the pure Python subclasses to set the value of the map
        """
        self._trading_pair_symbol_map = trading_pair_and_symbol_map

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        last_price = self.order_books.get(trading_pair).last_trade_price

        return last_price

    def buy(
            self, trading_pair: str, amount: Decimal, order_type=OrderType.LIMIT, price: Decimal = s_decimal_NaN,
            **kwargs
    ) -> str:
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

        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return order_id

    def sell(
            self,
            trading_pair: str,
            amount: Decimal,
            order_type: OrderType = OrderType.LIMIT,
            price: Decimal = s_decimal_NaN,
            **kwargs,
    ) -> str:
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
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return order_id

    async def _update_trading_rules(self):
        trading_rules_info = await self._make_trading_rules_request()
        trading_rules_list = await self._format_trading_rules(trading_rules_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

        exchange_info = await self._make_trading_pairs_request()
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _initialize_trading_pair_symbol_map(self):
        try:
            exchange_info = await self._make_trading_pairs_request()
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception as e:
            self.logger().exception(f"There was an error requesting exchange info: {e}")

    async def _make_network_check_request(self):
        with WebsocketClient(self.node_url) as client:
            client.request(Ping())

    async def _make_trading_rules_request(self) -> Dict[str, Any]:
        zeroTransferRate = 1000000000
        trading_rules_info = {}

        async with self._xrpl_client as client:
            for trading_pair in self._trading_pairs:
                base_currency, quote_currency = await self.get_currencies_from_trading_pair(trading_pair)

                if base_currency.currency == XRP().currency:
                    baseTickSize = 6
                    baseTransferRate = 0
                else:
                    base_info = await client.request(AccountInfo(
                        account=base_currency.issuer,
                        ledger_index="validated",
                    ))

                    if base_info.status == ResponseStatus.ERROR:
                        error_message = base_info.result.get("error_message")
                        raise ValueError(f"Base currency {base_currency} not found in ledger: {error_message}")

                    baseTickSize = base_info.result.get("account_data", {}).get("TickSize", 15)
                    rawTransferRate = base_info.result.get("account_data", {}).get("TransferRate", zeroTransferRate)
                    baseTransferRate = float(rawTransferRate / zeroTransferRate) - 1

                if quote_currency.currency == XRP().currency:
                    quoteTickSize = 6
                    quoteTransferRate = 0
                else:
                    quote_info = await client.request(AccountInfo(
                        account=quote_currency.issuer,
                        ledger_index="validated",
                    ))

                    if quote_info.status == ResponseStatus.ERROR:
                        error_message = quote_info.result.get("error_message")
                        raise ValueError(f"Quote currency {quote_currency} not found in ledger: {error_message}")

                    quoteTickSize = quote_info.result.get("account_data", {}).get("TickSize", 15)
                    rawTransferRate = quote_info.result.get("account_data", {}).get("TransferRate", zeroTransferRate)
                    quoteTransferRate = float(rawTransferRate / zeroTransferRate) - 1

                if baseTickSize is None or quoteTickSize is None:
                    raise ValueError(f"Tick size not found for trading pair {trading_pair}")

                if baseTransferRate is None or quoteTransferRate is None:
                    raise ValueError(f"Transfer rate not found for trading pair {trading_pair}")

                smallestTickSize = min(baseTickSize, quoteTickSize)
                minimumOrderSize = float(10) ** -smallestTickSize

                trading_rules_info[trading_pair] = {
                    "base_currency": base_currency,
                    "quote_currency": quote_currency,
                    "base_tick_size": baseTickSize,
                    "quote_tick_size": quoteTickSize,
                    "base_transfer_rate": baseTransferRate,
                    "quote_transfer_rate": quoteTransferRate,
                    "minimum_order_size": minimumOrderSize
                }

        return trading_rules_info

    async def _make_trading_pairs_request(self) -> [Dict[str, Any]]:
        markets = CONSTANTS.MARKETS
        return {"markets": markets}

    async def get_currencies_from_trading_pair(self, trading_pair: str) -> (
            Tuple)[Union[IssuedCurrency, XRP], Union[IssuedCurrency, XRP]]:
        # Find market in the markets list
        # TODO: Create a markets list that load from constant file and config file
        market = CONSTANTS.MARKETS.get(trading_pair, None)

        if market is None:
            raise ValueError(f"Market {trading_pair} not found in markets list")

        # Get all info
        base = market.get("base")
        base_issuer = market.get("base_issuer")
        quote = market.get("quote")
        quote_issuer = market.get("quote_issuer")

        if base == "XRP":
            base_currency = XRP()
        else:
            formatted_base = convert_string_to_hex(base)
            base_currency = IssuedCurrency(currency=formatted_base, issuer=base_issuer)

        if quote == "XRP":
            quote_currency = XRP()
        else:
            formatted_quote = convert_string_to_hex(quote)
            quote_currency = IssuedCurrency(currency=formatted_quote, issuer=quote_issuer)

        return base_currency, quote_currency
