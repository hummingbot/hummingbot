import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple


from bidict import bidict

from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor import RPCQueryExecutor
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.pubsub import Enum, PubSub
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange_py_base import ExchangePyBase



class ChainflipLPDataSource:
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
        chain_config:Dict = CONSTANTS.DEFAULT_CHAIN_CONFIG
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
            chain_config = self._chain_config
        )
    async def start(self):
        await self.assets_list()
    def configure_throttler(self, throttler: AsyncThrottlerBase):
        self._throttler = throttler
    async def assets_list(self) -> Dict[str, str]:
        all_assets = await self._rpc_executor.all_assets()
        self._assets_list = all_assets
        return self._assets_list

    async def order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        all_assets = await self.assets_list()
        symbol_dict = DataFormatter.format_trading_pair(trading_pair, all_assets)
        orderbook_items = await self._rpc_executor.get_orderbook(
            symbol_dict["base_asset"],
            symbol_dict["quote_asset"]
        )
        timestamp = self._time()
        bids = []
        asks = []
        for orderbook_item in orderbook_items:
            for bid in orderbook_item["bids"]:
                price = Decimal(bid["sqrt_price"])
                amount = Decimal(bid["amount"])
                bids.append((price, amount))
            for ask in orderbook_item["asks"]:
                price = Decimal(ask["sqrt_price"])
                amount = Decimal(ask["amount"])
                asks.append((price, amount))

        order_book_message_content = {
            "trading_pair": trading_pair,
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
        balances = await self._rpc_executor.get_all_balances()
        return balances
    async def place_order(
            self,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            trade_type: TradeType,
            order_type: OrderType,
            price: Decimal,
            *kwargs
        ) -> Tuple[str, float]:
        asset_list = await self.assets_list()
        asset = DataFormatter.format_trading_pair(trading_pair,asset_list)
        place_order_response = await self._rpc_executor.place_limit_order(
            base_asset=asset["base_asset"],
            quote_asset=asset["quote_asset"],
            order_id=order_id,
            order_price=price,
            side=CONSTANTS.SIDE_BUY if trade_type == TradeType.BUY else CONSTANTS.SIDE_SELL,
            sell_amount=amount
        )
        timestamp = self._time()
        return order_id, timestamp
    async def place_cancel(self,order_id:str, trading_pair:str,tracked_order:InFlightOrder):
        asset_list = await self.assets_list()
        asset = DataFormatter.format_trading_pair(trading_pair,asset_list)
        status = self._rpc_executor.cancel_order(
            base_asset=asset["base_asset"],
            quote_asset=asset["quote_asset"],
            order_id=order_id,
            side = CONSTANTS.SIDE_BUY if tracked_order.trade_type == TradeType.BUY else CONSTANTS.SIDE_SELL
        )
        return status
    async def get_last_traded_price(self, trading_pair):
        asset = DataFormatter.format_trading_pair(trading_pair,self._assets_list)
        price = await self._rpc_executor.get_market_price(
            base_asset=asset["base_asset"],
            quote_asset= asset["quote_asset"]
        )["price"]
        return {trading_pair: price}
    def add_listener(self, event_tag: Enum, listener: EventListener):
        self._publisher.add_listener(event_tag=event_tag, listener=listener)
    def _time(self):
        return time.time()
    