import asyncio
import math
import time
from asyncio import Lock
from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple, Union

from bidict import bidict

# XRPL Imports
from xrpl.asyncio.clients import AsyncWebsocketClient, Client, XRPLRequestFailureException
from xrpl.asyncio.transaction import sign
from xrpl.core.binarycodec import encode
from xrpl.models import (
    XRP,
    AccountInfo,
    AccountLines,
    AccountObjects,
    AccountTx,
    IssuedCurrency,
    Memo,
    OfferCancel,
    OfferCreate,
    Request,
    SubmitOnly,
    Transaction,
)
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.response import Response, ResponseStatus
from xrpl.utils import (
    drops_to_xrp,
    get_balance_changes,
    get_order_book_changes,
    hex_to_str,
    ripple_time_to_posix,
    xrp_to_drops,
)
from xrpl.wallet import Wallet

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS, xrpl_web_utils
from hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source import XRPLAPIOrderBookDataSource
from hummingbot.connector.exchange.xrpl.xrpl_api_user_stream_data_source import XRPLAPIUserStreamDataSource
from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.connector.exchange.xrpl.xrpl_utils import (
    XRPLMarket,
    _wait_for_final_transaction_outcome,
    autofill,
    convert_string_to_hex,
    get_token_from_changes,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class XrplExchange(ExchangePyBase):
    LONG_POLL_INTERVAL = 60.0

    web_utils = xrpl_web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        xrpl_secret_key: str,
        wss_node_url: str,
        wss_second_node_url: str,
        wss_third_node_url: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        custom_markets: Dict[str, XRPLMarket] = None,
    ):
        self._xrpl_secret_key = xrpl_secret_key
        self._wss_node_url = wss_node_url
        self._wss_second_node_url = wss_second_node_url
        self._wss_third_node_url = wss_third_node_url
        # self._xrpl_place_order_client = AsyncWebsocketClient(self._wss_node_url)
        self._xrpl_query_client = AsyncWebsocketClient(self._wss_second_node_url)
        self._xrpl_order_book_data_client = AsyncWebsocketClient(self._wss_second_node_url)
        self._xrpl_user_stream_client = AsyncWebsocketClient(self._wss_third_node_url)
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._auth: XRPLAuth = self.authenticator
        self._trading_pair_symbol_map: Optional[Mapping[str, str]] = None
        self._trading_pair_fee_rules: Dict[str, Dict[str, Any]] = {}
        self._xrpl_query_client_lock = asyncio.Lock()
        self._xrpl_place_order_client_lock = asyncio.Lock()
        self._xrpl_fetch_trades_client_lock = asyncio.Lock()
        self._nonce_creator = NonceCreator.for_microseconds()
        self._custom_markets = custom_markets or {}
        self._last_clients_refresh_time = 0

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

    @property
    def second_node_url(self) -> str:
        return self._wss_second_node_url

    @property
    def third_node_url(self) -> str:
        return self._wss_third_node_url

    @property
    def user_stream_client(self) -> AsyncWebsocketClient:
        return self._xrpl_user_stream_client

    @property
    def order_book_data_client(self) -> AsyncWebsocketClient:
        return self._xrpl_order_book_data_client

    @property
    def auth(self) -> XRPLAuth:
        return self._auth

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # We do not use time synchronizer in XRPL connector
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        # TODO: this will be important to implement in case that we request an order that is in memory but the update of it wasn't correct
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # TODO: this will be important to implement in case that we request an order that is in memory but the update of it wasn't correct
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        pass

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return XRPLAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs, connector=self, api_factory=self._web_assistants_factory
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return XRPLAPIUserStreamDataSource(auth=self._auth, connector=self)

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
    ) -> tuple[str, float, Response | None]:
        try:
            if price is None or price.is_nan():
                price = Decimal(
                    await self._get_best_price(trading_pair, is_buy=True if trade_type is TradeType.BUY else False)
                )

            if order_type is OrderType.MARKET:
                market = self.order_books.get(trading_pair)

                if market is None:
                    raise ValueError(f"Market {trading_pair} not found in markets list")

                get_price_with_enough_liquidity = market.get_price_for_volume(
                    is_buy=True if trade_type is TradeType.BUY else False,
                    volume=float(amount),  # Make sure we have enough liquidity
                )

                price = Decimal(get_price_with_enough_liquidity.result_price)

                # Adding slippage to make sure we get the order filled and not cross our own offers
                if trade_type is TradeType.SELL:
                    price *= Decimal("1") - CONSTANTS.MARKET_ORDER_MAX_SLIPPAGE
                else:
                    price *= Decimal("1") + CONSTANTS.MARKET_ORDER_MAX_SLIPPAGE

            base_currency, quote_currency = self.get_currencies_from_trading_pair(trading_pair)
            account = self._auth.get_account()
            trading_rule = self._trading_rules[trading_pair]

            amount_in_base_quantum = Decimal(trading_rule.min_base_amount_increment)
            amount_in_quote_quantum = Decimal(trading_rule.min_quote_amount_increment)

            amount_in_base = Decimal(amount.quantize(amount_in_base_quantum, rounding=ROUND_DOWN))
            amount_in_quote = Decimal((amount * price).quantize(amount_in_quote_quantum, rounding=ROUND_DOWN))

            # Count the digit in the base and quote amount
            # If the digit is more than 16, we need to round it to 16
            # This is to prevent the error of "Decimal precision out of range for issued currency value."
            # when the amount is too small
            # TODO: Add 16 to constant as the maximum precision of issued currency is 16
            total_digits_base = len(str(amount_in_base).split(".")[1]) + len(str(amount_in_base).split(".")[0])
            if total_digits_base > 16:
                adjusted_quantum = 16 - len(str(amount_in_base).split(".")[0])
                amount_in_base = Decimal(
                    amount_in_base.quantize(Decimal(f"1e-{adjusted_quantum}"), rounding=ROUND_DOWN)
                )

            total_digits_quote = len(str(amount_in_quote).split(".")[1]) + len(str(amount_in_quote).split(".")[0])
            if total_digits_quote > 16:
                adjusted_quantum = 16 - len(str(amount_in_quote).split(".")[0])
                amount_in_quote = Decimal(
                    amount_in_quote.quantize(Decimal(f"1e-{adjusted_quantum}"), rounding=ROUND_DOWN)
                )
        except Exception as e:
            self.logger().error(f"Error calculating amount in base and quote: {e}")
            raise e

        if trade_type is TradeType.SELL:
            if base_currency.currency == XRP().currency:
                we_pay = xrp_to_drops(amount_in_base)
            else:
                we_pay = IssuedCurrencyAmount(
                    currency=base_currency.currency, issuer=base_currency.issuer, value=str(amount_in_base)
                )

            if quote_currency.currency == XRP().currency:
                we_get = xrp_to_drops(amount_in_quote)
            else:
                we_get = IssuedCurrencyAmount(
                    currency=quote_currency.currency, issuer=quote_currency.issuer, value=str(amount_in_quote)
                )
        else:
            if quote_currency.currency == XRP().currency:
                we_pay = xrp_to_drops(amount_in_quote)
            else:
                we_pay = IssuedCurrencyAmount(
                    currency=quote_currency.currency, issuer=quote_currency.issuer, value=str(amount_in_quote)
                )

            if base_currency.currency == XRP().currency:
                we_get = xrp_to_drops(amount_in_base)
            else:
                we_get = IssuedCurrencyAmount(
                    currency=base_currency.currency, issuer=base_currency.issuer, value=str(amount_in_base)
                )

        flags = CONSTANTS.XRPL_ORDER_TYPE[order_type]

        if trade_type is TradeType.SELL and order_type is OrderType.MARKET:
            flags += CONSTANTS.XRPL_SELL_FLAG

        memo = Memo(
            memo_data=convert_string_to_hex(order_id, padding=False),
        )
        request = OfferCreate(account=account, flags=flags, taker_gets=we_pay, taker_pays=we_get, memos=[memo])

        try:
            retry = 0
            resp: Optional[Response] = None
            verified = False
            submit_data = {}
            o_id = None

            while retry < CONSTANTS.PLACE_ORDER_MAX_RETRY:
                async with self._xrpl_place_order_client_lock:
                    async with AsyncWebsocketClient(self._wss_node_url) as client:
                        filled_tx = await self.tx_autofill(request, client)
                        signed_tx = self.tx_sign(filled_tx, self._auth.get_wallet())
                        o_id = f"{signed_tx.sequence}-{signed_tx.last_ledger_sequence}"
                        submit_response = await self.tx_submit(signed_tx, client)
                        transact_time = time.time()
                        prelim_result = submit_response.result["engine_result"]

                        submit_data = {"transaction": signed_tx, "prelim_result": prelim_result}

                    if prelim_result[0:3] != "tes" and prelim_result != "terQUEUED":
                        error_message = submit_response.result["engine_result_message"]
                        self.logger().error(f"{prelim_result}: {error_message}, data: {submit_response}")
                        raise Exception(f"Failed to place order {order_id} ({o_id})")

                if retry == 0:
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=order_id,
                        exchange_order_id=str(o_id),
                        trading_pair=trading_pair,
                        update_timestamp=transact_time,
                        new_state=OrderState.PENDING_CREATE,
                    )

                    self._order_tracker.process_order_update(order_update)

                verified, resp = await self._verify_transaction_result(submit_data)

                if verified:
                    retry = CONSTANTS.PLACE_ORDER_MAX_RETRY
                else:
                    retry += 1
                    self.logger().info(
                        f"Order placing failed. Retrying in {CONSTANTS.PLACE_ORDER_RETRY_INTERVAL} seconds..."
                    )
                    await self._sleep(CONSTANTS.PLACE_ORDER_RETRY_INTERVAL)

            if resp is None:
                self.logger().error(f"Failed to place order {order_id} ({o_id}), submit_data: {submit_data}")
                raise Exception(f"Failed to place order {order_id} ({o_id})")

            if not verified:
                self.logger().error(
                    f"Failed to verify transaction result for order {order_id} ({o_id}), submit_data: {submit_data}"
                )
                raise Exception(f"Failed to verify transaction result for order {order_id} ({o_id})")

        except Exception as e:
            new_state = OrderState.FAILED
            order_update = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=time.time(),
                new_state=new_state,
                client_order_id=order_id,
            )
            self._order_tracker.process_order_update(order_update=order_update)
            raise Exception(f"Order {o_id} ({order_id}) creation failed: {e}")

        return o_id, transact_time, resp

    async def _place_order_and_process_update(self, order: InFlightOrder, **kwargs) -> str:
        exchange_order_id, update_timestamp, order_creation_resp = await self._place_order(
            order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            amount=order.amount,
            trade_type=order.trade_type,
            order_type=order.order_type,
            price=order.price,
            **kwargs,
        )

        order_update = await self._request_order_status(
            order, creation_tx_resp=order_creation_resp.to_dict().get("result")
        )

        if order_update.new_state in [OrderState.FILLED, OrderState.PARTIALLY_FILLED]:
            trade_update = await self.process_trade_fills(order_creation_resp.to_dict(), order)
            if trade_update is not None:
                self._order_tracker.process_trade_update(trade_update)
            else:
                self.logger().error(
                    f"Failed to process trade fills for order {order.client_order_id} ({order.exchange_order_id}), order state: {order_update.new_state}, data: {order_creation_resp.to_dict()}"
                )

        self._order_tracker.process_order_update(order_update)

        return exchange_order_id

    async def _verify_transaction_result(
        self, submit_data: dict[str, Any], try_count: int = 0
    ) -> tuple[bool, Optional[Response]]:
        transaction: Transaction = submit_data.get("transaction")
        prelim_result = submit_data.get("prelim_result")

        if prelim_result is None:
            self.logger().error("Failed to verify transaction result, prelim_result is None")
            return False, None

        if transaction is None:
            self.logger().error("Failed to verify transaction result, transaction is None")
            return False, None

        try:
            # await self._make_network_check_request()
            resp = await self.wait_for_final_transaction_outcome(transaction, prelim_result)
            return True, resp
        except (TimeoutError, asyncio.exceptions.TimeoutError):
            self.logger().debug(
                f"Verify transaction timeout error, Attempt {try_count + 1}/{CONSTANTS.VERIFY_TRANSACTION_MAX_RETRY}"
            )
            if try_count < CONSTANTS.VERIFY_TRANSACTION_MAX_RETRY:
                await self._sleep(CONSTANTS.VERIFY_TRANSACTION_RETRY_INTERVAL)
                return await self._verify_transaction_result(submit_data, try_count + 1)
            else:
                self.logger().error("Max retries reached. Verify transaction failed due to timeout.")
                return False, None

        except Exception as e:
            # If there is code 429, retry the request
            if "429" in str(e):
                self.logger().debug(
                    f"Verify transaction failed with code 429, Attempt {try_count + 1}/{CONSTANTS.VERIFY_TRANSACTION_MAX_RETRY}"
                )
                if try_count < CONSTANTS.VERIFY_TRANSACTION_MAX_RETRY:
                    await self._sleep(CONSTANTS.VERIFY_TRANSACTION_RETRY_INTERVAL)
                    return await self._verify_transaction_result(submit_data, try_count + 1)
                else:
                    self.logger().error("Max retries reached. Verify transaction failed with code 429.")
                    return False, None

            self.logger().error(f"Submitted transaction failed: {e}")

            return False, None

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = tracked_order.exchange_order_id
        cancel_result = False
        cancel_data = {}
        submit_response = None

        if exchange_order_id is None:
            self.logger().error(f"Unable to cancel order {order_id}, it does not yet have exchange order id")
            return False, {}

        try:
            # await self._client_health_check()
            async with self._xrpl_place_order_client_lock:
                async with AsyncWebsocketClient(self._wss_node_url) as client:
                    sequence, _ = exchange_order_id.split("-")
                    memo = Memo(
                        memo_data=convert_string_to_hex(order_id, padding=False),
                    )
                    request = OfferCancel(account=self._auth.get_account(), offer_sequence=int(sequence), memos=[memo])

                    filled_tx = await self.tx_autofill(request, client)
                    signed_tx = self.tx_sign(filled_tx, self._auth.get_wallet())

                    submit_response = await self.tx_submit(signed_tx, client)
                    prelim_result = submit_response.result["engine_result"]

                if prelim_result is None:
                    raise Exception(
                        f"prelim_result is None for {order_id} ({exchange_order_id}), data: {submit_response}"
                    )

                if prelim_result[0:3] != "tes":
                    error_message = submit_response.result["engine_result_message"]
                    raise Exception(f"{prelim_result}: {error_message}, data: {submit_response}")

                cancel_result = True
                cancel_data = {"transaction": signed_tx, "prelim_result": prelim_result}
                await self._sleep(0.3)

        except Exception as e:
            self.logger().error(
                f"Order cancellation failed: {e}, order_id: {exchange_order_id}, submit_response: {submit_response}"
            )
            cancel_result = False
            cancel_data = {}

        return cancel_result, cancel_data

    async def _execute_order_cancel_and_process_update(self, order: InFlightOrder) -> bool:
        if not self.ready:
            await self._sleep(3)

        retry = 0
        submitted = False
        verified = False
        resp = None
        submit_data = {}

        update_timestamp = self.current_timestamp
        if update_timestamp is None or math.isnan(update_timestamp):
            update_timestamp = self._time()

        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=OrderState.PENDING_CANCEL,
        )
        self._order_tracker.process_order_update(order_update)

        while retry < CONSTANTS.CANCEL_MAX_RETRY:
            submitted, submit_data = await self._place_cancel(order.client_order_id, order)
            verified, resp = await self._verify_transaction_result(submit_data)

            if submitted and verified:
                retry = CONSTANTS.CANCEL_MAX_RETRY
            else:
                retry += 1
                self.logger().debug(
                    f"Order cancellation failed. Retrying in {CONSTANTS.CANCEL_RETRY_INTERVAL} seconds..."
                )
                await self._sleep(CONSTANTS.CANCEL_RETRY_INTERVAL)

        if submitted and verified:
            if resp is None:
                self.logger().error(
                    f"Failed to cancel order {order.client_order_id} ({order.exchange_order_id}), data: {order}, submit_data: {submit_data}"
                )
                return False

            meta = resp.result.get("meta", {})
            sequence, ledger_index = order.exchange_order_id.split("-")
            changes_array = get_order_book_changes(meta)
            changes_array = [x for x in changes_array if x.get("maker_account") == self._auth.get_account()]
            status = "UNKNOWN"

            for offer_change in changes_array:
                changes = offer_change.get("offer_changes", [])

                for change in changes:
                    if int(change.get("sequence")) == int(sequence):
                        status = change.get("status")
                        break

            if len(changes_array) == 0:
                status = "cancelled"

            if status == "cancelled":
                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=order.client_order_id,
                    trading_pair=order.trading_pair,
                    update_timestamp=self._time(),
                    new_state=OrderState.CANCELED,
                )
                self._order_tracker.process_order_update(order_update)
                return True
            else:
                await self._order_tracker.process_order_not_found(order.client_order_id)
                return False

        await self._order_tracker.process_order_not_found(order.client_order_id)
        return False

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancellations are performed in parallel tasks.

        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run

        :return: a list of CancellationResult instances, one for each of the orders to be cancelled
        """
        return await super().cancel_all(CONSTANTS.CANCEL_ALL_TIMEOUT)

    def _format_trading_rules(self, trading_rules_info: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []
        for trading_pair, trading_pair_info in trading_rules_info.items():
            base_tick_size = trading_pair_info["base_tick_size"]
            quote_tick_size = trading_pair_info["quote_tick_size"]
            minimum_order_size = trading_pair_info["minimum_order_size"]

            trading_rule = TradingRule(
                trading_pair=trading_pair,
                min_order_size=Decimal(minimum_order_size),
                min_price_increment=Decimal(f"1e-{quote_tick_size}"),
                min_quote_amount_increment=Decimal(f"1e-{quote_tick_size}"),
                min_base_amount_increment=Decimal(f"1e-{base_tick_size}"),
                min_notional_size=Decimal(f"1e-{quote_tick_size}"),
            )

            trading_rules.append(trading_rule)

        return trading_rules

    def _format_trading_pair_fee_rules(self, trading_rules_info: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        trading_pair_fee_rules = []

        for trading_pair, trading_pair_info in trading_rules_info.items():
            base_token = trading_pair.split("-")[0]
            quote_token = trading_pair.split("-")[1]
            trading_pair_fee_rules.append(
                {
                    "trading_pair": trading_pair,
                    "base_token": base_token,
                    "quote_token": quote_token,
                    "base_transfer_rate": trading_pair_info["base_transfer_rate"],
                    "quote_transfer_rate": trading_pair_info["quote_transfer_rate"],
                }
            )

        return trading_pair_fee_rules

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        # TODO: Move fee update logic to this method
        pass

    def get_order_by_sequence(self, sequence) -> Optional[InFlightOrder]:
        for client_order_id, order in self._order_tracker.all_fillable_orders.items():
            if order.exchange_order_id is None:
                return None

            if int(order.exchange_order_id.split("-")[0]) == int(sequence):
                return order

        return None

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                transaction = event_message.get("transaction", None)

                if transaction is None:
                    transaction = event_message.get("tx", None)

                if transaction is None:
                    transaction = event_message.get("tx_json", None)

                meta = event_message.get("meta")

                if transaction is None or meta is None:
                    self._logger.debug(f"Received event message without transaction or meta: {event_message}")
                    continue

                self._logger.debug(
                    f"Handling TransactionType: {transaction.get('TransactionType')}, Hash: {transaction.get('hash')} OfferSequence: {transaction.get('OfferSequence')}, Sequence: {transaction.get('Sequence')}..."
                )

                balance_changes = get_balance_changes(meta)
                order_book_changes = get_order_book_changes(meta)

                # Check if this is market order, if it is, check if it has been filled or failed
                tx_sequence = transaction.get("Sequence")
                tracked_order = self.get_order_by_sequence(tx_sequence)

                if tracked_order is not None and tracked_order.order_type is OrderType.MARKET:
                    tx_status = meta.get("TransactionResult")
                    if tx_status != "tesSUCCESS":
                        self.logger().error(
                            f"Order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}) failed: {tx_status}, data: {event_message}"
                        )
                        new_order_state = OrderState.FAILED
                    else:
                        new_order_state = OrderState.FILLED
                        trade_update = await self.process_trade_fills(event_message, tracked_order)
                        if trade_update is not None:
                            self._order_tracker.process_trade_update(trade_update)
                        else:
                            self.logger().error(
                                f"Failed to process trade fills for order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}), order state: {new_order_state}, data: {event_message}"
                            )

                    order_update = OrderUpdate(
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=tracked_order.exchange_order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=time.time(),
                        new_state=new_order_state,
                    )

                    self._order_tracker.process_order_update(order_update=order_update)

                # Handle state updates for orders
                for order_book_change in order_book_changes:
                    if order_book_change["maker_account"] != self._auth.get_account():
                        self._logger.debug(
                            f"Order book change not for this account? {order_book_change['maker_account']}"
                        )
                        continue

                    for offer_change in order_book_change["offer_changes"]:
                        tracked_order = self.get_order_by_sequence(offer_change["sequence"])
                        if tracked_order is None:
                            self._logger.debug(f"Tracked order not found for sequence '{offer_change['sequence']}'")
                            continue

                        status = offer_change["status"]
                        if status == "filled":
                            new_order_state = OrderState.FILLED

                        elif status == "partially-filled":
                            new_order_state = OrderState.PARTIALLY_FILLED
                        elif status == "cancelled":
                            new_order_state = OrderState.CANCELED
                        else:
                            # Check if the transaction did cross any offers in the order book
                            taker_gets = offer_change.get("taker_gets")
                            taker_pays = offer_change.get("taker_pays")

                            tx_taker_gets = transaction.get("TakerGets")
                            tx_taker_pays = transaction.get("TakerPays")

                            if isinstance(tx_taker_gets, str):
                                tx_taker_gets = {"currency": "XRP", "value": str(drops_to_xrp(tx_taker_gets))}

                            if isinstance(tx_taker_pays, str):
                                tx_taker_pays = {"currency": "XRP", "value": str(drops_to_xrp(tx_taker_pays))}

                            if taker_gets.get("value") != tx_taker_gets.get("value") or taker_pays.get(
                                "value"
                            ) != tx_taker_pays.get("value"):
                                new_order_state = OrderState.PARTIALLY_FILLED
                            else:
                                new_order_state = OrderState.OPEN

                        if new_order_state == OrderState.FILLED or new_order_state == OrderState.PARTIALLY_FILLED:
                            trade_update = await self.process_trade_fills(event_message, tracked_order)
                            if trade_update is not None:
                                self._order_tracker.process_trade_update(trade_update)
                            else:
                                self.logger().error(
                                    f"Failed to process trade fills for order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}), order state: {new_order_state}, data: {event_message}"
                                )

                        self._logger.debug(
                            f"Order update for order '{tracked_order.client_order_id}' with sequence '{offer_change['sequence']}': '{new_order_state}'"
                        )
                        order_update = OrderUpdate(
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=tracked_order.exchange_order_id,
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=time.time(),
                            new_state=new_order_state,
                        )

                        self._order_tracker.process_order_update(order_update=order_update)

                # Handle balance changes
                for balance_change in balance_changes:
                    if balance_change["account"] == self._auth.get_account():
                        await self._update_balances()
                        break

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        if order.exchange_order_id is None:
            return []

        _, ledger_index = order.exchange_order_id.split("-")

        transactions = await self._fetch_account_transactions(ledger_index, is_forward=True)

        trade_fills = []

        for transaction in transactions:
            tx = transaction.get("tx", None)

            if tx is None:
                tx = transaction.get("transaction", None)

            if tx is None:
                tx = transaction.get("tx_json", None)

            tx_type = tx.get("TransactionType", None)

            if tx_type is None or tx_type not in ["OfferCreate", "Payment"]:
                continue

            trade_update = await self.process_trade_fills(transaction, order)
            if trade_update is not None:
                trade_fills.append(trade_update)

        return trade_fills

    async def process_trade_fills(self, data: Dict[str, Any], order: InFlightOrder) -> Optional[TradeUpdate]:
        base_currency, quote_currency = self.get_currencies_from_trading_pair(order.trading_pair)
        sequence, ledger_index = order.exchange_order_id.split("-")
        fee_rules = self._trading_pair_fee_rules.get(order.trading_pair)

        if fee_rules is None:
            await self._update_trading_rules()
            fee_rules = self._trading_pair_fee_rules.get(order.trading_pair)

        if "result" in data:
            data_result = data.get("result", {})
            meta = data_result.get("meta", {})

            if "tx_json" in data_result:
                tx = data_result.get("tx_json")
                tx["hash"] = data_result.get("hash")
            elif "transaction" in data_result:
                tx = data_result.get("transaction")
                tx["hash"] = data_result.get("hash")
            else:
                tx = data_result
        else:
            meta = data.get("meta", {})
            tx = {}

            # check if transaction has key "tx" or "transaction"?
            if "tx" in data:
                tx = data.get("tx", None)
            elif "transaction" in data:
                tx = data.get("transaction", None)
            elif "tx_json" in data:
                tx = data.get("tx_json", None)

            if "hash" in data:
                tx["hash"] = data.get("hash")

        if not isinstance(tx, dict):
            self.logger().error(
                f"Transaction not found for order {order.client_order_id} ({order.exchange_order_id}), data: {data}"
            )
            return None

        if tx.get("TransactionType") not in ["OfferCreate", "Payment"]:
            return None

        if tx["hash"] is None:
            self.logger().error("Hash is None")
            self.logger().error(f"Data: {data}")
            self.logger().error(f"Tx: {tx}")

        offer_changes = get_order_book_changes(meta)
        balance_changes = get_balance_changes(meta)

        # Filter out change that is not from this account
        offer_changes = [x for x in offer_changes if x.get("maker_account") == self._auth.get_account()]
        balance_changes = [x for x in balance_changes if x.get("account") == self._auth.get_account()]

        tx_sequence = tx.get("Sequence")

        if int(tx_sequence) == int(sequence):
            # check status of the transaction
            tx_status = meta.get("TransactionResult")
            if tx_status != "tesSUCCESS":
                self.logger().error(
                    f"Order {order.client_order_id} ({order.exchange_order_id}) failed: {tx_status}, data: {data}"
                )
                return None

            # If this order is market order, this order has been filled
            if order.order_type is OrderType.MARKET:
                # check if there is any balance changes
                if len(balance_changes) == 0:
                    self.logger().error(
                        f"Order {order.client_order_id} ({order.exchange_order_id}) has no balance changes, data: {data}"
                    )
                    return None

                for balance_change in balance_changes:
                    changes = balance_change.get("balances", [])
                    base_change = get_token_from_changes(changes, token=base_currency.currency)
                    quote_change = get_token_from_changes(changes, token=quote_currency.currency)

                    if order.trade_type is TradeType.BUY:
                        fee_token = fee_rules.get("quote_token")
                        fee_rate = fee_rules.get("quote_transfer_rate")
                    else:
                        fee_token = fee_rules.get("base_token")
                        fee_rate = fee_rules.get("base_transfer_rate")

                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent_token=fee_token.upper(),
                        percent=Decimal(fee_rate),
                    )

                    trade_update = TradeUpdate(
                        trade_id=tx.get("hash"),
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                        trading_pair=order.trading_pair,
                        fee=fee,
                        fill_base_amount=abs(Decimal(base_change.get("value"))),
                        fill_quote_amount=abs(Decimal(quote_change.get("value"))),
                        fill_price=abs(Decimal(quote_change.get("value"))) / abs(Decimal(base_change.get("value"))),
                        fill_timestamp=ripple_time_to_posix(tx.get("date")),
                    )

                    # trade_fills.append(trade_update)
                    return trade_update
            else:
                # This is a limit order, check if the limit order did cross any offers in the order book
                for offer_change in offer_changes:
                    changes = offer_change.get("offer_changes", [])

                    for change in changes:
                        if int(change.get("sequence")) == int(sequence):
                            taker_gets = change.get("taker_gets")
                            taker_pays = change.get("taker_pays")

                            tx_taker_gets = tx.get("TakerGets")
                            tx_taker_pays = tx.get("TakerPays")

                            if isinstance(tx_taker_gets, str):
                                tx_taker_gets = {"currency": "XRP", "value": str(drops_to_xrp(tx_taker_gets))}

                            if isinstance(tx_taker_pays, str):
                                tx_taker_pays = {"currency": "XRP", "value": str(drops_to_xrp(tx_taker_pays))}

                            if taker_gets.get("value") != tx_taker_gets.get("value") or taker_pays.get(
                                "value"
                            ) != tx_taker_pays.get("value"):
                                diff_taker_gets_value = abs(
                                    Decimal(taker_gets.get("value")) - Decimal(tx_taker_gets.get("value"))
                                )
                                diff_taker_pays_value = abs(
                                    Decimal(taker_pays.get("value")) - Decimal(tx_taker_pays.get("value"))
                                )

                                diff_taker_gets = {
                                    "currency": taker_gets.get("currency"),
                                    "value": str(diff_taker_gets_value),
                                }

                                diff_taker_pays = {
                                    "currency": taker_pays.get("currency"),
                                    "value": str(diff_taker_pays_value),
                                }

                                base_change = get_token_from_changes(
                                    token_changes=[diff_taker_gets, diff_taker_pays], token=base_currency.currency
                                )
                                quote_change = get_token_from_changes(
                                    token_changes=[diff_taker_gets, diff_taker_pays], token=quote_currency.currency
                                )

                                if order.trade_type is TradeType.BUY:
                                    fee_token = fee_rules.get("quote_token")
                                    fee_rate = fee_rules.get("quote_transfer_rate")
                                else:
                                    fee_token = fee_rules.get("base_token")
                                    fee_rate = fee_rules.get("base_transfer_rate")

                                fee = TradeFeeBase.new_spot_fee(
                                    fee_schema=self.trade_fee_schema(),
                                    trade_type=order.trade_type,
                                    percent_token=fee_token.upper(),
                                    percent=Decimal(fee_rate),
                                )

                                trade_update = TradeUpdate(
                                    trade_id=tx.get("hash"),
                                    client_order_id=order.client_order_id,
                                    exchange_order_id=order.exchange_order_id,
                                    trading_pair=order.trading_pair,
                                    fee=fee,
                                    fill_base_amount=abs(Decimal(base_change.get("value"))),
                                    fill_quote_amount=abs(Decimal(quote_change.get("value"))),
                                    fill_price=abs(Decimal(quote_change.get("value")))
                                    / abs(Decimal(base_change.get("value"))),
                                    fill_timestamp=ripple_time_to_posix(tx.get("date")),
                                )

                                return trade_update
        else:
            # Find if offer changes are related to this order
            for offer_change in offer_changes:
                changes = offer_change.get("offer_changes", [])

                for change in changes:
                    if int(change.get("sequence")) == int(sequence):
                        taker_gets = change.get("taker_gets")
                        taker_pays = change.get("taker_pays")

                        base_change = get_token_from_changes(
                            token_changes=[taker_gets, taker_pays], token=base_currency.currency
                        )
                        quote_change = get_token_from_changes(
                            token_changes=[taker_gets, taker_pays], token=quote_currency.currency
                        )

                        if order.trade_type is TradeType.BUY:
                            fee_token = fee_rules.get("quote_token")
                            fee_rate = fee_rules.get("quote_transfer_rate")
                        else:
                            fee_token = fee_rules.get("base_token")
                            fee_rate = fee_rules.get("base_transfer_rate")

                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=order.trade_type,
                            percent_token=fee_token.upper(),
                            percent=Decimal(fee_rate),
                        )

                        trade_update = TradeUpdate(
                            trade_id=tx.get("hash"),
                            client_order_id=order.client_order_id,
                            exchange_order_id=order.exchange_order_id,
                            trading_pair=order.trading_pair,
                            fee=fee,
                            fill_base_amount=abs(Decimal(base_change.get("value"))),
                            fill_quote_amount=abs(Decimal(quote_change.get("value"))),
                            fill_price=abs(Decimal(quote_change.get("value"))) / abs(Decimal(base_change.get("value"))),
                            fill_timestamp=ripple_time_to_posix(tx.get("date")),
                        )

                        return trade_update

        return None

    async def _request_order_status(self, tracked_order: InFlightOrder, creation_tx_resp: Dict = None) -> OrderUpdate:
        # await self._make_network_check_request()
        new_order_state = tracked_order.current_state
        latest_status = "UNKNOWN"

        if tracked_order.exchange_order_id is None:
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=time.time(),
                new_state=new_order_state,
            )

            return order_update

        sequence, ledger_index = tracked_order.exchange_order_id.split("-")

        if tracked_order.order_type is OrderType.MARKET:
            if creation_tx_resp is None:
                transactions = await self._fetch_account_transactions(ledger_index)
            else:
                transactions = [creation_tx_resp]

            for transaction in transactions:
                if "result" in transaction:
                    data_result = transaction.get("result", {})
                    meta = data_result.get("meta", {})
                    tx = data_result
                else:
                    meta = transaction.get("meta", {})
                    if "tx" in transaction:
                        tx = transaction.get("tx", None)
                    elif "transaction" in transaction:
                        tx = transaction.get("transaction", None)
                    elif "tx_json" in transaction:
                        tx = transaction.get("tx_json", None)
                    else:
                        tx = transaction

                tx_sequence = tx.get("Sequence")

                if int(tx_sequence) == int(sequence):
                    tx_status = meta.get("TransactionResult")
                    update_timestamp = time.time()
                    if tx_status != "tesSUCCESS":
                        new_order_state = OrderState.FAILED
                        self.logger().error(
                            f"Order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}) failed: {tx_status}, data: {transaction}"
                        )
                    else:
                        new_order_state = OrderState.FILLED

                    order_update = OrderUpdate(
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=tracked_order.exchange_order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=update_timestamp,
                        new_state=new_order_state,
                    )

                    return order_update

            update_timestamp = time.time()
            self.logger().debug(
                f"Order {tracked_order.client_order_id} ({sequence}) not found in transaction history, tx history: {transactions}"
            )

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=update_timestamp,
                new_state=new_order_state,
            )

            return order_update
        else:
            if creation_tx_resp is None:
                transactions = await self._fetch_account_transactions(ledger_index, is_forward=True)
            else:
                transactions = [creation_tx_resp]

            found = False
            update_timestamp = time.time()

            for transaction in transactions:
                if found:
                    break

                if "result" in transaction:
                    data_result = transaction.get("result", {})
                    meta = data_result.get("meta", {})
                else:
                    meta = transaction.get("meta", {})

                changes_array = get_order_book_changes(meta)
                # Filter out change that is not from this account
                changes_array = [x for x in changes_array if x.get("maker_account") == self._auth.get_account()]

                for offer_change in changes_array:
                    changes = offer_change.get("offer_changes", [])

                    for change in changes:
                        if int(change.get("sequence")) == int(sequence):
                            latest_status = change.get("status")
                            found = True

            if latest_status == "UNKNOWN":
                current_state = tracked_order.current_state
                if current_state is OrderState.PENDING_CREATE or current_state is OrderState.PENDING_CANCEL:
                    # give order at least 120 seconds to be processed
                    if time.time() - tracked_order.last_update_timestamp > CONSTANTS.PENDING_ORDER_STATUS_CHECK_TIMEOUT:
                        new_order_state = OrderState.FAILED
                        self.logger().error(
                            f"Order status not found for order {tracked_order.client_order_id} ({sequence}), tx history: {transactions}"
                        )
                    else:
                        new_order_state = current_state
                else:
                    new_order_state = current_state
            elif latest_status == "filled":
                new_order_state = OrderState.FILLED
            elif latest_status == "partially-filled":
                new_order_state = OrderState.PARTIALLY_FILLED
            elif latest_status == "cancelled":
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

    async def _fetch_account_transactions(self, ledger_index: int, is_forward: bool = False) -> list:
        """
        Fetches account transactions from the XRPL ledger.

        :param ledger_index: The ledger index to start fetching transactions from.
        :param is_forward: If True, fetches transactions in forward order, otherwise in reverse order.
        :return: A list of transactions.
        """
        try:
            async with self._xrpl_fetch_trades_client_lock:
                request = AccountTx(
                    account=self._auth.get_account(),
                    ledger_index_min=int(ledger_index) - CONSTANTS.LEDGER_OFFSET,
                    forward=is_forward,
                )

                client_one = AsyncWebsocketClient(self._wss_node_url)
                client_two = AsyncWebsocketClient(self._wss_second_node_url)
                tasks = [
                    self.request_with_retry(client_one, request, 5),
                    self.request_with_retry(client_two, request, 5),
                ]
                task_results = await safe_gather(*tasks, return_exceptions=True)

                return_transactions = []

                for task_id, task_result in enumerate(task_results):
                    if isinstance(task_result, Response):
                        result = task_result.result
                        if result is not None:
                            transactions = result.get("transactions", [])

                            if len(transactions) > len(return_transactions):
                                return_transactions = transactions
                await self._sleep(3)

        except Exception as e:
            self.logger().error(f"Failed to fetch account transactions: {e}")
            return_transactions = []

        return return_transactions

    async def _update_balances(self):
        await self._client_health_check()
        account_address = self._auth.get_account()

        account_info = await self.request_with_retry(
            self._xrpl_query_client,
            AccountInfo(account=account_address, ledger_index="validated"),
            5,
            self._xrpl_query_client_lock,
            0.3,
        )

        objects = await self.request_with_retry(
            self._xrpl_query_client,
            AccountObjects(
                account=account_address,
            ),
            5,
            self._xrpl_query_client_lock,
            0.3,
        )

        open_offers = [x for x in objects.result.get("account_objects", []) if x.get("LedgerEntryType") == "Offer"]

        account_lines = await self.request_with_retry(
            self._xrpl_query_client,
            AccountLines(
                account=account_address,
            ),
            5,
            self._xrpl_query_client_lock,
            0.3,
        )

        if account_lines is not None:
            balances = account_lines.result.get("lines", [])
        else:
            balances = []

        xrp_balance = account_info.result.get("account_data", {}).get("Balance", "0")
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

            token = currency.strip("\x00").upper()
            token_issuer = balance.get("account")
            token_symbol = self.get_token_symbol_from_all_markets(token, token_issuer)

            amount = balance.get("balance")

            if token_symbol is None:
                continue

            account_balances[token_symbol] = abs(Decimal(amount))

        if self._account_balances is not None and len(balances) == 0:
            account_balances = self._account_balances.copy()

        account_available_balances = account_balances.copy()
        account_available_balances["XRP"] = Decimal(available_xrp)

        for offer in open_offers:
            taker_gets = offer.get("TakerGets")
            taker_gets_funded = offer.get("taker_gets_funded", None)

            if taker_gets_funded is not None:
                if isinstance(taker_gets_funded, dict):
                    token = taker_gets_funded.get("currency")
                    token_issuer = taker_gets_funded.get("issuer")
                    if len(token) > 3:
                        token = hex_to_str(token).strip("\x00").upper()
                    token_symbol = self.get_token_symbol_from_all_markets(token, token_issuer)
                    amount = Decimal(taker_gets_funded.get("value"))
                else:
                    amount = drops_to_xrp(taker_gets_funded)
                    token_symbol = "XRP"
            else:
                if isinstance(taker_gets, dict):
                    token = taker_gets.get("currency")
                    token_issuer = taker_gets.get("issuer")
                    if len(token) > 3:
                        token = hex_to_str(token).strip("\x00").upper()
                    token_symbol = self.get_token_symbol_from_all_markets(token, token_issuer)
                    amount = Decimal(taker_gets.get("value"))
                else:
                    amount = drops_to_xrp(taker_gets)
                    token_symbol = "XRP"

            if token_symbol is None:
                continue

            account_available_balances[token_symbol] -= amount

        self._account_balances = account_balances
        self._account_available_balances = account_available_balances

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, XRPLMarket]):
        markets = exchange_info
        mapping_symbol = bidict()

        for market, _ in markets.items():
            self.logger().debug(f"Processing market {market}")
            mapping_symbol[market.upper()] = market.upper()
        self._set_trading_pair_symbol_map(mapping_symbol)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        last_price = self.order_books.get(trading_pair).last_trade_price

        return last_price

    async def _get_best_price(self, trading_pair: str, is_buy: bool) -> float:
        best_price = self.order_books.get(trading_pair).get_price(is_buy)

        return best_price

    def buy(
        self, trading_pair: str, amount: Decimal, order_type=OrderType.LIMIT, price: Decimal = s_decimal_NaN, **kwargs
    ) -> str:
        """
        Creates a promise to create a buy order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        prefix = f"{self.client_order_id_prefix}-{self._nonce_creator.get_tracking_nonce()}-"
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=prefix,
            max_id_len=self.client_order_id_max_length,
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
        prefix = f"{self.client_order_id_prefix}-{self._nonce_creator.get_tracking_nonce()}-"
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=prefix,
            max_id_len=self.client_order_id_max_length,
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
        trading_rules_list = self._format_trading_rules(trading_rules_info)
        trading_pair_fee_rules = self._format_trading_pair_fee_rules(trading_rules_info)
        self._trading_rules.clear()
        self._trading_pair_fee_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

        for trading_pair_fee_rule in trading_pair_fee_rules:
            self._trading_pair_fee_rules[trading_pair_fee_rule["trading_pair"]] = trading_pair_fee_rule

        exchange_info = self._make_trading_pairs_request()
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _initialize_trading_pair_symbol_map(self):
        try:
            exchange_info = self._make_trading_pairs_request()
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception as e:
            self.logger().exception(f"There was an error requesting exchange info: {e}")

    async def _make_network_check_request(self):
        await self._xrpl_query_client.open()

    async def _client_health_check(self):
        # Clear client memory to prevent memory leak
        if time.time() - self._last_clients_refresh_time > CONSTANTS.CLIENT_REFRESH_INTERVAL:
            async with self._xrpl_query_client_lock:
                await self._xrpl_query_client.close()

            self._last_clients_refresh_time = time.time()

        await self._xrpl_query_client.open()

    async def _make_trading_rules_request(self) -> Dict[str, Any]:
        await self._client_health_check()
        zeroTransferRate = 1000000000
        trading_rules_info = {}

        for trading_pair in self._trading_pairs:
            base_currency, quote_currency = self.get_currencies_from_trading_pair(trading_pair)

            if base_currency.currency == XRP().currency:
                baseTickSize = 6
                baseTransferRate = 0
            else:
                base_info = await self.request_with_retry(
                    self._xrpl_query_client,
                    AccountInfo(account=base_currency.issuer, ledger_index="validated"),
                    3,
                    self._xrpl_query_client_lock,
                    1,
                )

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
                quote_info = await self.request_with_retry(
                    self._xrpl_query_client,
                    AccountInfo(account=quote_currency.issuer, ledger_index="validated"),
                    3,
                    self._xrpl_query_client_lock,
                    1,
                )

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
                "minimum_order_size": minimumOrderSize,
            }

        return trading_rules_info

    def _make_trading_pairs_request(self) -> Dict[str, XRPLMarket]:
        # Load default markets
        markets = CONSTANTS.MARKETS
        loaded_markets: Dict[str, XRPLMarket] = {}

        # Load each market into XRPLMarket
        for k, v in markets.items():
            loaded_markets[k] = XRPLMarket(
                base=v["base"],
                base_issuer=v["base_issuer"],
                quote=v["quote"],
                quote_issuer=v["quote_issuer"],
                trading_pair_symbol=k,
            )

        # Merge default markets with custom markets
        loaded_markets.update(self._custom_markets)

        return loaded_markets

    def get_currencies_from_trading_pair(
        self, trading_pair: str
    ) -> (Tuple)[Union[IssuedCurrency, XRP], Union[IssuedCurrency, XRP]]:
        # Find market in the markets list
        all_markets = self._make_trading_pairs_request()
        market = all_markets.get(trading_pair, None)

        if market is None:
            raise ValueError(f"Market {trading_pair} not found in markets list")

        # Get all info
        base = market.base
        base_issuer = market.base_issuer
        quote = market.quote
        quote_issuer = market.quote_issuer

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

    async def tx_autofill(
        self, transaction: Transaction, client: Client, signers_count: Optional[int] = None
    ) -> Transaction:
        return await autofill(transaction, client, signers_count)

    def tx_sign(
        self,
        transaction: Transaction,
        wallet: Wallet,
        multisign: bool = False,
    ) -> Transaction:
        return sign(transaction, wallet, multisign)

    async def tx_submit(
        self,
        transaction: Transaction,
        client: Client,
        *,
        fail_hard: bool = False,
    ) -> Response:

        transaction_blob = encode(transaction.to_xrpl())
        response = await client._request_impl(
            SubmitOnly(tx_blob=transaction_blob, fail_hard=fail_hard), timeout=CONSTANTS.REQUEST_TIMEOUT
        )
        if response.is_successful():
            return response

        raise XRPLRequestFailureException(response.result)

    async def wait_for_final_transaction_outcome(self, transaction, prelim_result) -> Response:
        async with AsyncWebsocketClient(self._wss_node_url) as client:
            resp = await _wait_for_final_transaction_outcome(
                transaction.get_hash(), client, prelim_result, transaction.last_ledger_sequence
            )
        return resp

    async def request_with_retry(
        self,
        client: AsyncWebsocketClient,
        request: Request,
        max_retries: int = 3,
        lock: Lock = None,
        delay_time: float = 0.0,
    ) -> Response:
        try:
            await client.open()

            if lock is not None:
                async with lock:
                    async with client:
                        resp = await client.request(request)
            else:
                async with client:
                    resp = await client.request(request)

            await self._sleep(delay_time)
            return resp
        except (TimeoutError, asyncio.exceptions.TimeoutError) as e:
            self.logger().debug(f"Request {request} timeout error: {e}")
            if max_retries > 0:
                await self._sleep(CONSTANTS.REQUEST_RETRY_INTERVAL)
                return await self.request_with_retry(client, request, max_retries - 1, lock, delay_time)
            else:
                self.logger().error(f"Max retries reached. Request {request} failed due to timeout.")
        except Exception as e:
            self.logger().error(f"Request {request} failed: {e}")

    def get_token_symbol_from_all_markets(self, code: str, issuer: str) -> Optional[str]:
        all_markets = self._make_trading_pairs_request()
        for market in all_markets.values():
            token_symbol = market.get_token_symbol(code, issuer)

            if token_symbol is not None:
                return token_symbol.upper()
        return None
