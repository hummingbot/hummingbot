import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from _decimal import Decimal

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.chainflip_lp import (
    chainflip_lp_constants as CONSTANTS,
    chainflip_lp_web_utils as web_utils,
)
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_api_order_book_data_source import (
<<<<<<< HEAD
    ChainflipLpAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_source import ChainflipLpDataSource
=======
    ChainflipLPAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_source import ChainflipLPDataSource
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent
from hummingbot.core.network_iterator import NetworkStatus, safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter  # pragma: no cover


class ChainflipLpExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        chainflip_lp_api_url: str,
        chainflip_lp_address: str,
        chainflip_eth_chain: str,
        chainflip_usdc_chain: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self.chain_config = CONSTANTS.DEFAULT_CHAIN_CONFIG.copy()
        self.chain_config["ETH"] = chainflip_eth_chain
        self.chain_config["USDC"] = chainflip_usdc_chain
<<<<<<< HEAD
        self._data_source = ChainflipLpDataSource(
=======
        self._data_source = ChainflipLPDataSource(
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
            connector=self,
            address=chainflip_lp_address,
            rpc_api_url=chainflip_lp_api_url,
            domain=self._domain,
            trading_pairs=trading_pairs,
            trading_required=trading_required,
            chain_config=self.chain_config,
        )
        super().__init__(client_config_map=client_config_map)
        self._data_source.configure_throttler(throttler=self._throttler)
        self._forwarders = []
        self._configure_event_forwarders()

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> AuthBase:
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> Optional[int]:
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.CLIENT_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        raise NotImplementedError  # pragma: no cover

    @property
    def trading_pairs_request_path(self) -> str:
        raise NotImplementedError  # pragma: no cover

    @property
    def check_network_request_path(self) -> str:
        raise NotImplementedError  # pragma: no cover

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
        await super().start_network()
<<<<<<< HEAD
<<<<<<< HEAD
        await self._data_source.start()
=======

        market_symbols = [
            await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            for trading_pair in self._trading_pairs
        ]
        await self._data_source.start(market_symbols=market_symbols)
>>>>>>> 63271bb03 ((refactor) update and cleanup chainflip connector codes)
=======
        await self._data_source.start()
>>>>>>> 9979ea9b9 ((refactor) update code and tests)

    async def stop_network(self):
        """
        This function is executed when the connector is stopped. It performs a general cleanup and stops all background
        tasks that require the connection with the exchange to work.
        """
        await super().stop_network()
        await self._data_source.stop()

    async def check_network(self) -> NetworkStatus:
        """
        Checks connectivity with the exchange using the API
        """
        try:
            status = await self._data_source.exchange_status()
        except asyncio.CancelledError:
            raise
        except Exception:
            status = NetworkStatus.NOT_CONNECTED
        return status

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return WebAssistantsFactory(throttler=self._throttler)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        # Not used in Chainflip LP
        raise NotImplementedError  # pragma: no cover

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    def _is_user_stream_initialized(self):
        return self._data_source.is_started()

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]):
        raise NotImplementedError

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
<<<<<<< HEAD
        return ChainflipLpAPIOrderBookDataSource(
=======
        return ChainflipLPAPIOrderBookDataSource(
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
            trading_pairs=self._trading_pairs, connector=self, data_source=self._data_source, domain=self.domain
        )

    def _create_user_stream_tracker(self):
        # not used in chainflip LP
        return None

    def _create_user_stream_tracker_task(self):
        # Not used in chainflip lp
        return None

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        # Not used in chainflip lp
        raise NotImplementedError()  # pragma: no cover

    async def _initialize_trading_pair_symbol_map(self):
        exchange_info = None
        try:
            mapping = await self._data_source.symbols_map()
            self._set_trading_pair_symbol_map(mapping)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")
        return exchange_info

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
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        hex_order_id = f"0x{order_id.encode('utf-8').hex()}"
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
            max_id_len=self.client_order_id_max_length,
        )
        hex_order_id = f"0x{order_id.encode('utf-8').hex()}"
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

    async def _update_balances(self):
        self.logger().info("Updating balances")
        all_balances = await self._data_source.all_balances()
        self.logger().info("New balances: " + str(all_balances))

        self._account_available_balances.clear()
        self._account_balances.clear()

        for token in all_balances:
            self._account_balances[token] = all_balances[token]
            self._account_available_balances[token] = all_balances[token]

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
        **kwargs,
    ) -> Tuple[str, float]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

        result = await self._data_source.place_order(
            order_id=order_id,
            trading_pair=symbol,
            amount=amount,
            trade_type=trade_type,
            order_type=order_type,
            price=price,
        )

        return result

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        return await self._data_source.place_cancel(order_id, symbol, tracked_order)
<<<<<<< HEAD
<<<<<<< HEAD

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        try:
            if len(orders) > 0:
                trade_updates = await self._data_source.get_order_fills(orders)
=======
    
    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        try:
            if len(orders) > 0:
                trade_updates = await self._data_source.get_order_fills(
                    orders
                )
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
=======

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        try:
            if len(orders) > 0:
                trade_updates = await self._data_source.get_order_fills(orders)
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
                for trade_update in trade_updates:
                    self._order_tracker.process_trade_update(trade_update=trade_update)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().warning(f"Error fetching trades updates. {e}")
<<<<<<< HEAD
<<<<<<< HEAD

    async def _update_trading_rules(self):
        trading_rules_list = await self._data_source.all_trading_rules()
        self._trading_rules = {trading_rule.trading_pair: trading_rule for trading_rule in trading_rules_list}

=======
    
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
=======

>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # not used
        raise NotImplementedError

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
<<<<<<< HEAD
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    async def _user_stream_event_listener(self):
        # no user stream in chainflip lp
        raise NotImplementedError

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        # not used in chainflip LP
=======
        raise NotImplementedError

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        raise NotImplementedError

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        raise NotImplementedError

    async def _user_stream_event_listener(self):
        raise NotImplementedError

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
        raise NotImplementedError

    def _configure_event_forwarders(self):

        event_forwarder = EventForwarder(to_function=self._process_user_order_update)
        self._forwarders.append(event_forwarder)
        self._data_source.add_listener(event_tag=MarketEvent.OrderUpdate, listener=event_forwarder)

        event_forwarder = EventForwarder(to_function=self._process_balance_event)
        self._forwarders.append(event_forwarder)
        self._data_source.add_listener(event_tag=AccountEvent.BalanceEvent, listener=event_forwarder)

    def _process_balance_event(self, event: BalanceUpdateEvent):
        self._account_balances[event.asset_name] = event.total_balance
        self._account_available_balances[event.asset_name] = event.available_balance

    def _process_user_order_update(self, order_update: OrderUpdate):
        tracked_order = self._order_tracker.all_updatable_orders.get(order_update.client_order_id)

        if tracked_order is not None:
            self.logger().debug(f"Processing order update {order_update}\nUpdatable order {tracked_order.to_json()}")
            order_update_to_process = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=order_update.update_timestamp,
                new_state=order_update.new_state,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=order_update.exchange_order_id,
            )
            self._order_tracker.process_order_update(order_update=order_update_to_process)

    async def get_last_traded_prices(self, trading_pairs: List[str]):
<<<<<<< HEAD
        price_dict = {}
        for pair in trading_pairs:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=pair)
            price = await self._data_source.get_last_traded_price(symbol)
            price_dict[pair] = price
        return price_dict
=======
        price_list = []
        for pair in trading_pairs:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=pair)
            price_map = await self._data_source.get_last_traded_price(symbol)
            price_list.append(price_map)
        return price_list
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
