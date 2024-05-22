import asyncio
import math
from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple

from bidict import ValueDuplicationError, bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.cube import cube_constants as CONSTANTS, cube_utils, cube_web_utils as web_utils
from hummingbot.connector.exchange.cube.cube_api_order_book_data_source import CubeAPIOrderBookDataSource
from hummingbot.connector.exchange.cube.cube_api_user_stream_data_source import CubeAPIUserStreamDataSource
from hummingbot.connector.exchange.cube.cube_auth import CubeAuth
from hummingbot.connector.exchange.cube.cube_utils import raw_units_to_number
from hummingbot.connector.exchange.cube.cube_ws_protobufs import trade_pb2
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CubeExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            cube_api_key: str,
            cube_api_secret: str,
            cube_subaccount_id: str,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.api_key = cube_api_key
        self.secret_key = cube_api_secret
        self.cube_subaccount_id = int(cube_subaccount_id)
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_cube_timestamp = 1.0
        self._auth: CubeAuth = self.authenticator
        self._trading_pair_symbol_map: Optional[Mapping[str, str]] = None
        self._trading_pair_market_id_map: Optional[Mapping[int, str]] = None
        self._token_id_map: Optional[Mapping[int, str]] = None
        self._token_info: Dict[int, Any] = {}
        self._is_bootstrap_completed = False
        self._nonce_creator = NonceCreator.for_milliseconds()
        self._mapping_initialization_lock = asyncio.Lock()

        if not self.check_domain(self._domain):
            raise ValueError(f"Invalid domain: {self._domain}")

        super().__init__(client_config_map)

    @staticmethod
    def cube_order_type(order_type: OrderType) -> str:
        return CONSTANTS.CUBE_ORDER_TYPE[order_type]

    @staticmethod
    def to_hb_order_type(cube_type: str) -> OrderType:
        return OrderType[cube_type]

    @property
    def authenticator(self) -> CubeAuth:
        return CubeAuth(api_key=self.api_key, secret_key=self.secret_key)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

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
        return pairs_prices.get("result", [])

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
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CubeAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return CubeAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
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
        # Response Example:
        # {
        #     "result": {
        #         "Ack": {
        #             "msgSeqNum": 540682839,
        #             "clientOrderId": 9991110,
        #             "requestId": 111223,
        #             "exchangeOrderId": 782467861,
        #             "marketId": 100006,
        #             "price": 10100,
        #             "quantity": 1,
        #             "side": 0,
        #             "timeInForce": 1,
        #             "orderType": 0,
        #             "transactTime": 1710314637443860607,
        #             "subaccountId": 38393,
        #             "cancelOnDisconnect": false
        #         }
        # }
        cube_order_type = CubeExchange.cube_order_type(order_type)
        order_side = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        market_id = await self.exchange_market_id_associated_to_pair(trading_pair=trading_pair)
        # trading_rule: TradingRule = self._trading_rules[trading_pair]

        price_scaler = Decimal(await self.get_price_scaler(trading_pair))
        quantity_scaler = Decimal(await self.get_quantity_scaler(trading_pair))

        if math.isnan(price):
            order_book_price = self.get_price(trading_pair, is_buy=True if trade_type is TradeType.BUY else False)
            exchange_price = order_book_price / price_scaler
        else:
            exchange_price = price / price_scaler

        exchange_amount = amount / quantity_scaler

        api_params = {
            "clientOrderId": int(order_id),
            "requestId": int(order_id),
            "marketId": int(market_id),
            "price": int(round(exchange_price)),
            "quantity": int(round(exchange_amount)),
            "side": order_side,
            "timeInForce": CONSTANTS.TIME_IN_FORCE_GTC,
            "orderType": int(cube_order_type),
            "subaccountId": int(self.cube_subaccount_id),
            "selfTradePrevention": 0,
            "postOnly": 0,
            "cancelOnDisconnect": False,
        }

        if order_type is OrderType.LIMIT_MAKER:
            api_params["postOnly"] = 1
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC
            api_params["orderType"] = CONSTANTS.CUBE_ORDER_TYPE[OrderType.LIMIT_MAKER]
        elif order_type is OrderType.LIMIT:
            api_params["postOnly"] = 0
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC
            api_params["orderType"] = CONSTANTS.CUBE_ORDER_TYPE[OrderType.LIMIT]

        elif order_type is OrderType.MARKET:
            if trade_type is TradeType.SELL:
                api_params["price"] = int(
                    round(exchange_price - (exchange_price * CONSTANTS.MAX_SLIPPAGE_PERCENTAGE / 100)))
            else:
                api_params["price"] = int(
                    round(exchange_price + (exchange_price * CONSTANTS.MAX_SLIPPAGE_PERCENTAGE / 100)))
            api_params["postOnly"] = 0
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_IOC
            api_params["orderType"] = CONSTANTS.CUBE_ORDER_TYPE[OrderType.MARKET]

        try:
            resp = await self._api_post(path_url=CONSTANTS.POST_ORDER_PATH_URL, data=api_params, is_auth_required=True)

            order_result = resp.get("result", None).get("Ack", None)
            order_reject = resp.get("result", None).get("Rej", None)

            if order_result is not None:
                o_id = str(order_result.get("exchangeOrderId"))
                transact_time = order_result.get("transactTime") * 1e-9
            elif order_reject is not None:
                new_state = OrderState.FAILED

                order_update = OrderUpdate(
                    trading_pair=trading_pair,
                    update_timestamp=order_reject.get("transactTime") * 1e-9,
                    new_state=new_state,
                    client_order_id=order_id,
                )
                self._order_tracker.process_order_update(order_update=order_update)
                o_id = "UNKNOWN"
                transact_time = order_reject.get("transactTime") * 1e-9,
                self.logger().error(
                    f"Order ({order_id}) creation failed: {order_reject.get('reason')}")
            else:
                raise ValueError("Unknown response from the exchange when placing order: %s" % resp)

        except IOError as e:
            error_description = str(e)
            is_server_overloaded = (
                "status is 503" in error_description
                and "Unknown error, please check your request or try again later." in error_description
            )
            if is_server_overloaded:
                o_id = "UNKNOWN"
                transact_time = self._time_synchronizer.time()
            else:
                raise

        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        # Response Example:
        # {
        #     "result": {
        #         "Ack": {
        #             "msgSeqNum": 544365567,
        #             "clientOrderId": 9991110,
        #             "requestId": 111223,
        #             "transactTime": 1710326938455195233,
        #             "subaccountId": 38393,
        #             "reason": 2,
        #             "marketId": 100006,
        #             "exchangeOrderId": 782467861
        #         }
        #     }
        # }
        market_id = await self.exchange_market_id_associated_to_pair(trading_pair=tracked_order.trading_pair)

        api_params = {
            "marketId": int(market_id),
            "clientOrderId": int(tracked_order.client_order_id),
            "requestId": int(tracked_order.client_order_id),
            "subaccountId": int(self.cube_subaccount_id),
        }

        resp = await self._api_delete(path_url=CONSTANTS.POST_ORDER_PATH_URL, data=api_params, is_auth_required=True)

        cancel_result = resp.get("result", {}).get("Ack", {})

        if int(cancel_result.get("clientOrderId", 0)) == int(tracked_order.client_order_id):
            return True

        cancel_reject = resp.get("result", {}).get("Rej", {})

        # If the order is not found, the response will contain a reason code 2
        if cancel_reject.get("reason") == 2:
            await self._order_tracker.process_order_not_found(tracked_order.client_order_id)

        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "result": {
                "assets": [
                    {
                        "assetId": 1,
                        "symbol": "BTC",
                        "decimals": 8,
                        "displayDecimals": 5,
                        "settles": true,
                        "assetType": "Crypto",
                        "sourceId": 1,
                        "metadata": {
                            "dustAmount": 3000
                        },
                        "disabled": false
                    }
                ],
                "sources": [
                    {
                        "sourceId": 0,
                        "name": "fiat",
                        "metadata": {}
                    },
                    {
                        "sourceId": 1,
                        "name": "bitcoin",
                        "transactionExplorer": "https://mempool.space/tx/{}",
                        "addressExplorer": "https://mempool.space/address/{}",
                        "metadata": {
                            "network": "Mainnet",
                            "scope": "bitcoin",
                            "type": "mainnet"
                        }
                    }
                ],
                "markets": [
                    {
                        "marketId": 100004,
                        "symbol": "BTCUSDC",
                        "baseAssetId": 1,
                        "baseLotSize": "1000",
                        "quoteAssetId": 7,
                        "quoteLotSize": "1",
                        "priceDisplayDecimals": 2,
                        "protectionPriceLevels": 3000,
                        "priceBandBidPct": 25,
                        "priceBandAskPct": 400,
                        "priceTickSize": "0.1",
                        "quantityTickSize": "0.00001",
                        "disabled": false,
                        "feeTableId": 2
                    }
                ],
                "feeTables": [
                    {
                        "feeTableId": 1,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0,
                                "takerFeeRatio": 0.0
                            }
                        ]
                    },
                    {
                        "feeTableId": 2,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0004,
                                "takerFeeRatio": 0.0008
                            }
                        ]
                    }
                ]
            }
        }
        """
        assets = {asset["assetId"]: asset for asset in exchange_info_dict.get("result", {}).get("assets", [])}
        markets = exchange_info_dict.get("result", {}).get("markets", [])
        retval = []
        for market in filter(cube_utils.is_exchange_information_valid, markets):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                    symbol=market.get("symbol").upper())
                base_asset = assets[market.get("baseAssetId")]
                quote_asset = assets[market.get("quoteAssetId")]

                min_order_size = Decimal(market.get("quantityTickSize"))
                min_price_increment = Decimal(market.get("priceTickSize"))
                min_base_amount_increment = Decimal(market.get("baseLotSize")) / (10 ** base_asset.get("decimals"))
                min_notional_size = Decimal(market.get("quoteLotSize")) / (10 ** quote_asset.get("decimals"))

                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=min_price_increment,
                        min_base_amount_increment=min_base_amount_increment,
                        min_notional_size=min_notional_size,
                    )
                )

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {market}. Skipping.")
        return retval

    # async def _status_polling_loop_fetch_updates(self):
    #     await self._update_order_fills_from_trades()
    #     await super()._status_polling_loop_fetch_updates()

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
                if self._is_bootstrap_completed is False:
                    msg: trade_pb2.Bootstrap = trade_pb2.Bootstrap().FromString(event_message)

                    if msg.HasField("done"):
                        self._is_bootstrap_completed = msg.done.read_only

                    if msg.HasField("position"):
                        for position in msg.position.positions:
                            if position.subaccount_id == self.cube_subaccount_id:
                                token_id_map = await self.token_id_map()
                                token_symbol = token_id_map[position.asset_id]

                                token_info = await self.token_info()
                                decimals = token_info.get(position.asset_id, {}).get("decimals", 1)

                                self._account_balances[token_symbol] = Decimal(raw_units_to_number(position.total) / (
                                    10 ** decimals))
                                self._account_available_balances[token_symbol] = Decimal(raw_units_to_number(
                                    position.available) / (10 ** decimals))

                else:
                    msg: trade_pb2.OrderResponse = trade_pb2.OrderResponse().FromString(event_message)

                    if msg.HasField("new_ack"):
                        tracked_order = self._order_tracker.all_updatable_orders.get(str(msg.new_ack.client_order_id))
                        if tracked_order is not None:
                            new_state = OrderState.OPEN

                            order_update = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=msg.new_ack.transact_time * 1e-9,
                                new_state=new_state,
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=str(msg.new_ack.exchange_order_id),
                            )
                            self._order_tracker.process_order_update(order_update=order_update)

                    if msg.HasField("cancel_ack"):
                        tracked_order = self._order_tracker.all_updatable_orders.get(
                            str(msg.cancel_ack.client_order_id)
                        )

                        if tracked_order is not None:
                            new_state = OrderState.CANCELED

                            order_update = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=msg.cancel_ack.transact_time * 1e-9,
                                new_state=new_state,
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=str(msg.cancel_ack.exchange_order_id),
                            )
                            self._order_tracker.process_order_update(order_update=order_update)

                    if msg.HasField("new_reject"):
                        tracked_order = self._order_tracker.all_updatable_orders.get(
                            str(msg.new_reject.client_order_id)
                        )
                        if tracked_order is not None:
                            new_state = OrderState.FAILED

                            order_update = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=msg.new_reject.transact_time * 1e-9,
                                new_state=new_state,
                                client_order_id=tracked_order.client_order_id,
                            )
                            self._order_tracker.process_order_update(order_update=order_update)
                            self.logger().error(
                                f"Order ({tracked_order.client_order_id}) creation failed: {msg.new_reject}")

                    if msg.HasField("position"):
                        if msg.position.subaccount_id == self.cube_subaccount_id:
                            # token_symbol = self.token_id_to_token_symbol(msg.position.asset_id)
                            token_id_map = await self.token_id_map()
                            token_symbol = token_id_map[msg.position.asset_id]
                            token_info = await self.token_info()
                            decimals = token_info.get(msg.position.asset_id, {}).get("decimals", 1)
                            self._account_balances[token_symbol] = Decimal(raw_units_to_number(msg.position.total) / (
                                10 ** decimals))
                            self._account_available_balances[token_symbol] = Decimal(raw_units_to_number(
                                msg.position.available) / (10 ** decimals))

                    if msg.HasField("fill"):
                        client_order_id = str(msg.fill.client_order_id)
                        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        if tracked_order is not None:
                            fill_token = (
                                tracked_order.base_asset
                                if tracked_order.trade_type is TradeType.BUY
                                else tracked_order.quote_asset
                            )

                            price_scaler = Decimal(await self.get_price_scaler(tracked_order.trading_pair))
                            quantity_scaler = Decimal(await self.get_quantity_scaler(tracked_order.trading_pair))

                            base_precision, quote_precision = await self.get_base_quote_precision(
                                tracked_order.trading_pair
                            )

                            fill_price = Decimal(msg.fill.fill_price) * price_scaler
                            fill_base_amount = Decimal(msg.fill.fill_quantity) * quantity_scaler
                            fill_base_amount = fill_base_amount.quantize(base_precision, rounding=ROUND_DOWN)
                            fill_quote_amount = fill_base_amount * fill_price
                            fill_quote_amount = fill_quote_amount.quantize(quote_precision, rounding=ROUND_DOWN)

                            # If trade is buy, fee is deducted from base token
                            # If trade is sell, fee is deducted from quote token
                            if tracked_order.trade_type is TradeType.BUY:
                                fee_amount = fill_base_amount * Decimal(msg.fill.fee_ratio.mantissa * (
                                    10 ** msg.fill.fee_ratio.exponent))
                            else:
                                fee_amount = fill_quote_amount * Decimal(msg.fill.fee_ratio.mantissa * (
                                    10 ** msg.fill.fee_ratio.exponent))

                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=tracked_order.trade_type,
                                percent_token=fill_token,
                                flat_fees=[TokenAmount(amount=Decimal(fee_amount), token=fill_token)],
                            )
                            trade_update = TradeUpdate(
                                trade_id=str(msg.fill.trade_id),
                                client_order_id=client_order_id,
                                exchange_order_id=str(msg.fill.exchange_order_id),
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=Decimal(fill_base_amount),
                                fill_quote_amount=Decimal(fill_quote_amount),
                                fill_price=Decimal(fill_price),
                                fill_timestamp=msg.fill.transact_time * 1e-9,
                            )
                            self._order_tracker.process_trade_update(trade_update)

                        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                        if tracked_order is not None:
                            new_state = OrderState.PARTIALLY_FILLED
                            if msg.fill.leaves_quantity <= 0:
                                new_state = OrderState.FILLED

                            order_update = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=msg.fill.transact_time * 1e-9,
                                new_state=new_state,
                                client_order_id=client_order_id,
                                exchange_order_id=str(msg.fill.exchange_order_id),
                            )
                            self._order_tracker.process_order_update(order_update=order_update)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)

            all_fills_response = await self._api_get(
                path_url=CONSTANTS.FILLS_PATH_URL.format(self.cube_subaccount_id),
                params={"orderIds": exchange_order_id},
                is_auth_required=True,
                limit_id=CONSTANTS.FILLS_PATH_URL_ID,
            )

            fills_data = all_fills_response.get("result", {}).get("fills", [])

            for fill in fills_data:
                exchange_order_id = str(fill.get("orderId"))
                fee_token = self._token_info[fill["feeAssetId"]]

                fee_decimals = fee_token.get("decimals")
                fee_amount = Decimal(fill.get("feeAmount", 0)) / (10 ** fee_decimals)

                base_token_info = self._token_info[await self.token_symbol_to_token_id(order.base_asset)]
                quote_token_info = self._token_info[await self.token_symbol_to_token_id(order.quote_asset)]

                base_decimals = base_token_info.get("decimals")
                quote_decimals = quote_token_info.get("decimals")
                base_precision, quote_precision = await self.get_base_quote_precision(
                    order.trading_pair
                )

                fill_base_amount = Decimal(fill["baseAmount"]) / (10 ** base_decimals)
                fill_base_amount = fill_base_amount.quantize(base_precision, rounding=ROUND_DOWN)
                fill_quote_amount = Decimal(fill["quoteAmount"]) / (10 ** quote_decimals)
                fill_quote_amount = fill_quote_amount.quantize(quote_precision, rounding=ROUND_DOWN)
                # price = Decimal(fill["price"]) / (10 ** quote_token_info.get("decimals"))
                price = Decimal(fill_quote_amount) / Decimal(fill_base_amount)

                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=fee_token.get("symbol").upper(),
                    flat_fees=[TokenAmount(amount=Decimal(fee_amount), token=fee_token.get("symbol").upper())],
                )
                trade_update = TradeUpdate(
                    trade_id=str(fill.get("tradeId")),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(fill_base_amount),
                    fill_quote_amount=Decimal(fill_quote_amount),
                    fill_price=Decimal(price),
                    fill_timestamp=fill["filledAt"] * 1e-9,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        # Response Example:
        # {
        #     "result": {
        #         "name": "primary",
        #         "orders": [
        #             {
        #                 "orderId": 774262014,
        #                 "marketId": 100006,
        #                 "side": "Bid",
        #                 "price": 10100,
        #                 "qty": 1,
        #                 "createdAt": 1710257649309918309,
        #                 "modifiedAt": 1710257660587607288,
        #                 "canceledAt": 1710257715967425433,
        #                 "modifies": [
        #                     {
        #                         "price": 10000,
        #                         "quantity": 1,
        #                         "modifiedAt": 1710257649309918309
        #                     }
        #                 ],
        #                 "reason": "Requested",
        #                 "status": "canceled",
        #                 "clientOrderId": 1710257649137,
        #                 "timeInForce": 1,
        #                 "orderType": 0,
        #                 "selfTradePrevention": 0,
        #                 "cancelOnDisconnect": false,
        #                 "postOnly": false
        #             },
        #             {
        #                 "orderId": 770248872,
        #                 "marketId": 100006,
        #                 "side": "Ask",
        #                 "price": 14578,
        #                 "qty": 1,
        #                 "createdAt": 1710232107014998560,
        #                 "filledAt": 1710232107014998560,
        #                 "filledTotal": {
        #                     "baseAmount": "10000000",
        #                     "quoteAmount": "1487500",
        #                     "feeAmount": "1190",
        #                     "feeAssetId": 7,
        #                     "filledAt": 1710232107014998560
        #                 },
        #                 "fills": [
        #                     {
        #                         "baseAmount": "10000000",
        #                         "quoteAmount": "1487500",
        #                         "feeAmount": "1190",
        #                         "feeAssetId": 7,
        #                         "filledAt": 1710232107014998560,
        #                         "tradeId": 1187039,
        #                         "baseBatchId": "ab72f0fd-c571-4949-835f-49fd30895e5e",
        #                         "quoteBatchId": "62e622f7-4a6b-4c99-a783-0c3716db01c8",
        #                         "baseSettled": true,
        #                         "quoteSettled": true
        #                     }
        #                 ],
        #                 "settled": true,
        #                 "status": "filled",
        #                 "clientOrderId": 1710232106907,
        #                 "timeInForce": 1,
        #                 "orderType": 2,
        #                 "selfTradePrevention": 0,
        #                 "cancelOnDisconnect": false,
        #                 "postOnly": false
        #             }
        #         ]
        #     }
        # }
        orders_rsp = await self._api_get(
            path_url=CONSTANTS.ORDER_PATH_URL.format(self.cube_subaccount_id),
            params={
                "createdBefore": int((tracked_order.creation_timestamp + 30) * 1e9),
                "limit": 500,
            },
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_PATH_URL_ID,
        )

        orders_data = orders_rsp.get("result", {}).get("orders", [])

        # find the order with the same client order id
        updated_order_data = next(
            (order for order in orders_data if int(order["clientOrderId"]) == int(tracked_order.client_order_id)), None
        )

        if updated_order_data is None:
            # If the order is not found in the response, return an OrderUpdate with the same status as before
            self.logger().info(f"Order Update for {tracked_order.client_order_id} not found in the response.")

            return OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self._time_synchronizer.time(),
                new_state=tracked_order.current_state,
            )

        new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"].lower()]

        create_timestamp = updated_order_data.get("createdAt", 0) * 1e-9
        modified_timestamp = updated_order_data.get("modifiedAt", 0) * 1e-9
        canceled_timestamp = updated_order_data.get("canceledAt", 0) * 1e-9
        filled_timestamp = updated_order_data.get("filledAt", 0) * 1e-9

        update_timestamp = max(create_timestamp, modified_timestamp, canceled_timestamp, filled_timestamp)

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["orderId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        # Balance Response Example:
        # {
        #     "result": {
        #         "38393": {
        #             "name": "primary",
        #             "inner": [
        #                 {
        #                     "amount": "0",
        #                     "receivedAmount": "0",
        #                     "pendingDeposits": "0",
        #                     "assetId": 5,
        #                     "accountingType": "asset"
        #                 },
        #                 {
        #                     "amount": "1486310",
        #                     "receivedAmount": "1486310",
        #                     "pendingDeposits": "0",
        #                     "assetId": 7,
        #                     "accountingType": "asset"
        #                 }
        #             ]
        #         }
        #     }
        # }
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        positions = await self._api_get(path_url=CONSTANTS.ACCOUNTS_PATH_URL.format(self.cube_subaccount_id),
                                        is_auth_required=True, limit_id=CONSTANTS.ACCOUNTS_PATH_URL_ID)
        token_map = await self.token_id_map()
        token_info = await self.token_info()

        balances = positions.get("result", {}).get(str(self.cube_subaccount_id), {}).get("inner", [])
        for balance_entry in balances:
            asset_name = token_map.get(balance_entry["assetId"], "UNKNOWN")
            decimals = token_info.get(balance_entry["assetId"], {}).get("decimals", 1)
            total_balance = Decimal(balance_entry.get("amount", "0")) / (10 ** decimals)
            # If _account_available_balances exists, use existing value, otherwise use total_balance
            self._account_available_balances[asset_name] = self._account_available_balances.get(
                asset_name, total_balance
            )
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        markets = exchange_info.get("result", {}).get("markets", [])
        assets = {asset["assetId"]: asset for asset in exchange_info.get("result", {}).get("assets", [])}

        self._set_token_info(assets)

        mapping_token_id = bidict()
        mapping_symbol = bidict()
        mapping_market_id = bidict()

        for asset in assets.values():
            mapping_token_id[asset["assetId"]] = asset["symbol"].upper()

        self.logger().debug(f"markets: {markets}")

        for market in filter(cube_utils.is_exchange_information_valid, markets):
            self.logger().debug(f"Processing market {market}")
            base_asset = assets[market.get("baseAssetId")]
            quote_asset = assets[market.get("quoteAssetId")]
            mapping_symbol[market["symbol"].upper()] = combine_to_hb_trading_pair(
                base=base_asset["symbol"].upper(), quote=quote_asset["symbol"].upper()
            )
            try:
                mapping_market_id[market.get("marketId")] = combine_to_hb_trading_pair(
                    base=base_asset["symbol"].upper(), quote=quote_asset["symbol"].upper()
                )
            except ValueDuplicationError:
                # Ignore the error if the key already exists
                self.logger().debug(f"Duplicate key found for {market.get('marketId')}")
                pass

        self._set_trading_pair_symbol_map(mapping_symbol)
        self._set_trading_pair_market_id_map(mapping_market_id)
        self._set_token_id_map(mapping_token_id)

    def _set_trading_pair_symbol_map(self, trading_pair_and_symbol_map: Optional[Mapping[str, str]]):
        """
        Method added to allow the pure Python subclasses to set the value of the map
        """
        self._trading_pair_symbol_map = trading_pair_and_symbol_map

    def _set_trading_pair_market_id_map(self, trading_pair_market_id_map: Optional[Mapping[int, str]]):
        """
        Method added to allow the pure Python subclasses to set the value of the map
        """
        self._trading_pair_market_id_map = trading_pair_market_id_map

    def _set_token_id_map(self, token_id_map: Optional[Mapping[int, str]]):
        """
        Method added to allow the pure Python subclasses to set the value of the map
        """
        self._token_id_map = token_id_map

    def _set_token_info(self, token_info: Dict[str, Any]):
        """
        Method added to allow the pure Python subclasses to set the value of the map
        """
        self._token_info = token_info

    def trading_pair_symbol_map_ready(self):
        """
        Checks if the mapping from exchange symbols to client trading pairs has been initialized

        :return: True if the mapping has been initialized, False otherwise
        """
        symbol_map_ready = False
        market_id_map_ready = False
        token_info_ready = False
        token_id_map_read = False

        if self._trading_pair_symbol_map is not None and len(self._trading_pair_symbol_map) > 0:
            symbol_map_ready = True

        if self._trading_pair_market_id_map is not None and len(self._trading_pair_market_id_map) > 0:
            market_id_map_ready = True

        if self._token_info is not None and len(self._token_info) > 0:
            token_info_ready = True

        if self._token_id_map is not None and len(self._token_id_map) > 0:
            token_id_map_read = True

        return symbol_map_ready and market_id_map_ready and token_info_ready and token_id_map_read

    def trading_rule_ready(self):
        trading_rules_ready = False

        if self._trading_rules is not None and len(self._trading_rules) > 0:
            trading_rules_ready = True

        return trading_rules_ready

    async def exchange_market_id_associated_to_pair(self, trading_pair: str) -> str:
        """
        Used to translate a trading pair from the client notation to the exchange market id

        :param trading_pair: trading pair in client notation

        :return: trading pair in exchange market id
        """
        market_id_map = await self.trading_pair_market_id_map()

        return market_id_map.inverse[trading_pair]

    async def trading_pair_market_id_map(self):
        if not self.trading_pair_symbol_map_ready():
            async with self._mapping_initialization_lock:
                if not self.trading_pair_symbol_map_ready():
                    await self._initialize_trading_pair_symbol_map()
        current_map = self._trading_pair_market_id_map or bidict()
        return current_map

    async def token_symbol_to_token_id(self, token_symbol: str) -> int:
        """
        Used to translate a token symbol from the client notation to the exchange token id

        :param token_symbol: token symbol in client notation

        :return: token symbol in exchange token id
        """
        token_id_map = await self.token_id_map()
        return token_id_map.inverse[token_symbol]

    async def token_id_map(self):
        if not self.trading_pair_symbol_map_ready():
            async with self._mapping_initialization_lock:
                if not self.trading_pair_symbol_map_ready():
                    await self._initialize_trading_pair_symbol_map()
        current_map = self._token_id_map or bidict()
        return current_map

    async def token_info(self):
        if not self.trading_pair_symbol_map_ready():
            async with self._mapping_initialization_lock:
                if not self.trading_pair_symbol_map_ready():
                    await self._initialize_trading_pair_symbol_map()
        current_map = self._token_info or {}
        return current_map

    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        """
        Used to translate a trading pair from the client notation to the exchange notation

        :param trading_pair: trading pair in client notation

        :return: trading pair in exchange notation
        """
        symbol_map = await self.trading_pair_symbol_map()
        return symbol_map.inverse[trading_pair]

    async def trading_pair_symbol_map(self):
        if not self.trading_pair_symbol_map_ready():
            async with self._mapping_initialization_lock:
                if not self.trading_pair_symbol_map_ready():
                    await self._initialize_trading_pair_symbol_map()
        current_map = self._trading_pair_symbol_map or bidict()
        return current_map

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_BOOK_PATH_URL,
        )

        tickers = resp_json.get("result", [])
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        # Filter tickers that match the trading pair
        tickers = [ticker for ticker in tickers if ticker["ticker_id"].upper() == symbol]
        # Get the first item
        ticker = tickers[0]

        if ticker.get("last_price", 0) is None:
            return float(0)

        return float(ticker.get("last_price", 0))

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
        prefix = CONSTANTS.HBOT_ORDER_ID_PREFIX
        new_order_id = get_new_numeric_client_order_id(nonce_creator=self._nonce_creator,
                                                       max_id_bit_count=CONSTANTS.MAX_ORDER_ID_LEN)
        numeric_order_id = f"{prefix}{new_order_id}"

        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
                order_id=numeric_order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return numeric_order_id

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
        prefix = CONSTANTS.HBOT_ORDER_ID_PREFIX
        new_order_id = get_new_numeric_client_order_id(nonce_creator=self._nonce_creator,
                                                       max_id_bit_count=CONSTANTS.MAX_ORDER_ID_LEN)
        numeric_order_id = f"{prefix}{new_order_id}"
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
                order_id=numeric_order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return numeric_order_id

    async def get_price_scaler(self, trading_pair: str) -> float:
        """
        Returns the price scaler for a trading pair
        :param trading_pair: the trading pair to get the price scaler
        :return: the price scaler
        """
        while not self.trading_rule_ready():
            await asyncio.sleep(0.1)

        trading_rule: TradingRule = self._trading_rules.get(trading_pair)

        if trading_rule is None:
            self.logger().error(f"get_price_scaler: Trading rule for trading pair {trading_pair} is not defined")
            return float("1")

        if trading_rule.min_price_increment is None:
            self.logger().error(f"get_price_scaler: min_price_increment for trading pair {trading_pair} is not defined")
            return float("1")

        min_price_increment = trading_rule.min_price_increment

        if math.isnan(min_price_increment):
            self.logger().error(f"get_price_scaler: min_price_increment for trading pair {trading_pair} is NaN")
            return float("1")

        return float(min_price_increment)

    async def get_quantity_scaler(self, trading_pair: str) -> float:
        """
        Returns the quantity scaler for a trading pair
        :param trading_pair: the trading pair to get the quantity scaler
        :return: the quantity scaler
        """
        while not self.trading_rule_ready():
            await asyncio.sleep(0.1)

        trading_rule: TradingRule = self._trading_rules.get(trading_pair)

        if trading_rule is None:
            self.logger().error(f"get_quantity_scaler: Trading rule for trading pair {trading_pair} is not defined")
            return float("1")

        if trading_rule.min_order_size is None:
            self.logger().error(f"get_quantity_scaler: min_order_size for trading pair {trading_pair} is not defined")
            return float("1")

        min_order_size = trading_rule.min_order_size

        if math.isnan(min_order_size):
            self.logger().error(f"get_quantity_scaler: min_order_size for trading pair {trading_pair} is NaN")
            return float("1")

        return float(min_order_size)

    async def get_base_quote_precision(self, trading_pair: str) -> Tuple[Decimal, Decimal]:
        """
        Returns the base and quote precision for a trading pair
        :param trading_pair: the trading pair to get the base and quote precision
        :return: the base and quote precision
        """
        while not self.trading_rule_ready():
            await asyncio.sleep(0.1)

        trading_rule: TradingRule = self._trading_rules.get(trading_pair)
        base_precision = trading_rule.min_order_size
        quote_precision = trading_rule.min_notional_size
        return base_precision, quote_precision

    def check_domain(self, domain: str):
        """
        Checks if the domain value is valid
        :param domain: the domain value to check
        :return: True if the domain value is valid, False otherwise
        """
        valid_domains = [CONSTANTS.DEFAULT_DOMAIN, CONSTANTS.TESTNET_DOMAIN]
        if domain not in valid_domains:
            self.logger().error(f"Invalid domain: {domain}. Domain must be one of {valid_domains}")
            return False
        return True

    async def all_trading_pairs(self) -> List[str]:
        """
        Returns a list of all trading pairs on the exchange
        :return: a list of all trading pairs on the exchange
        """
        all_pairs: bidict = await self.trading_pair_symbol_map()
        all_pairs_inverse = list(all_pairs.inverse)

        return all_pairs_inverse
