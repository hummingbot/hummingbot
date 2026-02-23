import asyncio
import hashlib
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as CONSTANTS,
    grvt_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_order_book_data_source import (
    GrvtPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_user_stream_data_source import (
    GrvtPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import (
    grvt_instrument_to_hb_trading_pair,
    hb_trading_pair_to_grvt_instrument,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

bpm_logger = None


class GrvtPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Main connector class for the GRVT Perpetual exchange.

    Extends PerpetualDerivativePyBase and implements all GRVT-specific
    REST and WebSocket interactions.

    Key differences from other connectors:
    - All REST endpoints use POST method
    - Triple-host architecture (edge, trade, market-data)
    - Session cookie authentication (not per-request HMAC)
    - EIP-712 order signing with legs[] array
    - Prices use 9 decimal precision for signing
    - Instrument format: BTC_USDT_Perp
    """

    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        grvt_perpetual_api_key: str = None,
        grvt_perpetual_secret_key: str = None,
        grvt_perpetual_sub_account_id: str = "0",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self.grvt_perpetual_api_key = grvt_perpetual_api_key
        self.grvt_perpetual_secret_key = grvt_perpetual_secret_key
        self._sub_account_id = grvt_perpetual_sub_account_id
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None

        # Maps instrument name to its metadata (asset_id, base_decimals, etc.)
        self._instrument_map: Dict[str, Dict[str, Any]] = {}

        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[GrvtPerpetualAuth]:
        if self._trading_required:
            return GrvtPerpetualAuth(
                api_key=self.grvt_perpetual_api_key,
                private_key=self.grvt_perpetual_secret_key,
                sub_account_id=self._sub_account_id,
                domain=self._domain,
            )
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> Optional[int]:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.ALL_INSTRUMENTS_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.ALL_INSTRUMENTS_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.ALL_INSTRUMENTS_URL

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
        await self._api_post(
            path_url=self.check_network_request_path,
            data={"is_active": True},
        )

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

    def _is_request_exception_related_to_time_synchronizer(
        self, request_exception: Exception
    ) -> bool:
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self._api_post(
            path_url=self.trading_rules_request_path,
            data={"is_active": True},
        )
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_post(
            path_url=self.trading_pairs_request_path,
            data={"is_active": True},
        )
        return exchange_info

    def _is_order_not_found_during_status_update_error(
        self, status_update_exception: Exception
    ) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(
        self, cancelation_exception: Exception
    ) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def quantize_order_price(
        self, trading_pair: str, price: Decimal
    ) -> Decimal:
        """
        Applies trading rule to quantize order price.
        GRVT uses 9 decimal precision for prices in signing.
        """
        d_price = Decimal(round(float(f"{price:.5g}"), 6))
        return d_price

    async def _update_trading_rules(self):
        exchange_info = await self._api_post(
            path_url=self.trading_rules_request_path,
            data={"is_active": True},
        )
        self._initialize_trading_pair_symbols_from_exchange_info(
            exchange_info=exchange_info
        )
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _initialize_trading_pair_symbol_map(self):
        try:
            exchange_info = await self._api_post(
                path_url=self.trading_pairs_request_path,
                data={"is_active": True},
            )
            self._initialize_trading_pair_symbols_from_exchange_info(
                exchange_info=exchange_info
            )
        except Exception:
            self.logger().exception(
                "There was an error requesting exchange info."
            )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GrvtPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GrvtPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        """
        Fetches ticker prices for all instruments.
        """
        res: List[Dict[str, str]] = []

        instruments = await self._api_post(
            path_url=CONSTANTS.ALL_INSTRUMENTS_URL,
            data={"is_active": True},
        )

        instrument_list = instruments.get("result", instruments)
        if isinstance(instrument_list, dict):
            instrument_list = instrument_list.get("instruments", [])
        if not isinstance(instrument_list, list):
            instrument_list = []

        for instrument_info in instrument_list:
            instrument_name = instrument_info.get("instrument", "")
            # Fetch ticker for each instrument
            try:
                ticker = await self._api_post(
                    path_url=CONSTANTS.TICKER_URL,
                    data={"instrument": instrument_name},
                )
                ticker_data = ticker.get("result", ticker)
                if isinstance(ticker_data, list) and len(ticker_data) > 0:
                    ticker_data = ticker_data[0]
                res.append(
                    {
                        "symbol": instrument_name,
                        "price": str(
                            ticker_data.get(
                                "mark_price",
                                ticker_data.get("last_price", "0"),
                            )
                        ),
                    }
                )
            except Exception:
                self.logger().debug(
                    f"Error fetching ticker for {instrument_name}"
                )
                continue

        return res

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_trade_history(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_order_status(self):
        await self._update_orders()

    async def _update_lost_orders_status(self):
        await self._update_lost_orders()

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
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
        Update fees information from the exchange.
        GRVT fees are static per tier; no dynamic endpoint needed.
        """
        pass

    async def _place_cancel(
        self, order_id: str, tracked_order: InFlightOrder
    ):
        """
        Cancels an order on the GRVT exchange.

        GRVT endpoint: POST /full/v1/cancel_order
        """
        instrument = await self.exchange_symbol_associated_to_pair(
            trading_pair=tracked_order.trading_pair
        )

        api_params = {
            "instrument": instrument,
            "order_id": tracked_order.exchange_order_id or order_id,
            "client_order_id": order_id,
            "sub_account_id": self._sub_account_id,
        }

        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=api_params,
            is_auth_required=True,
        )

        result = cancel_result.get("result", cancel_result)

        if cancel_result.get("code") and cancel_result.get("code") != 0:
            error_msg = cancel_result.get("message", "Unknown cancel error")
            self.logger().debug(
                f"The order {order_id} does not exist on GRVT. "
                f"No cancelation needed."
            )
            await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f"{error_msg}")

        return True

    # === Order Placing ===

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type=OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        """
        Creates a promise to create a buy order.

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the client order id assigned by the connector
        """
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode("utf-8"))
        hex_order_id = f"0x{md5.hexdigest()}"

        if order_type is OrderType.MARKET:
            reference_price = (
                self.get_mid_price(trading_pair) if price.is_nan() else price
            )
            price = self.quantize_order_price(
                trading_pair,
                reference_price * Decimal(1 + CONSTANTS.MARKET_ORDER_SLIPPAGE),
            )

        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
                order_id=hex_order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return hex_order_id

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        """
        Creates a promise to create a sell order.

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the client order id assigned by the connector
        """
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode("utf-8"))
        hex_order_id = f"0x{md5.hexdigest()}"

        if order_type is OrderType.MARKET:
            reference_price = (
                self.get_mid_price(trading_pair) if price.is_nan() else price
            )
            price = self.quantize_order_price(
                trading_pair,
                reference_price * Decimal(1 - CONSTANTS.MARKET_ORDER_SLIPPAGE),
            )

        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
                order_id=hex_order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return hex_order_id

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
        """
        Places an order on the GRVT exchange using EIP-712 signed data.

        GRVT endpoint: POST /full/v1/create_order
        Orders use legs[] array (single leg for perps).
        """
        instrument = await self.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair
        )

        # Get instrument metadata for proper precision
        instrument_info = self._instrument_map.get(instrument, {})
        base_decimals = instrument_info.get("base_decimals", 8)
        asset_id = instrument_info.get("asset_id", 0)

        # Determine time-in-force
        if order_type is OrderType.LIMIT_MAKER:
            time_in_force = 1  # Post-only / ALO
            is_market = False
            post_only = True
        elif order_type is OrderType.MARKET:
            time_in_force = 3  # IOC
            is_market = True
            post_only = False
        else:
            time_in_force = 2  # GTC
            is_market = False
            post_only = False

        is_buy = trade_type is TradeType.BUY
        reduce_only = position_action == PositionAction.CLOSE

        # Convert price and size to signing precision
        # Price: multiply by 1e9
        limit_price_int = int(float(price) * CONSTANTS.PRICE_PRECISION)
        # Size: multiply by 10^base_decimals
        contract_size_int = int(float(amount) * (10**base_decimals))

        nonce = int(time.time() * 1000) % (2**32)
        expiration = int(time.time()) + 86400  # 24 hours from now

        # Sign the order using EIP-712
        signature = self._auth.sign_order(
            sub_account_id=int(self._sub_account_id),
            is_market=is_market,
            time_in_force=time_in_force,
            post_only=post_only,
            reduce_only=reduce_only,
            asset_id=asset_id,
            contract_size=contract_size_int,
            limit_price=limit_price_int,
            is_buying_contract=is_buy,
            nonce=nonce,
            expiration=expiration,
        )

        # Build the API request payload
        api_params = {
            "order": {
                "sub_account_id": self._sub_account_id,
                "is_market": is_market,
                "time_in_force": time_in_force,
                "post_only": post_only,
                "reduce_only": reduce_only,
                "legs": [
                    {
                        "instrument": instrument,
                        "asset_id": str(asset_id),
                        "size": str(amount),
                        "limit_price": str(price),
                        "is_buying_contract": is_buy,
                    }
                ],
                "nonce": nonce,
                "expiration": expiration,
                "signature": signature,
                "client_order_id": order_id,
            },
            "instrument": instrument,
        }

        order_result = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_URL,
            data=api_params,
            is_auth_required=True,
        )

        # Check for errors
        if order_result.get("code") and order_result.get("code") != 0:
            error_msg = order_result.get(
                "message", order_result.get("error", "Unknown error")
            )
            raise IOError(f"Error submitting order {order_id}: {error_msg}")

        result = order_result.get("result", order_result)
        exchange_order_id = str(
            result.get("order_id", result.get("oid", ""))
        )

        return (exchange_order_id, self.current_timestamp)

    async def _update_trade_history(self):
        """
        Fetches recent fill history and processes trade updates.

        GRVT endpoint: POST /full/v1/fill_history
        """
        orders = list(self._order_tracker.all_fillable_orders.values())
        all_fillable_orders = (
            self._order_tracker.all_fillable_orders_by_exchange_order_id
        )
        all_fills_response = []

        if len(orders) > 0:
            try:
                all_fills_response = await self._api_post(
                    path_url=CONSTANTS.FILL_HISTORY_URL,
                    data={
                        "sub_account_id": self._sub_account_id,
                    },
                    is_auth_required=True,
                )
                # Normalize response
                if isinstance(all_fills_response, dict):
                    all_fills_response = all_fills_response.get(
                        "result", all_fills_response.get("fills", [])
                    )
                if not isinstance(all_fills_response, list):
                    all_fills_response = []
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                self.logger().warning(
                    f"Failed to fetch trade updates. Error: {request_error}",
                    exc_info=request_error,
                )

            for trade_fill in all_fills_response:
                self._process_trade_rs_event_message(
                    order_fill=trade_fill,
                    all_fillable_order=all_fillable_orders,
                )

    def _process_trade_rs_event_message(
        self,
        order_fill: Dict[str, Any],
        all_fillable_order: Dict[str, InFlightOrder],
    ):
        exchange_order_id = str(
            order_fill.get("order_id", order_fill.get("oid", ""))
        )
        fillable_order = all_fillable_order.get(exchange_order_id)

        if fillable_order is not None:
            fee_asset = fillable_order.quote_asset

            # Determine position action from fill data
            is_close = order_fill.get("is_close", False) or order_fill.get(
                "reduce_only", False
            )
            position_action = (
                PositionAction.CLOSE if is_close else PositionAction.OPEN
            )

            fee_amount = Decimal(
                str(order_fill.get("fee", order_fill.get("trade_fee", "0")))
            )
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)],
            )

            fill_price = Decimal(
                str(order_fill.get("price", order_fill.get("fill_price", "0")))
            )
            fill_size = Decimal(
                str(order_fill.get("size", order_fill.get("fill_size", "0")))
            )
            trade_id = str(
                order_fill.get(
                    "trade_id", order_fill.get("fill_id", order_fill.get("tid", ""))
                )
            )
            fill_timestamp = order_fill.get(
                "timestamp", order_fill.get("time", time.time() * 1e3)
            )

            trade_update = TradeUpdate(
                trade_id=trade_id,
                client_order_id=fillable_order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=fillable_order.trading_pair,
                fee=fee,
                fill_base_amount=fill_size,
                fill_quote_amount=fill_price * fill_size,
                fill_price=fill_price,
                fill_timestamp=float(fill_timestamp) * 1e-3,
            )
            self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates_for_order(
        self, order: InFlightOrder
    ) -> List[TradeUpdate]:
        # Handled by _update_trade_history instead
        pass

    async def _handle_update_error_for_active_order(
        self, order: InFlightOrder, error: Exception
    ):
        try:
            raise error
        except (asyncio.TimeoutError, KeyError):
            self.logger().debug(
                f"Tracked order {order.client_order_id} does not have an "
                f"exchange id. Attempting fetch in next polling interval."
            )
            await self._order_tracker.process_order_not_found(
                order.client_order_id
            )
        except asyncio.CancelledError:
            raise
        except Exception as request_error:
            self.logger().warning(
                f"Error fetching status update for active order "
                f"{order.client_order_id}: {request_error}.",
            )
            await self._order_tracker.process_order_not_found(
                order.client_order_id
            )

    async def _request_order_status(
        self, tracked_order: InFlightOrder
    ) -> OrderUpdate:
        """
        Fetches the status of a single order.

        GRVT endpoint: POST /full/v1/order
        """
        client_order_id = tracked_order.client_order_id
        try:
            if tracked_order.exchange_order_id:
                exchange_order_id = tracked_order.exchange_order_id
            else:
                exchange_order_id = await tracked_order.get_exchange_order_id()
        except asyncio.TimeoutError:
            exchange_order_id = None

        order_update_response = await self._api_post(
            path_url=CONSTANTS.ORDER_URL,
            data={
                "sub_account_id": self._sub_account_id,
                "order_id": exchange_order_id or "",
                "client_order_id": client_order_id,
            },
            is_auth_required=True,
        )

        result = order_update_response.get("result", order_update_response)
        order_data = result.get("order", result)

        current_state = order_data.get("status", "PENDING")
        _exchange_order_id = str(
            tracked_order.exchange_order_id
            or order_data.get("order_id", order_data.get("oid", ""))
        )
        update_timestamp = order_data.get(
            "timestamp", order_data.get("updated_at", time.time() * 1e3)
        )

        _order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=float(update_timestamp) * 1e-3,
            new_state=CONSTANTS.ORDER_STATE.get(
                current_state, CONSTANTS.ORDER_STATE.get("PENDING")
            ),
            client_order_id=order_data.get(
                "client_order_id", client_order_id
            ),
            exchange_order_id=_exchange_order_id,
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
                    app_warning_msg=(
                        "Could not fetch user events from GRVT. "
                        "Check API key and network connection."
                    ),
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Processes order, fill, and position updates from the WS.
        """
        user_channels = [
            CONSTANTS.WS_ORDER_CHANNEL,
            CONSTANTS.WS_ORDER_STATE_CHANNEL,
            CONSTANTS.WS_FILL_CHANNEL,
            CONSTANTS.WS_POSITION_CHANNEL,
        ]
        async for event_message in self._iter_user_event_queue():
            try:
                if isinstance(event_message, dict):
                    channel: str = event_message.get("channel", "")
                    results = event_message.get("data", None)
                elif event_message is asyncio.CancelledError:
                    raise asyncio.CancelledError
                else:
                    raise Exception(event_message)

                if channel not in user_channels:
                    self.logger().error(
                        f"Unexpected message in user stream: {event_message}.",
                        exc_info=True,
                    )
                    continue

                if channel in [
                    CONSTANTS.WS_ORDER_CHANNEL,
                    CONSTANTS.WS_ORDER_STATE_CHANNEL,
                ]:
                    # Order updates
                    if isinstance(results, list):
                        for order_msg in results:
                            self._process_order_message(order_msg)
                    elif isinstance(results, dict):
                        self._process_order_message(results)

                elif channel == CONSTANTS.WS_FILL_CHANNEL:
                    # Fill / trade updates
                    if isinstance(results, list):
                        for trade_msg in results:
                            await self._process_trade_message(trade_msg)
                    elif isinstance(results, dict):
                        await self._process_trade_message(results)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.",
                    exc_info=True,
                )
                await self._sleep(5.0)

    async def _process_trade_message(
        self,
        trade: Dict[str, Any],
        client_order_id: Optional[str] = None,
    ):
        """
        Updates in-flight order and triggers order filled event for trade
        messages received via WebSocket.
        """
        exchange_order_id = str(
            trade.get("order_id", trade.get("oid", ""))
        )
        tracked_order = (
            self._order_tracker.all_fillable_orders_by_exchange_order_id.get(
                exchange_order_id
            )
        )

        if tracked_order is None:
            all_orders = self._order_tracker.all_fillable_orders
            for k, v in all_orders.items():
                await v.get_exchange_order_id()
            _cli_tracked_orders = [
                o
                for o in all_orders.values()
                if exchange_order_id == o.exchange_order_id
            ]
            if not _cli_tracked_orders:
                self.logger().debug(
                    f"Ignoring trade message with id {exchange_order_id}: "
                    f"not in in_flight_orders."
                )
                return
            tracked_order = _cli_tracked_orders[0]

        is_close = trade.get("is_close", False) or trade.get(
            "reduce_only", False
        )
        position_action = (
            PositionAction.CLOSE if is_close else PositionAction.OPEN
        )
        fee_asset = tracked_order.quote_asset
        fee_amount = Decimal(
            str(trade.get("fee", trade.get("trade_fee", "0")))
        )
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)],
        )

        fill_price = Decimal(
            str(trade.get("price", trade.get("fill_price", "0")))
        )
        fill_size = Decimal(
            str(trade.get("size", trade.get("fill_size", "0")))
        )
        trade_id = str(
            trade.get(
                "trade_id", trade.get("fill_id", trade.get("tid", ""))
            )
        )
        fill_timestamp = trade.get(
            "timestamp", trade.get("time", time.time() * 1e3)
        )

        trade_update = TradeUpdate(
            trade_id=trade_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=float(fill_timestamp) * 1e-3,
            fill_price=fill_price,
            fill_base_amount=fill_size,
            fill_quote_amount=fill_price * fill_size,
            fee=fee,
        )
        self._order_tracker.process_trade_update(trade_update)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancelation or failure event
        if needed.
        """
        client_order_id = str(
            order_msg.get("client_order_id", order_msg.get("cloid", ""))
        )
        tracked_order = self._order_tracker.all_updatable_orders.get(
            client_order_id
        )
        if not tracked_order:
            self.logger().debug(
                f"Ignoring order message with id {client_order_id}: "
                f"not in in_flight_orders."
            )
            return

        current_state = order_msg.get("status", "PENDING")
        exchange_oid = str(
            order_msg.get("order_id", order_msg.get("oid", ""))
        )
        tracked_order.update_exchange_order_id(exchange_oid)

        update_timestamp = order_msg.get(
            "timestamp",
            order_msg.get("updated_at", time.time() * 1e3),
        )

        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=float(update_timestamp) * 1e-3,
            new_state=CONSTANTS.ORDER_STATE.get(
                current_state, CONSTANTS.ORDER_STATE.get("PENDING")
            ),
            client_order_id=client_order_id,
            exchange_order_id=exchange_oid,
        )
        self._order_tracker.process_order_update(order_update=order_update)

    async def _format_trading_rules(
        self, exchange_info: Any
    ) -> List[TradingRule]:
        """
        Parses the exchange instrument info and creates TradingRule objects.

        GRVT instruments have format: BTC_USDT_Perp
        """
        # Normalize the response format
        if isinstance(exchange_info, dict):
            instruments = exchange_info.get(
                "result",
                exchange_info.get("instruments", []),
            )
            if isinstance(instruments, dict):
                instruments = instruments.get("instruments", [])
        elif isinstance(exchange_info, list):
            instruments = exchange_info
        else:
            instruments = []

        return_val: List[TradingRule] = []

        for instrument_info in instruments:
            try:
                instrument_name = instrument_info.get(
                    "instrument", instrument_info.get("name", "")
                )
                if not instrument_name:
                    continue

                # Store instrument metadata for order placement
                base_decimals = int(
                    instrument_info.get("base_decimals", 8)
                )
                quote_decimals = int(
                    instrument_info.get("quote_decimals", 6)
                )
                asset_id = instrument_info.get("asset_id", 0)

                self._instrument_map[instrument_name] = {
                    "asset_id": asset_id,
                    "base_decimals": base_decimals,
                    "quote_decimals": quote_decimals,
                    "tick_size": instrument_info.get("tick_size", "0.01"),
                    "min_size": instrument_info.get("min_size", "0.001"),
                }

                trading_pair = grvt_instrument_to_hb_trading_pair(
                    instrument_name
                )

                # Calculate step sizes from decimals
                step_size = Decimal(str(10**-base_decimals))
                price_increment = Decimal(
                    str(
                        instrument_info.get(
                            "tick_size",
                            str(10**-quote_decimals),
                        )
                    )
                )
                min_order_size = Decimal(
                    str(instrument_info.get("min_size", str(step_size)))
                )

                # Determine collateral token from instrument name
                parts = instrument_name.replace("_Perp", "").split("_")
                collateral_token = parts[1] if len(parts) >= 2 else CONSTANTS.CURRENCY

                return_val.append(
                    TradingRule(
                        trading_pair,
                        min_base_amount_increment=step_size,
                        min_price_increment=price_increment,
                        min_order_size=min_order_size,
                        buy_order_collateral_token=collateral_token,
                        sell_order_collateral_token=collateral_token,
                    )
                )
            except Exception:
                self.logger().error(
                    f"Error parsing trading pair rule for {instrument_info}. Skipping.",
                    exc_info=True,
                )

        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(
        self, exchange_info: Any
    ):
        """
        Initializes the bidict mapping between exchange symbols and
        hummingbot trading pairs.
        """
        mapping = bidict()

        # Normalize response
        if isinstance(exchange_info, dict):
            instruments = exchange_info.get(
                "result",
                exchange_info.get("instruments", []),
            )
            if isinstance(instruments, dict):
                instruments = instruments.get("instruments", [])
        elif isinstance(exchange_info, list):
            instruments = exchange_info
        else:
            instruments = []

        for instrument_info in instruments:
            if not web_utils.is_exchange_information_valid(instrument_info):
                continue
            instrument_name = instrument_info.get(
                "instrument", instrument_info.get("name", "")
            )
            if not instrument_name:
                continue

            # Convert BTC_USDT_Perp -> BTC-USDT
            hb_pair = grvt_instrument_to_hb_trading_pair(instrument_name)
            parts = hb_pair.split("-")
            if len(parts) >= 2:
                base = parts[0]
                quote = parts[1]
                trading_pair = combine_to_hb_trading_pair(base, quote)
                if trading_pair in mapping.inverse:
                    self._resolve_trading_pair_symbols_duplicate(
                        mapping, instrument_name, base, quote
                    )
                else:
                    mapping[instrument_name] = trading_pair

        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """
        Fetches the last traded price for a trading pair.

        GRVT endpoint: POST /full/v1/ticker
        """
        try:
            instrument = await self.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair
            )
        except KeyError:
            instrument = hb_trading_pair_to_grvt_instrument(trading_pair)

        try:
            response = await self._api_post(
                path_url=CONSTANTS.TICKER_URL,
                data={"instrument": instrument},
            )

            result = response.get("result", response)
            if isinstance(result, list) and len(result) > 0:
                result = result[0]

            return float(
                result.get(
                    "mark_price",
                    result.get("last_price", result.get("markPx", 0)),
                )
            )
        except Exception as e:
            self.logger().error(
                f"Error fetching last traded price for "
                f"{trading_pair} ({instrument}): {e}"
            )
            raise RuntimeError(
                f"Price not found for trading_pair={trading_pair}, "
                f"instrument={instrument}"
            )

    def _resolve_trading_pair_symbols_duplicate(
        self,
        mapping: bidict,
        new_exchange_symbol: str,
        base: str,
        quote: str,
    ):
        """
        Resolves name conflicts for trading pair symbols.
        """
        expected_exchange_symbol = f"{base}_{quote}_Perp"
        trading_pair = combine_to_hb_trading_pair(base, quote)
        current_exchange_symbol = mapping.inverse[trading_pair]

        if current_exchange_symbol == expected_exchange_symbol:
            pass
        elif new_exchange_symbol == expected_exchange_symbol:
            mapping.pop(current_exchange_symbol)
            mapping[new_exchange_symbol] = trading_pair
        else:
            self.logger().error(
                f"Could not resolve the exchange symbols "
                f"{new_exchange_symbol} and {current_exchange_symbol}"
            )
            mapping.pop(current_exchange_symbol)

    async def _update_balances(self):
        """
        Fetches account summary to update balances.

        GRVT endpoint: POST /full/v1/account_summary
        """
        account_info = await self._api_post(
            path_url=CONSTANTS.ACCOUNT_SUMMARY_URL,
            data={"sub_account_id": self._sub_account_id},
            is_auth_required=True,
        )

        result = account_info.get("result", account_info)

        # Parse balance information
        total_equity = Decimal(
            str(result.get("total_equity", result.get("account_value", "0")))
        )
        available_balance = Decimal(
            str(
                result.get(
                    "available_balance",
                    result.get("withdrawable", str(total_equity)),
                )
            )
        )

        quote = CONSTANTS.CURRENCY
        self._account_balances[quote] = total_equity
        self._account_available_balances[quote] = available_balance

    async def _update_positions(self):
        """
        Fetches current positions.

        GRVT endpoint: POST /full/v1/positions
        """
        positions_response = await self._api_post(
            path_url=CONSTANTS.POSITIONS_URL,
            data={"sub_account_id": self._sub_account_id},
            is_auth_required=True,
        )

        result = positions_response.get("result", positions_response)
        positions = result.get("positions", result if isinstance(result, list) else [])

        processed_instruments = set()

        for position_data in positions:
            instrument = position_data.get(
                "instrument", position_data.get("coin", "")
            )

            if instrument in processed_instruments:
                continue
            processed_instruments.add(instrument)

            try:
                hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                    instrument
                )
            except KeyError:
                self.logger().debug(
                    f"Skipping position for unmapped instrument: {instrument}"
                )
                continue

            size = Decimal(
                str(position_data.get("size", position_data.get("szi", "0")))
            )
            position_side = (
                PositionSide.LONG if size > 0 else PositionSide.SHORT
            )
            unrealized_pnl = Decimal(
                str(
                    position_data.get(
                        "unrealized_pnl",
                        position_data.get("unrealizedPnl", "0"),
                    )
                )
            )
            entry_price = Decimal(
                str(
                    position_data.get(
                        "entry_price",
                        position_data.get("entryPx", "0"),
                    )
                )
            )
            leverage = Decimal(
                str(position_data.get("leverage", "1"))
            )

            pos_key = self._perpetual_trading.position_key(
                hb_trading_pair, position_side
            )

            if size != 0:
                _position = Position(
                    trading_pair=hb_trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=size,
                    leverage=leverage,
                )
                self._perpetual_trading.set_position(pos_key, _position)
            else:
                self._perpetual_trading.remove_position(pos_key)

        if not positions:
            keys = list(self._perpetual_trading.account_positions.keys())
            for key in keys:
                self._perpetual_trading.remove_position(key)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        return PositionMode.ONEWAY

    async def _trading_pair_position_mode_set(
        self, mode: PositionMode, trading_pair: str
    ) -> Tuple[bool, str]:
        msg = ""
        success = True
        initial_mode = await self._get_position_mode()
        if initial_mode != mode:
            msg = "GRVT only supports the ONEWAY position mode."
            success = False
        return success, msg

    async def _set_trading_pair_leverage(
        self, trading_pair: str, leverage: int
    ) -> Tuple[bool, str]:
        """
        GRVT sets leverage per-order via the order parameters, not via a
        separate API call. This method is a no-op that always succeeds.
        """
        self.logger().info(
            f"GRVT leverage is set per-order. Requested leverage {leverage}x "
            f"for {trading_pair} will be applied to subsequent orders."
        )
        return True, ""

    async def _fetch_last_fee_payment(
        self, trading_pair: str
    ) -> Tuple[int, Decimal, Decimal]:
        """
        Fetches the last funding payment for a trading pair.

        GRVT endpoint: POST /full/v1/funding_payment_history
        """
        instrument = await self.exchange_symbol_associated_to_pair(
            trading_pair
        )

        try:
            response = await self._api_post(
                path_url=CONSTANTS.FUNDING_PAYMENT_HISTORY_URL,
                data={
                    "sub_account_id": self._sub_account_id,
                    "instrument": instrument,
                },
                is_auth_required=True,
            )

            result = response.get("result", response)
            payments = result.get("payments", result if isinstance(result, list) else [])

            if not payments:
                return 0, Decimal("-1"), Decimal("-1")

            # Sort by timestamp descending to get most recent
            payments_sorted = sorted(
                payments,
                key=lambda x: x.get("timestamp", 0),
                reverse=True,
            )
            latest = payments_sorted[0]

            payment = Decimal(
                str(latest.get("payment", latest.get("amount", "0")))
            )
            funding_rate = Decimal(
                str(latest.get("funding_rate", latest.get("rate", "0")))
            )
            timestamp = float(latest.get("timestamp", 0)) * 1e-3

            if payment != Decimal("0"):
                return int(timestamp), funding_rate, payment
            else:
                return 0, Decimal("-1"), Decimal("-1")

        except Exception as e:
            self.logger().debug(
                f"Error fetching funding payment for {trading_pair}: {e}"
            )
            return 0, Decimal("-1"), Decimal("-1")

    def _last_funding_time(self) -> int:
        """
        GRVT funding settlement occurs every 8 hours.
        Returns the start of the current funding period in milliseconds.
        """
        interval = 8 * 3600  # 8 hours in seconds
        return int(((time.time() // interval) - 1) * interval * 1e3)
