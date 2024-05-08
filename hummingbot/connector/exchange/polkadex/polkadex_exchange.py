import asyncio
import math
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from _decimal import Decimal

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS, polkadex_web_utils as web_utils
from hummingbot.connector.exchange.polkadex.polkadex_api_order_book_data_source import PolkadexAPIOrderBookDataSource
from hummingbot.connector.exchange.polkadex.polkadex_data_source import PolkadexDataSource
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent
from hummingbot.core.network_iterator import NetworkStatus, safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter  # pragma: no cover


class PolkadexExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        polkadex_seed_phrase: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._data_source = PolkadexDataSource(
            connector=self, seed_phrase=polkadex_seed_phrase, domain=self._domain, trading_pairs=trading_pairs, trading_required=trading_required
        )
        super().__init__(client_config_map=client_config_map)
        self._data_source.configure_throttler(throttler=self._throttler)
        self._forwarders = []
        self._open_oder_fetching_timestamp = float(0)
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
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    async def start_network(self):
        await super().start_network()

        market_symbols = [
            await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            for trading_pair in self._trading_pairs
        ]
        await self._data_source.start(market_symbols=market_symbols)

    async def stop_network(self):
        """
        This function is executed when the connector is stopped. It performs a general cleanup and stops all background
        tasks that require the connection with the exchange to work.
        """
        await super().stop_network()
        await self._data_source.stop()

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

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

    # === Orders placing ===

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
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        hex_order_id = f"0x{order_id.encode('utf-8').hex()}"
        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

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
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        hex_order_id = f"0x{order_id.encode('utf-8').hex()}"
        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        # Polkadex does not use a time synchronizer
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_MESSAGE in str(cancelation_exception)

    async def _execute_order_cancel_and_process_update(self, order: InFlightOrder) -> bool:
        new_order_state = await self._place_cancel(order.client_order_id, order)
        cancelled = new_order_state in [OrderState.CANCELED, OrderState.PENDING_CANCEL]
        if cancelled:
            update_timestamp = self.current_timestamp
            if update_timestamp is None or math.isnan(update_timestamp):
                update_timestamp = self._time()
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=update_timestamp,
                new_state=new_order_state,
            )
            self._order_tracker.process_order_update(order_update)
        return cancelled

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> OrderState:
        await tracked_order.get_exchange_order_id()
        market_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)

        new_order_state = await self._data_source.cancel_order(
            order=tracked_order, market_symbol=market_symbol, timestamp=self.current_timestamp
        )

        return new_order_state

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
            market_symbol=symbol,
            client_order_id=order_id,
            price=price,
            amount=amount,
            trade_type=trade_type,
            order_type=order_type,
        )

        return result

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
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
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

    async def _trading_fees_polling_loop(self):
        pass

    async def _update_trading_fees(self):
        raise NotImplementedError  # pragma: no cover

    async def _user_stream_event_listener(self):
        # Not required in Polkadex since all event are processed using the data source PubSub
        pass  # pragma: no cover

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        # Not used in Polkadex
        raise NotImplementedError  # pragma: no cover

    async def _update_balances(self):
        all_balances = await self._data_source.all_balances()

        self._account_available_balances.clear()
        self._account_balances.clear()

        for token_balance_info in all_balances:
            self._account_balances[token_balance_info["token_name"]] = token_balance_info["total_balance"]
            self._account_available_balances[token_balance_info["token_name"]] = token_balance_info["available_balance"]

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        try:
            if len(orders) != 0:
                minimum_creation_timestamp = min([order.creation_timestamp for order in orders])
                current_timestamp = self.current_timestamp
                trade_updates = await self._data_source.get_all_fills(
                    from_timestamp=minimum_creation_timestamp,
                    to_timestamp=current_timestamp,
                    orders=orders,
                )

                for trade_update in trade_updates:
                    self._order_tracker.process_trade_update(trade_update=trade_update)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().warning(f"Error fetching trades updates. {e}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # not used
        raise NotImplementedError

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        symbol = await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)
        await tracked_order.get_exchange_order_id()
        order_update = await self._data_source.order_update(order=tracked_order, market_symbol=symbol)
        return order_update

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return WebAssistantsFactory(throttler=self._throttler)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return PolkadexAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            data_source=self._data_source,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        # Not used in Polkadex
        raise NotImplementedError  # pragma: no cover

    def _is_user_stream_initialized(self):
        # Polkadex does not have private websocket endpoints
        return self._data_source.is_started()

    def _create_user_stream_tracker(self):
        # Polkadex does not use a tracker for the private streams
        return None

    def _create_user_stream_tracker_task(self):
        # Polkadex does not use a tracker for the private streams
        return None

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        # Not used in Bluefin
        raise NotImplementedError()  # pragma: no cover

    async def _initialize_trading_pair_symbol_map(self):
        exchange_info = None
        try:
            mapping = await self._data_source.symbols_map()
            self._set_trading_pair_symbol_map(mapping)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")
        return exchange_info

    async def _update_trading_rules(self):
        trading_rules_list = await self._data_source.all_trading_rules()
        self._trading_rules = {trading_rule.trading_pair: trading_rule for trading_rule in trading_rules_list}

    async def _get_all_pairs_prices(self) -> Dict[str, Any]:
        # Polkadex is configured to not be a price provider (check is_price_provider)
        # This method should never be called
        raise NotImplementedError  # pragma: no cover

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        last_price = await self._data_source.last_price(market_symbol=symbol)
        return last_price

    def _configure_event_forwarders(self):
        event_forwarder = EventForwarder(to_function=self._process_user_trade_update)
        self._forwarders.append(event_forwarder)
        self._data_source.add_listener(event_tag=MarketEvent.TradeUpdate, listener=event_forwarder)

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

    def _process_user_trade_update(self, trade_update: TradeUpdate):
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(trade_update.exchange_order_id)

        if tracked_order is not None:
            self.logger().debug(f"Processing trade update {trade_update}\nFillable order {tracked_order.to_json()}")
            flat_fees = [
                TokenAmount(amount=flat_fee.amount, token=tracked_order.quote_asset)
                for flat_fee in trade_update.fee.flat_fees
            ]
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                trade_type=tracked_order.trade_type,
                percent_token=tracked_order.quote_asset,
                flat_fees=flat_fees,
            )
            fill_amount = trade_update.fill_base_amount - tracked_order.executed_amount_base
            trade_update: TradeUpdate = TradeUpdate(
                trade_id=trade_update.trade_id,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=trade_update.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                fill_timestamp=trade_update.fill_timestamp,
                fill_price=trade_update.fill_price,
                fill_base_amount=fill_amount,
                fill_quote_amount=fill_amount * trade_update.fill_price,
                fee=fee,
            )
            self._order_tracker.process_trade_update(trade_update)
