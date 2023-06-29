import asyncio
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from bidict import bidict
from pyinjective.async_client import AsyncClient
from pyinjective.constant import Network
from pyinjective.wallet import Address, PrivateKey

from hummingbot.connector.exchange.injective import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective.injective_market import InjectiveSpotMarket, InjectiveToken
from hummingbot.connector.exchange.injective.injective_query_executor import PythonSDKInjectiveQueryExecutor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import OrderBookDataSourceEvent
from hummingbot.core.pubsub import PubSub
from hummingbot.logger import HummingbotLogger


class InjectiveDataSource(ABC):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    @classmethod
    def for_grantee(
            cls,
            private_key: str,
            subaccount_index: int,
            granter_address: str,
            granter_subaccount_index: int,
            domain: Optional[str] = CONSTANTS.DEFAULT_DOMAIN):
        return InjectiveGranteeDataSource(
            private_key=private_key,
            subaccount_index=subaccount_index,
            granter_address=granter_address,
            granter_subaccount_index=granter_subaccount_index,
            domain=domain,
        )

    @property
    @abstractmethod
    def publisher(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def query_executor(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def throttler(self):
        raise NotImplementedError

    @abstractmethod
    async def market_info_for_id(self, market_id: str):
        raise NotImplementedError

    @abstractmethod
    async def trading_pair_for_market(self, market_id: str):
        raise NotImplementedError

    @abstractmethod
    def events_listening_tasks(self) -> List[asyncio.Task]:
        raise NotImplementedError

    @abstractmethod
    def add_listening_task(self, task: asyncio.Task):
        raise NotImplementedError

    async def start(self, market_ids: List[str]):
        if len(self.events_listening_tasks()) == 0:

            self.add_listening_task(asyncio.create_task(self._listen_to_public_trades(market_ids=market_ids)))
            self.add_listening_task(asyncio.create_task(self._listen_to_order_book_updates(market_ids=market_ids)))

            # self._events_listening_tasks.append(
            #     asyncio.create_task(
            #         self._query_executor.listen_to_private_events(
            #             events_handler=self._process_private_event, address=self._user_proxy_address
            #         )
            #     )
            # )
            # self._events_listening_tasks.append(
            #     asyncio.create_task(
            #         self._query_executor.listen_to_private_events(
            #             events_handler=self._process_private_event, address=main_address
            #         )
            #     )
            # )

    async def stop(self):
        for task in self.events_listening_tasks():
            task.cancel()

    def add_listener(self, event_tag: Enum, listener: EventListener):
        self.publisher.add_listener(event_tag=event_tag, listener=listener)

    def remove_listener(self, event_tag: Enum, listener: EventListener):
        self.publisher.remove_listener(event_tag=event_tag, listener=listener)

    async def order_book_snapshot(self, market_id: str, trading_pair: str) -> OrderBookMessage:
        async with self.throttler.execute_task(limit_id=CONSTANTS.ORDERBOOK_LIMIT_ID):
            snapshot_data = await self.query_executor.get_spot_orderbook(market_id=market_id)

        market = await self.market_info_for_id(market_id=market_id)
        bids = [(market.price_from_chain_format(chain_price=Decimal(price)),
                 market.quantity_from_chain_format(chain_quantity=Decimal(quantity)))
                for price, quantity, _ in snapshot_data["buys"]]
        asks = [(market.price_from_chain_format(chain_price=Decimal(price)),
                 market.quantity_from_chain_format(chain_quantity=Decimal(quantity)))
                for price, quantity, _ in snapshot_data["sells"]]
        snapshot_msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": snapshot_data["sequence"],
                "bids": bids,
                "asks": asks,
            },
            timestamp=snapshot_data["timestamp"] * 1e-3,
        )
        return snapshot_msg

    @abstractmethod
    def _order_book_updates_stream(self, market_ids: List[str]):
        raise NotImplementedError

    @abstractmethod
    def _public_trades_stream(self, market_ids: List[str]):
        raise NotImplementedError

    async def _listen_to_order_book_updates(self, market_ids: List[str]):
        while True:
            try:
                updates_stream = self._order_book_updates_stream(market_ids=market_ids)
                async for update in updates_stream:
                    try:
                        await self._process_order_book_update(order_book_update=update)
                    except asyncio.CancelledError:
                        raise
                    except Exception as ex:
                        self.logger().warning(f"Invalid orderbook diff event format ({ex})\n{update}")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Error while listening to order book updates, reconnecting ... ({ex})")

    async def _listen_to_public_trades(self, market_ids: List[str]):
        while True:
            try:
                public_trades_stream = self._public_trades_stream(market_ids=market_ids)
                async for trade in public_trades_stream:
                    try:
                        await self._process_public_trade_update(trade_update=trade)
                    except asyncio.CancelledError:
                        raise
                    except Exception as ex:
                        self.logger().warning(f"Invalid public trade event format ({ex})\n{trade}")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Error while listening to public trades, reconnecting ... ({ex})")

    async def _process_order_book_update(self, order_book_update: Dict[str, Any]):
        market_id = order_book_update["marketId"]
        market_info = await self.market_info_for_id(market_id=market_id)

        trading_pair = await self.trading_pair_for_market(market_id=market_id)
        bids = [(market_info.price_from_chain_format(chain_price=Decimal(bid["price"])),
                 market_info.quantity_from_chain_format(chain_quantity=Decimal(bid["quantity"])))
                for bid in order_book_update["buys"]]
        asks = [(market_info.price_from_chain_format(chain_price=Decimal(ask["price"])),
                 market_info.quantity_from_chain_format(chain_quantity=Decimal(ask["quantity"])))
                for ask in order_book_update["sells"]]

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": int(order_book_update["sequence"]),
            "bids": bids,
            "asks": asks,
        }
        diff_message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=order_book_message_content,
            timestamp=int(order_book_update["updatedAt"]) * 1e-3,
        )
        self.publisher.trigger_event(
            event_tag=OrderBookDataSourceEvent.DIFF_EVENT, message=diff_message
        )

    async def _process_public_trade_update(self, trade_update: Dict[str, Any]):
        market_id = trade_update["marketId"]
        market_info = await self.market_info_for_id(market_id=market_id)

        trading_pair = await self.trading_pair_for_market(market_id=market_id)
        timestamp = int(trade_update["executedAt"]) * 1e-3
        trade_type = float(TradeType.BUY.value) if trade_update["tradeDirection"] == "buy" else float(TradeType.SELL.value)
        message_content = {
            "trade_id": trade_update["tradeId"],
            "trading_pair": trading_pair,
            "trade_type": trade_type,
            "amount": market_info.quantity_from_chain_format(chain_quantity=Decimal(str(trade_update["price"]["quantity"]))),
            "price": market_info.price_from_chain_format(chain_price=Decimal(str(trade_update["price"]["price"]))),
        }
        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=message_content,
            timestamp=timestamp,
        )
        self.publisher.trigger_event(
            event_tag=OrderBookDataSourceEvent.TRADE_EVENT, message=trade_message
        )


