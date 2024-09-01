import asyncio
import logging
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple

from bidict import bidict

from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor import RPCQueryExecutor
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_utils import DEFAULT_FEES
from hummingbot.connector.trading_rule import TradingRule
<<<<<<< HEAD
=======
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_utils import DEFAULT_FEES
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
=======
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.data_type.common import OrderType, TradeType
<<<<<<< HEAD
<<<<<<< HEAD
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
=======
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate
>>>>>>> 63271bb03 ((refactor) update and cleanup chainflip connector codes)
=======
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import MarketEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.pubsub import Enum, PubSub
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange_py_base import ExchangePyBase


<<<<<<< HEAD
<<<<<<< HEAD
class ChainflipLpDataSource:
=======
class ChainflipLPDataSource:
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
class ChainflipLpDataSource:
>>>>>>> cb0a3d276 ((refactor) implement review changes)
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    def __init__(
        self,
        connector: "ExchangePyBase",
        address: str,
        rpc_api_url: str,
        domain: Optional[str] = CONSTANTS.DEFAULT_DOMAIN,
        trading_required: bool = True,
        trading_pairs: list = [],
        chain_config: Dict = CONSTANTS.DEFAULT_CHAIN_CONFIG,
    ):
        self._connector = connector
        self._domain = domain
        self._trading_required = trading_required
        self._address = address
        self._trading_pairs = trading_pairs
        self._lp_api_url = rpc_api_url
        self._publisher = PubSub()
        self._last_received_message_time = 0
        # We create a throttler instance here just to have a fully valid instance from the first moment.
        # The connector using this data source should replace the throttler with the one used by the connector.
        self._throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self._events_listening_tasks = []
        self._assets_list: List[Dict[str, str]] = []
        self._chain_config = chain_config

        self._rpc_executor = RPCQueryExecutor(
            throttler=self._throttler,
            chainflip_lp_api_url=self._lp_api_url,
            lp_account_address=address,
            domain=self._domain,
            chain_config=self._chain_config,
        )
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)

    async def start(self):
        await self._rpc_executor.start()
        await self.assets_list()
        self._events_listening_tasks.append(
            asyncio.create_task(self._rpc_executor.listen_to_order_fills(self._process_recent_order_fills_event))
<<<<<<< HEAD
        )

=======
    async def start(self, market_symbols):
=======
    async def start(self):
        await self._rpc_executor.start()
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
        await self.assets_list()
        self._events_listening_tasks.append(
            asyncio.create_task(
                self._rpc_executor.listen_to_order_fills(
                    self._process_recent_order_fills_event
                )
            )
        )
>>>>>>> 63271bb03 ((refactor) update and cleanup chainflip connector codes)
=======
        )

>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
    async def stop(self):
        for task in self._events_listening_tasks:
            task.cancel()
        self._events_listening_tasks = []

<<<<<<< HEAD
<<<<<<< HEAD
    def is_started(self):
        return len(self._assets_list) > 0

=======
>>>>>>> 63271bb03 ((refactor) update and cleanup chainflip connector codes)
=======
    def is_started(self):
        return len(self._assets_list) > 0

>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
    def configure_throttler(self, throttler: AsyncThrottlerBase):
        self._throttler = throttler

    async def assets_list(self) -> Dict[str, str]:

        all_assets = await self._rpc_executor.all_assets()
        self._assets_list = all_assets
        return self._assets_list

    async def order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        all_assets = await self.assets_list()
        symbol_dict = DataFormatter.format_trading_pair(trading_pair, all_assets)
        orderbook_items = await self._rpc_executor.get_orderbook(symbol_dict["base_asset"], symbol_dict["quote_asset"])
<<<<<<< HEAD
        if orderbook_items is None:
            raise ValueError("Error getting orderbook from Chainflip Lp")
