from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, cast

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.gateway.clob.backup import clob_constants as constant, clob_web_utils as web_utils
from hummingbot.connector.gateway.clob.backup.clob_api_order_book_data_source import CLOBAPIOrderBookDataSource
from hummingbot.connector.gateway.clob.backup.clob_api_user_stream_data_source import CLOBAPIUserStreamDataSource
from hummingbot.connector.gateway.clob.backup.clob_types import OrderSide, OrderStatus, OrderType
from hummingbot.core.data_type.common import OrderType as HummingbotOrderType, TradeType as HummingbotOrderSide
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, DeductedFromReturnsTradeFee
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class CLOBExchange(ExchangePyBase):

    def __init__(
        self,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = constant.DEFAULT_DOMAIN,
    ):
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs

        super().__init__()

    @property
    def domain(self):
        return self._domain

    def name(self):
        if self._domain == constant.DEFAULT_DOMAIN:
            return "clob"
        else:
            return f"clob_{self._domain}"

    @property
    def authenticator(self):
        # TODO do we need to override this method?!!!
        pass

    @property
    def rate_limits_rules(self):
        return constant.RATE_LIMITS_RULES

    @property
    def client_order_id_max_length(self):
        return constant.MAX_CLIENT_ORDER_ID_LENGTH

    @property
    def client_order_id_prefix(self):
        return constant.CLIENT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return constant.TRADING_RULES_REQUEST_PATH

    @property
    def check_network_request_path(self):
        return constant.CHECK_NETWORK_REQUEST_PATH

    def supported_order_types(self):
        # TODO Should we include IoC and Post Only?!!!
        # TODO How about OrderType.LIMIT_MAKER?!!!
        return [OrderType.LIMIT]

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: HummingbotOrderType,
        order_type: HummingbotOrderSide,
        price: Decimal
    ) -> Tuple[str, float]:
        order_type = OrderType.from_hummingbot(trade_type)
        order_side = OrderSide.from_hummingbot(order_type)

        created_order = await GatewayHttpClient.get_instance().clob_post_orders(
            chain="solana",  # TODO fix!!!
            network="mainnet-beta",  # TODO fix!!!
            connector="serum",  # TODO fix!!!
            order={
                "id": order_id,
                "marketName": trading_pair,
                "ownerAddress": "",  # TODO fix!!!
                "payerAddress": "",  # TODO fix!!!
                "side": order_side,
                "price": price,
                "amount": amount,
                "type": order_type,
            }
        )

        if created_order.get("status") == OrderStatus.CREATION_PENDING:
            self.logger().warning(f"""The creation of the order "{order_id}" was submitted but it wasn't possible to confirm if it succeeded or not.""")

        client_order_id = str(created_order["id"])
        transaction_time = 0.0  # TODO fix!!!

        return client_order_id, transaction_time

    async def _place_cancel(
        self,
        order_id: str,
        trading_pair: str
    ) -> bool:
        canceled_order = await GatewayHttpClient.get_instance().clob_delete_orders(
            chain="solana",  # TODO fix!!!
            network="mainnet-beta",  # TODO fix!!!
            connector="serum",  # TODO fix!!!
            order={
                "id": order_id,
                "marketName": trading_pair,
                "ownerAddress": "FMosjpvtAxwL6GFDSL31o9pU5somKjifbkt32bEgLddf"  # TODO fix!!!
            }
        )

        if canceled_order.get("status") == OrderStatus.CANCELED:
            return True
        elif canceled_order.get("status") == OrderStatus.CANCELATION_PENDING:
            self.logger().warning(f"""The cancelation of the order "{order_id}" was submitted but it wasn't possible to confirm if it succeeded or not.""")

        return False

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: HummingbotOrderType,
        order_side: HummingbotOrderSide,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None
    ) -> AddedToCostTradeFee:
        is_maker = order_type is OrderType.LIMIT_MAKER

        # TODO check if this cast will work properly!!!
        return cast(DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker)), AddedToCostTradeFee)

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        # TODO binance is not implementing this method, should we implement it?!!!
        pass

    def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        # TODO should we implement this?!!!
        pass

    def _format_trading_rules(self):
        # TODO do we need to override this method?!!!
        raise NotImplementedError

    def _update_order_status(self):
        # TODO do we need to override this method?!!!
        raise NotImplementedError

    def _update_balances(self):
        # TODO do we need to override this method?!!!
        raise NotImplementedError

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        # TODO do we need to override this method?!!!
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        # TODO check if all the parameters are needed!!!
        return CLOBAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        # TODO check if all the parameters are needed!!!
        return CLOBAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def c_stop_tracking_order(self, order_id):
        # TODO binance is not implementing this method, should we implement it?!!!
        pass

    async def _status_polling_loop_fetch_updates(self):
        # TODO do we need to override this method?!!!
        # await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

    @property
    def trading_pairs_request_path(self):
        return constant.TRADING_PAIRS_REQUEST_PATH

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        # TODO fix!!!
        pass