class InjectiveDirectTradingDataSource(InjectiveDataSource):
    _logger: Optional[HummingbotLogger] = None


class InjectiveGranteeDataSource(InjectiveDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            private_key: str,
            subaccount_index: int,
            granter_address: str,
            granter_subaccount_index: int,
            domain: Optional[str] = CONSTANTS.DEFAULT_DOMAIN):
        self._network = Network.testnet() if domain == CONSTANTS.TESTNET_DOMAIN else Network.mainnet()
        self._client = AsyncClient(network=self._network, insecure=False)
        self._query_executor = PythonSDKInjectiveQueryExecutor(sdk_client=self._client)

        self._private_key = PrivateKey.from_hex(private_key)
        self._public_key = self._private_key.to_public_key()
        self._grantee_address = self._public_key.to_address()
        self._grantee_subaccount_id = self._grantee_address.get_subaccount_id(index=subaccount_index)
        granter_address = Address.from_acc_bech32(granter_address)
        self._granter_subaccount_id = granter_address.get_subaccount_id(index=granter_subaccount_index)

        self._publisher = PubSub()
        self._last_received_message_time = 0
        # We create a throttler instance here just to have a fully valid instance from the first moment.
        # The connector using this data source should replace the throttler with the one used by the connector.
        self._throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)

        self._market_info_map: Optional[Dict[str, InjectiveSpotMarket]] = None
        self._market_and_trading_pair_map: Optional[Mapping[str, str]] = None
        self._tokens_map: Optional[Dict[str, InjectiveToken]] = None
        self._token_symbol_symbol_and_denom_map: Optional[Mapping[str, str]] = None

        self._events_listening_tasks: List[asyncio.Task] = []

    @property
    def publisher(self):
        return self._publisher

    @property
    def query_executor(self):
        return self._query_executor

    @property
    def throttler(self):
        return self._throttler

    def events_listening_tasks(self) -> List[asyncio.Task]:
        return self._events_listening_tasks.copy()

    def add_listening_task(self, task: asyncio.Task):
        self._events_listening_tasks.append(task)

    async def market_info_for_id(self, market_id: str):
        if self._market_info_map is None:
            await self._update_markets()

        return self._market_info_map[market_id]

    async def trading_pair_for_market(self, market_id: str):
        if self._market_and_trading_pair_map is None:
            await self._update_markets()

        return self._market_and_trading_pair_map[market_id]

    async def stop(self):
        await super().stop()
        self._events_listening_tasks = []

    def _token_from_market_info(self, denom: str, token_meta: Dict[str, Any], candidate_symbol: str) -> InjectiveToken:
        token = self._tokens_map.get(denom)
        if token is None:
            unique_symbol = token_meta["symbol"]
            if unique_symbol in self._token_symbol_symbol_and_denom_map:
                if candidate_symbol not in self._token_symbol_symbol_and_denom_map:
                    unique_symbol = candidate_symbol
                else:
                    unique_symbol = token_meta["name"]
            token = InjectiveToken(
                denom=denom,
                symbol=token_meta["symbol"],
                unique_symbol=unique_symbol,
                name=token_meta["name"],
                decimals=token_meta["decimals"]
            )
            self._tokens_map[denom] = token
            self._token_symbol_symbol_and_denom_map[unique_symbol] = denom

        return token

    async def _update_markets(self):
        self._tokens_map = {}
        self._token_symbol_symbol_and_denom_map = bidict()
        markets = await self._query_executor.spot_markets(status="active")
        markets_map = {}
        market_id_to_trading_pair = bidict()

        for market_info in markets:
            try:
                ticker_base, ticker_quote = market_info["ticker"].split("/")
                base_token = self._token_from_market_info(
                    denom=market_info["baseDenom"],
                    token_meta=market_info["baseTokenMeta"],
                    candidate_symbol=ticker_base,
                )
                quote_token = self._token_from_market_info(
                    denom=market_info["quoteDenom"],
                    token_meta=market_info["quoteTokenMeta"],
                    candidate_symbol=ticker_quote,
                )
                market = InjectiveSpotMarket(
                    market_id=market_info["marketId"],
                    base_token=base_token,
                    quote_token=quote_token,
                    market_info=market_info
                )
                market_id_to_trading_pair[market.market_id] = market.trading_pair()
                markets_map[market.market_id] = market
            except KeyError:
                self.logger().warning(f"The market {market_info['marketId']} will be excluded because it could not be "
                                      f"parsed ({market_info})")
                continue

        self._market_info_map = markets_map
        self._market_and_trading_pair_map = market_id_to_trading_pair

    def _order_book_updates_stream(self, market_ids: List[str]):
        stream = self._query_executor.spot_order_book_updates_stream(market_ids=market_ids)
        return stream

    def _public_trades_stream(self, market_ids: List[str]):
        stream = self._query_executor.public_spot_trades_stream(market_ids=market_ids)
        return stream