=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
        timestamp = self._time()
        bids = []
        asks = []
        update_id = orderbook_items["id"]

        for bid in orderbook_items["bids"]:
            price = Decimal(bid["price"])
            amount = Decimal(bid["amount"])
            bids.append((price, amount))
        for ask in orderbook_items["asks"]:
            price = Decimal(ask["price"])
            amount = Decimal(ask["amount"])
            asks.append((price, amount))

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks,
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=order_book_message_content,
            timestamp=timestamp,
        )
        return snapshot_msg

    async def exchange_status(self):
        status = await self._rpc_executor.check_connection_status()

        if status:
            result = NetworkStatus.CONNECTED
        else:
            result = NetworkStatus.NOT_CONNECTED
        return result

    async def symbols_map(self) -> Mapping[str, str]:
        symbols_map = bidict()
        all_markets = await self._rpc_executor.all_markets()
        for market_info in all_markets:
            try:
                base, quote = market_info["symbol"].split("-")
                symbols_map[market_info["symbol"]] = combine_to_hb_trading_pair(base=base, quote=quote)
            except KeyError:
                continue
        return symbols_map

    async def all_balances(self) -> List[Dict[str, Any]]:
<<<<<<< HEAD
<<<<<<< HEAD
        return await self._rpc_executor.get_all_balances()
=======
        balances = await self._rpc_executor.get_all_balances()
        return balances
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
        return await self._rpc_executor.get_all_balances()
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)

    async def place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
<<<<<<< HEAD
<<<<<<< HEAD
        *kwargs,
=======
        *kwargs
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
        *kwargs,
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
    ) -> Tuple[str, float]:
        asset_list = await self.assets_list()
        self.logger().info(f"Placing Order on Chainflip LP with order id {order_id}")
        asset = DataFormatter.format_trading_pair(trading_pair, asset_list)
        place_order_response = await self._rpc_executor.place_limit_order(
            base_asset=asset["base_asset"],
            quote_asset=asset["quote_asset"],
            order_id=order_id,
            order_price=price,
            side=CONSTANTS.SIDE_BUY if trade_type == TradeType.BUY else CONSTANTS.SIDE_SELL,
            sell_amount=amount,
        )
        timestamp = self._time()
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
        if not place_order_response:
            raise ValueError(f"Error placing order {order_id} in Chainflip LP")
        return place_order_response["order_id"], timestamp

    async def place_cancel(self, order_id: str, trading_pair: str, tracked_order: InFlightOrder):
=======
        return place_order_response["order_id"], timestamp
