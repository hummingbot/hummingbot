from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import grpc

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.penumbra.penumbra_api_order_book_data_source import PenumbraAPIOrderBookDataSource
from hummingbot.connector.exchange.penumbra.penumbra_api_user_stream_data_source import PenumbraAPIUserStreamDataSource
from hummingbot.connector.exchange.penumbra.penumbra_constants import EXCHANGE_NAME, RATE_LIMITS
from hummingbot.connector.exchange.penumbra.penumbra_utils import build_api_factory
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.view.v1alpha1.view_pb2 import (
    _builder as ViewBuilder,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.view.v1alpha1.view_pb2_grpc import (
    ViewProtocolServiceStub as ViewProtocolServiceClient,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.penumbra_api_data_source import (
    PenumbraAPIDataSource as PenumbraGateway,
)
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class PenumbraExchange(ExchangePyBase):

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 pclientd_url: str,
                 gateway_url: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._pclientd_url = pclientd_url
        self._gateway_url = gateway_url

        self.gateway = PenumbraGateway(
            connector_spec={
                "network":
                "testnet",  # Eventually make this an arg once we have a mainnet
                "chain": "penumbra",
            },
            client_config_adaptor=client_config_map,
            connection_secure=False)

        super().__init__(client_config_map=client_config_map)
        self.type = "penumbra"

    @property
    def name(self) -> str:
        return EXCHANGE_NAME

    @property
    def authenticator(self) -> AuthBase:
        return None

    # Need to implement all abstract methods from ExchangePyBase
    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return RATE_LIMITS

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    @property
    def domain(self) -> str:
        return self._pclientd_url

    async def _initialize_trading_pair_symbol_map(self):
        try:
            markets = await self.gateway.get_all_market_metadata()
            # for us the exchange symbol is the same as the trading pair, so just make a map of keys to keys
            self._trading_pair_symbol_map = {k: k for k in markets.keys()}
        except Exception:
            self.logger().exception(
                "There was an error requesting exchange info for Penumbra.")

    def _initialize_trading_pair_symbols_from_exchange_info(
            self, exchange_info: Dict[str, Any]):
        self._initialize_trading_pair_symbol_map()

    @property
    def client_order_id_max_length(self) -> int:
        return None

    @property
    def client_order_id_prefix(self) -> str:
        return ""

    @property
    def trading_rules_request_path(self) -> str:
        return

    @property
    def trading_pairs_request_path(self) -> str:
        return

    @property
    def check_network_request_path(self) -> str:
        return

    def _is_request_exception_related_to_time_synchronizer(
            self, request_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(
            self, status_update_exception: Exception) -> bool:
        # TODO: Consider adding a custom exception for this
        return False

    def _is_order_not_found_during_cancelation_error(
            self, cancelation_exception: Exception) -> bool:
        return False

    # ------------------------------------------------------ WIP
    #! Overridden method
    def get_order_book(self, trading_pair: str) -> OrderBook:
        """
        Returns the current order book for a particular market

        :param trading_pair: the pair of tokens for which the order book should be retrieved
        """
        print("get_order_book -- overriden method, here to see if this is executed, if so reevaluate until websockets are implemented")
        return 

    async def _update_balances(self):
        print("~~~~~~~Trying to get balances~~~~~~~")
        return
        # Create new grpc.Channel + client
        channel = grpc.insecure_channel(self._pclientd_url)
        client = ViewProtocolServiceClient(channel=channel)

        print("??")
        print(BalancesRequest())
        balances = await client.Balances(BalancesRequest())


        print('Balancees: ', balances)

        print("_update_balances")

    # ------------------------------------------------------ WIP

    # TODO: Implement the below methods

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        print("_place_cancel")
        raise NotImplementedError

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
        print("_place_order")
        raise NotImplementedError

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        print("_get_fee")
        raise NotImplementedError

    async def _update_trading_fees(self):
        print("_update_trading_fees")
        raise NotImplementedError

    async def _user_stream_event_listener(self):
        print("_user_stream_event_listener")
        raise NotImplementedError

    async def _format_trading_rules(
            self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        print("_format_trading_rules")
        raise NotImplementedError

    async def _all_trade_updates_for_order(
            self, order: InFlightOrder) -> List[TradeUpdate]:
        print("_all_trade_updates_for_order")
        raise NotImplementedError

    async def _request_order_status(
            self, tracked_order: InFlightOrder) -> OrderUpdate:
        print("_request_order_status")
        raise NotImplementedError

    # Below are mostly helpers, however we need to implement the order book data source
    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return PenumbraAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
        )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return build_api_factory(throttler=self._throttler, auth=self._auth)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return PenumbraAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            api_factory=self._web_assistants_factory,
            connector=self,
            domain=self.domain,
        )


# Resources:
# Working torwards https://hummingbot.org/strategies/avellaneda-market-making/
# https://hummingbot.org/developers/strategies/tutorial/#what-youll-learn
# https://www.youtube.com/watch?v=ZbkkGvB-fis
# M1 & M2 Chip Setup https://hummingbot.org/installation/mac/#conda-and-apple-m1m2-chips

# Installation command copypasta
'''
conda activate hummingbot
./install
./compile
./start

'''