<<<<<<< HEAD
    async def place_cancel(self,order_id:str, trading_pair:str,tracked_order:InFlightOrder):
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
        asset_list = await self.assets_list()
        asset = DataFormatter.format_trading_pair(trading_pair, asset_list)
        self.logger().info(f"Canceling Order with id {order_id}")
        status = await self._rpc_executor.cancel_order(
=======

    async def place_cancel(self, order_id: str, trading_pair: str, tracked_order: InFlightOrder):
        asset_list = await self.assets_list()
        asset = DataFormatter.format_trading_pair(trading_pair, asset_list)
<<<<<<< HEAD
        status = self._rpc_executor.cancel_order(
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
        self.logger().info("Canceling Order in Chainflip LP")
        self.logger().info(f"Canceling Order with id {order_id}")
        status = await self._rpc_executor.cancel_order(
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
            base_asset=asset["base_asset"],
            quote_asset=asset["quote_asset"],
            order_id=order_id,
            side=CONSTANTS.SIDE_BUY if tracked_order.trade_type == TradeType.BUY else CONSTANTS.SIDE_SELL,
        )
<<<<<<< HEAD
<<<<<<< HEAD
        return status

=======
        state = OrderState.CANCELED if status else tracked_order.current_state
        return state
<<<<<<< HEAD
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
=======
        return status

>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
    async def get_last_traded_price(self, trading_pair):
<<<<<<< HEAD
        asset = DataFormatter.format_trading_pair(trading_pair, self._assets_list)
        price_response = await self._rpc_executor.get_market_price(
            base_asset=asset["base_asset"], quote_asset=asset["quote_asset"]
        )
        price = price_response["price"]
        return price

    async def get_order_fills(self, orders: List[InFlightOrder]):
        order_fills = await self._rpc_executor.get_account_order_fills()
        exchange_order_id_to_order = {order.exchange_order_id: order for order in orders}
        trade_updates = []
        for fill in order_fills:
            order = exchange_order_id_to_order.get(fill["id"], None)
            if order:
                update = TradeUpdate(
                    trade_id=fill["id"],
                    client_order_id=order.client_order_id,
                    exchange_order_id=fill["id"],
                    trading_pair=fill["trading_pair"],
                    fill_timestamp=self._time(),
                    fill_price=fill["price"],
                    fill_base_amount=fill["base_amount"],
                    fill_quote_amount=fill["quote_amount"],
                    fee=DEFAULT_FEES,
                )
                trade_updates.append(update)
        return trade_updates

    async def all_trading_rules(self):
        # chainflip lp does not have implementation for trading rules
        # so we are going to set some arbituary values
        markets = await self._rpc_executor.all_markets()
        trading_rules = []
        for market in markets:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=market["symbol"])
            trading_rules.append(TradingRule(
                trading_pair=trading_pair,
                min_order_size=0,
                max_order_size=10**6,
                min_price_increment=Decimal("0.00001"),
                min_base_amount_increment=Decimal("0.00001"),
                min_quote_amount_increment=Decimal("0.00001"),
            ))
        return trading_rules

<<<<<<< HEAD
<<<<<<< HEAD
=======
        asset = DataFormatter.format_trading_pair(trading_pair,self._assets_list)
=======

    async def get_last_traded_price(self, trading_pair):
        asset = DataFormatter.format_trading_pair(trading_pair, self._assets_list)
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
        price = await self._rpc_executor.get_market_price(
            base_asset=asset["base_asset"], quote_asset=asset["quote_asset"]
        )["price"]
        return {trading_pair: price}
<<<<<<< HEAD
<<<<<<< HEAD
>>>>>>> 63271bb03 ((refactor) update and cleanup chainflip connector codes)
=======
=======

>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
    async def get_order_fills(self, orders: List[InFlightOrder]):
        order_fills = await self._rpc_executor.get_account_order_fills()
        exchange_order_id_to_order = {order.exchange_order_id: order for order in orders}
        trade_updates = []
        for fill in order_fills:
            order = exchange_order_id_to_order.get(fill["id"], None)
            if order:
                update = TradeUpdate(
                    trade_id=fill["id"],
                    client_order_id=order.client_order_id,
                    exchange_order_id=fill["id"],
                    trading_pair=fill["trading_pair"],
                    fill_timestamp=self._time(),
                    fill_price=fill["price"],
                    fill_base_amount=fill["base_amount"],
                    fill_quote_amount=fill["quote_amount"],
                    fee=DEFAULT_FEES,
                )
                trade_updates.append(update)
        return trade_updates

>>>>>>> 9979ea9b9 ((refactor) update code and tests)
=======
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
=======
    async def order_update(self, order: InFlightOrder):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(order.trading_pair)
        pair = DataFormatter.format_trading_pair(trading_pair, self._assets_list)
        trade_type = CONSTANTS.SIDE_BUY if order.trade_type == TradeType.BUY else CONSTANTS.SIDE_SELL
        order_info = await self._rpc_executor.get_order_status(
            order.exchange_order_id,
            trade_type,
            pair["base_asset"],
            pair["quote_asset"]
        )
        if order_info is None:
            order_update = OrderUpdate(
                trading_pair=order.trading_pair,
                update_timestamp=self._time(),
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                new_state=OrderState.COMPLETED
            )
        else:
            order_update = OrderUpdate(
                trading_pair=order.trading_pair,
                update_timestamp=self._time(),
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                new_state=OrderState.OPEN
            )
        return order_update

>>>>>>> 2df344816 ((refactor) add order update and fix balance mapping)
    async def _process_recent_order_fills_async(self, events: Dict[str, Any]):
        if not events:
            return
        for event in events:
            order_state = OrderState.PARTIALLY_FILLED
            update = OrderUpdate(
                trading_pair=event["trading_pair"],
                update_timestamp=self._time(),
                new_state=order_state,
                client_order_id=event["id"],
                exchange_order_id=event["id"],
            )
            self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=update)
<<<<<<< HEAD
<<<<<<< HEAD
=======
        
>>>>>>> 63271bb03 ((refactor) update and cleanup chainflip connector codes)
=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)

    def _process_recent_order_fills_event(self, event: Dict[str, Any]):
        safe_ensure_future(self._process_recent_order_fills_async(event=event))

    def add_listener(self, event_tag: Enum, listener: EventListener):
        self._publisher.add_listener(event_tag=event_tag, listener=listener)

    def _time(self):
        return time.time()
