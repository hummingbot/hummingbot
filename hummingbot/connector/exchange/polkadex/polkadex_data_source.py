import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

import gql
from bidict import bidict
from scalecodec.base import RuntimeConfiguration
from scalecodec.type_registry import load_type_registry_preset
from substrateinterface import Keypair, KeypairType

from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS, polkadex_utils
from hummingbot.connector.exchange.polkadex.polkadex_query_executor import GrapQLQueryExecutor
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent, OrderBookEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.pubsub import Enum, PubSub
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange_py_base import ExchangePyBase


class PolkadexDataSource:
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    def __init__(
        self,
        connector: "ExchangePyBase",
        seed_phrase: str,
        domain: Optional[str] = CONSTANTS.DEFAULT_DOMAIN,
        trading_required: bool = True,
        trading_pairs: list = [],
    ):
        self._connector = connector
        self._domain = domain
        self._trading_required = trading_required
        graphql_host = CONSTANTS.GRAPHQL_ENDPOINTS[self._domain]
        self.netloc_host = urlparse(graphql_host).netloc
        self._keypair = None
        self._user_main_address = None
        self._seed_phrase = seed_phrase
        self._trading_pairs = trading_pairs
        if seed_phrase is not None and len(seed_phrase) > 0:
            self._keypair = Keypair.create_from_mnemonic(
                seed_phrase, CONSTANTS.POLKADEX_SS58_PREFIX, KeypairType.SR25519
            )
            self._user_proxy_address = self._keypair.ss58_address
            self._auth = gql.transport.appsync_auth.AppSyncJWTAuthentication(self.netloc_host, self._user_proxy_address)
        else:
            self._user_proxy_address = "READ_ONLY"
            self._auth = gql.transport.appsync_auth.AppSyncJWTAuthentication(self.netloc_host, "READ_ONLY")

        # Load Polkadex Runtime Config
        self._runtime_config = RuntimeConfiguration()
        # Register core types
        self._runtime_config.update_type_registry(load_type_registry_preset("core"))
        # Register Orderbook specific types
        self._runtime_config.update_type_registry(CONSTANTS.CUSTOM_TYPES)

        self._publisher = PubSub()
        self._last_received_message_time = 0
        # We create a throttler instance here just to have a fully valid instance from the first moment.
        # The connector using this data source should replace the throttler with the one used by the connector.
        self._throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self._events_listening_tasks = []
        self._assets_map: Dict[str, str] = {}

        self._query_executor = GrapQLQueryExecutor(
            auth=self._auth,
            domain=self._domain,
            throttler=self._throttler
        )

        self._polkadex_order_type = {
            OrderType.MARKET: "MARKET",
            OrderType.LIMIT: "LIMIT",
            OrderType.LIMIT_MAKER: "LIMIT",
        }
        self._hummingbot_order_type = {
            "LIMIT": OrderType.LIMIT,
            "MARKET": OrderType.MARKET,
        }
        self._polkadex_trade_type = {
            TradeType.BUY: "Bid",
            TradeType.SELL: "Ask",
        }
        self._hummingbot_trade_type = {
            "Bid": TradeType.BUY,
            "Ask": TradeType.SELL,
        }

    def is_started(self) -> bool:
        # adds another status check
        return len(self._events_listening_tasks) > 0

    async def start(self, market_symbols: List[str]):
        if len(self._events_listening_tasks) > 0:
            raise AssertionError("Polkadex datasource is already listening to events and can't be started again")

        for market_symbol in market_symbols:
            self._events_listening_tasks.append(
                asyncio.create_task(
                    self._query_executor.listen_to_orderbook_updates(
                        events_handler=self._process_order_book_event, market_symbol=market_symbol
                    )
                )
            )
            self._events_listening_tasks.append(
                asyncio.create_task(
                    self._query_executor.listen_to_public_trades(
                        events_handler=self._process_recent_trades_event, market_symbol=market_symbol
                    )
                )
            )

        if self._trading_required:
            self._events_listening_tasks.append(
                asyncio.create_task(
                    self._query_executor.listen_to_private_events(
                        events_handler=self._process_private_event, address=self._user_proxy_address
                    )
                )
            )
            main_address = await self.user_main_address()
            self._events_listening_tasks.append(
                asyncio.create_task(
                    self._query_executor.listen_to_private_events(
                        events_handler=self._process_private_event, address=main_address
                    )
                )
            )
            self.logger().info("Started Polkadex_data_source")

    async def check_status(self):
        self.logger().info(f"Polkadex status is checked. self._query_executor._restart_initialization: {self._query_executor._restart_initialization}, self.trading_pairs {self._trading_pairs}")
        if self._query_executor._restart_initialization:
            self.logger().info("Polkadex status check - Need to reinitiate the query_executor")
            await self.stop()
            self.logger().info("Polkadex status check - Stopped the stackers")
            await self.reinitiaite_query_executor()
            self.logger().info("Polkadex status check - Reinitiated the trackers")
            await self.start(self._trading_pairs)
            self.logger().info("Polkadex status check - Started Again")

    async def reinitiaite_query_executor(self):
        self._query_executor = None
        self.logger().info("Polkadex status check - Reinitiating the query executor")
        if self._seed_phrase is not None and len(self._seed_phrase) > 0:
            self._keypair = Keypair.create_from_mnemonic(
                self._seed_phrase, CONSTANTS.POLKADEX_SS58_PREFIX, KeypairType.SR25519
            )
            self._user_proxy_address = self._keypair.ss58_address
            self._auth = gql.transport.appsync_auth.AppSyncJWTAuthentication(self.netloc_host, self._user_proxy_address)
        else:
            self._user_proxy_address = "READ_ONLY"
            self._auth = gql.transport.appsync_auth.AppSyncJWTAuthentication(self.netloc_host, "READ_ONLY")

        self._query_executor = GrapQLQueryExecutor(auth=self._auth, domain=self._domain, throttler=self._throttler)
        self.logger().info("Polkadex - Finished reinitiation")

    async def stop(self):
        for task in self._events_listening_tasks:
            task.cancel()
        self._events_listening_tasks = []
        self.logger().info("Stopped Polkadex_data_source")

    def configure_throttler(self, throttler: AsyncThrottlerBase):
        self._throttler = throttler

    def last_received_message_time(self) -> float:
        return self._last_received_message_time

    def add_listener(self, event_tag: Enum, listener: EventListener):
        self._publisher.add_listener(event_tag=event_tag, listener=listener)

    def remove_listener(self, event_tag: Enum, listener: EventListener):
        self._publisher.remove_listener(event_tag=event_tag, listener=listener)

    async def exchange_status(self):
        await self.check_status()
        all_assets = await self.assets_map()

        if len(all_assets) > 0:
            result = NetworkStatus.CONNECTED
        else:
            result = NetworkStatus.NOT_CONNECTED

        return result

    async def get_all_open_orders(self) -> List[Dict[str, Any]]:
        await self.check_status()
        return await self._query_executor.list_open_orders_by_main_account(main_account=await self.user_main_address())

    async def assets_map(self) -> Dict[str, str]:
        all_assets = await self._query_executor.all_assets()

        self._assets_map = {
            asset["asset_id"]: polkadex_utils.normalized_asset_name(
                asset_id=asset["asset_id"], asset_name=asset["name"]
            )
            for asset in all_assets
        }

        if len(self._assets_map) > 0:
            self._assets_map["polkadex"] = "PDEX"  # required due to inconsistent token name in private balance event

        return self._assets_map

    async def symbols_map(self) -> Mapping[str, str]:
        symbols_map = bidict()
        assets_map = await self.assets_map()

        all_markets = await self._query_executor.all_markets()

        for market_info in all_markets:
            try:
                base_asset, quote_asset = market_info["market"].split("-")
                base = assets_map[base_asset]
                quote = assets_map[quote_asset]
                symbols_map[market_info["market"]] = combine_to_hb_trading_pair(base=base, quote=quote)
            except KeyError:
                continue
        return symbols_map

    async def all_trading_rules(self) -> List[TradingRule]:
        all_markets = await self._query_executor.all_markets()

        trading_rules = []
        for market_info in all_markets:
            try:
                exchange_trading_pair = market_info["market"]
                trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                    symbol=exchange_trading_pair
                )
                amount_increment = Decimal(market_info["qty_step_size"])
                price_increment = Decimal(market_info["price_tick_size"])
                min_order_value = Decimal(market_info["min_volume"])
                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        # New API doesn't return min/max order size
                        # so we're trying to put some reasonable numbers here
                        min_order_size=0,
                        max_order_size=10**6,
                        min_price_increment=price_increment,
                        min_base_amount_increment=amount_increment,
                        min_quote_amount_increment=price_increment,
                        min_notional_size=min_order_value,
                        min_order_value=min_order_value,
                    )
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule: {market_info}. Skipping...")
                # QUICKFIX (dmitry): previously we were following "all or nothing" strategy here, but it was
                # blocking the startup of the bot

        return trading_rules

    async def order_book_snapshot(self, market_symbol: str, trading_pair: str) -> OrderBookMessage:
        orderbook_items = await self._query_executor.get_orderbook(market_symbol)

        timestamp = self._time()
        update_id = -1
        bids = []
        asks = []

        for orderbook_item in orderbook_items:
            price = Decimal(str(orderbook_item["p"]))
            amount = Decimal(str(orderbook_item["q"]))

            if orderbook_item["s"] == "Bid":
                bids.append((price, amount))
            else:
                asks.append((price, amount))

            update_id = max(update_id, int(orderbook_item["stid"]))

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

    async def user_main_address(self):
        if self._user_main_address is None:
            self._user_main_address = await self._query_executor.main_account_from_proxy(
                proxy_account=self._user_proxy_address)
        return self._user_main_address

    async def last_price(self, market_symbol: str) -> float:
        recent_trade = await self._query_executor.recent_trade(market_symbol=market_symbol)
        return float(recent_trade["p"])

    async def all_balances(self) -> List[Dict[str, Any]]:
        result = []
        assets_map = await self.assets_map()
        main_account = await self.user_main_address()
        balances = await self._query_executor.get_all_balances_by_main_account(main_account=main_account)

        for token_balance in balances:
            try:
                balance_info = {}
                available_balance = Decimal(token_balance["f"])
                locked_balance = Decimal(token_balance["r"])
                balance_info["token_name"] = assets_map[token_balance["a"]]
                balance_info["total_balance"] = available_balance + locked_balance
                balance_info["available_balance"] = available_balance
                result.append(balance_info)
            except KeyError:
                continue

        return result

    async def place_order(
        self,
        market_symbol: str,
        client_order_id: str,
        price: Decimal,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
    ) -> Tuple[str, float]:
        main_account = await self.user_main_address()
        price = self.normalize_fraction(price)
        amount = self.normalize_fraction(amount)
        timestamp = self._time()
        order_parameters = {
            "user": self._user_proxy_address,
            "main_account": main_account,
            "pair": market_symbol,
            "qty": f"{amount}",
            "price": f"{price}",
            "quote_order_quantity": "0",  # No need to be 8 decimal points
            "timestamp": int(timestamp * 1e3),
            "client_order_id": client_order_id,
            "order_type": self._polkadex_order_type[order_type],
            "side": self._polkadex_trade_type[trade_type],
        }

        place_order_request = self._runtime_config.create_scale_object("OrderPayload").encode(order_parameters)
        signature = self._keypair.sign(place_order_request)

        exchange_order_id = await self._query_executor.place_order(
            polkadex_order=order_parameters,
            signature={"Sr25519": signature.hex()}
        )

        if exchange_order_id is None:
            raise ValueError(f"Error in Polkadex creating order {client_order_id}")

        return exchange_order_id, timestamp

    async def cancel_order(self, order: InFlightOrder, market_symbol: str, timestamp: float) -> OrderState:
        # TODO (dmitry): analyze this logic and move to query executor
        try:
            cancel_result = await self._place_order_cancel(order=order, market_symbol=market_symbol)
        except Exception as e:
            if "Order is not active" in str(e):
                new_order_state = OrderState.CANCELED
            else:
                raise
        else:
            new_order_state = OrderState.PENDING_CANCEL if cancel_result else order.current_state

        return new_order_state

    async def order_update(self, order: InFlightOrder, market_symbol: str) -> OrderUpdate:
        # TODO (dmitry): remove `market_symbol` from function signature, it's not needed

        order_info = await self._query_executor.find_order_by_id(order_id=order.exchange_order_id)

        if order_info is None:
            raise IOError(f"Order not found {order.client_order_id} ({order.exchange_order_id})")

        new_state = CONSTANTS.ORDER_STATE[order_info["st"]]
        filled_amount = Decimal(order_info["fq"])
        if new_state == OrderState.OPEN and filled_amount > 0:
            new_state = OrderState.PARTIALLY_FILLED
        order_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order_info["id"],
            trading_pair=order.trading_pair,
            update_timestamp=self._time(),
            new_state=new_state,
        )
        return order_update

    async def get_all_fills(
        self, from_timestamp: float, to_timestamp: float, orders: List[InFlightOrder]
    ) -> List[TradeUpdate]:
        trade_updates = []

        fills = await self._query_executor.get_order_fills_by_main_account(
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            main_account=self._user_proxy_address
        )

        exchange_order_id_to_order = {order.exchange_order_id: order for order in orders}
        for fill in fills:
            exchange_trading_pair = fill["m"]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                symbol=exchange_trading_pair
            )

            price = Decimal(fill["p"])
            size = Decimal(fill["q"])
            order = exchange_order_id_to_order.get(fill["maker_id"], None)
            if order is None:
                order = exchange_order_id_to_order.get(fill["taker_id"], None)
            if order is not None:
                exchange_order_id = order.exchange_order_id
                client_order_id = order.client_order_id

                fee = await self._build_fee_for_event(event=fill, trade_type=order.trade_type)
                trade_updates.append(
                    TradeUpdate(
                        trade_id=fill["trade_id"],
                        client_order_id=client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=trading_pair,
                        fill_timestamp=int(fill["t"]) * 1e-3,
                        fill_price=price,
                        fill_base_amount=size,
                        fill_quote_amount=price * size,
                        fee=fee,
                    )
                )

        return trade_updates

    async def _place_order_cancel(self, order: InFlightOrder, market_symbol: str) -> Dict[str, Any]:
        cancel_request = self._runtime_config.create_scale_object("H256").encode(order.exchange_order_id)
        signature = self._keypair.sign(cancel_request)

        cancel_result = await self._query_executor.cancel_order(
            order_id=order.exchange_order_id,
            market_symbol=market_symbol,
            main_address=self._user_main_address,
            proxy_address=self._user_proxy_address,
            signature={"Sr25519": signature.hex()},
        )

        return cancel_result

    def _process_order_book_event(self, event: Dict[str, Any], market_symbol: str):
        safe_ensure_future(self._process_order_book_event_async(event=event, market_symbol=market_symbol))

    async def _process_order_book_event_async(self, event: Dict[str, Any], market_symbol: str):
        diff_data = json.loads(event["websocket_streams"]["data"])
        timestamp = self._time()
        update_id = diff_data["i"]
        asks = [(Decimal(price), Decimal(amount)) for price, amount in diff_data["a"].items()]
        bids = [(Decimal(price), Decimal(amount)) for price, amount in diff_data["b"].items()]

        order_book_message_content = {
            "trading_pair": await self._connector.trading_pair_associated_to_exchange_symbol(symbol=market_symbol),
            "update_id": update_id,
            "bids": bids,
            "asks": asks,
        }
        diff_message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=order_book_message_content,
            timestamp=timestamp,
        )
        self._publisher.trigger_event(event_tag=OrderBookEvent.OrderBookDataSourceUpdateEvent, message=diff_message)

    def _process_recent_trades_event(self, event: Dict[str, Any]):
        safe_ensure_future(self._process_recent_trades_event_async(event=event))

    async def _process_recent_trades_event_async(self, event: Dict[str, Any]):
        trade_data = json.loads(event["websocket_streams"]["data"])

        exchange_trading_pair = trade_data["m"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=exchange_trading_pair)
        timestamp = int(trade_data["t"]) * 1e-3
        trade_type = float(self._hummingbot_trade_type[trade_data["m_side"]].value)
        message_content = {
            "trade_id": trade_data["trade_id"],
            "trading_pair": trading_pair,
            "trade_type": trade_type,
            "amount": Decimal(str(trade_data["q"])),
            "price": Decimal(str(trade_data["p"])),
        }
        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=message_content,
            timestamp=timestamp,
        )
        self._publisher.trigger_event(event_tag=OrderBookEvent.TradeEvent, message=trade_message)

    def _process_private_event(self, event: Dict[str, Any]):
        event_data = json.loads(event["websocket_streams"]["data"])

        if event_data["type"] == "SetBalance":
            safe_ensure_future(self._process_balance_event(event=event_data))
        elif event_data["type"] == "Order":
            safe_ensure_future(self._process_private_order_update_event(event=event_data))
        elif event_data["type"] == "TradeFormat":
            safe_ensure_future(self._process_private_trade_event(event=event_data))

    async def _process_balance_event(self, event: Dict[str, Any]):
        self._last_received_message_time = self._time()

        assets_map = await self.assets_map()

        asset_name = assets_map[event["asset"]["asset"]]
        available_balance = Decimal(event["free"])
        reserved_balance = Decimal(event["reserved"])
        balance_msg = BalanceUpdateEvent(
            timestamp=self._time(),
            asset_name=asset_name,
            total_balance=available_balance + reserved_balance,
            available_balance=available_balance,
        )
        self._publisher.trigger_event(event_tag=AccountEvent.BalanceEvent, message=balance_msg)

    async def _process_private_order_update_event(self, event: Dict[str, Any]):
        self._last_received_message_time = self._time()

        exchange_order_id = event["id"]
        base = event["pair"]["base"]["asset"]
        quote = event["pair"]["quote"]["asset"]
        trading_pair = combine_to_hb_trading_pair(base=self._assets_map[base], quote=self._assets_map[quote])
        fill_amount = Decimal(event["filled_quantity"])
        order_state = CONSTANTS.ORDER_STATE[event["status"]]

        if order_state == OrderState.OPEN and fill_amount > 0:
            order_state = OrderState.PARTIALLY_FILLED
        order_update = OrderUpdate(
            trading_pair=trading_pair,
            update_timestamp=event["stid"],
            new_state=order_state,
            client_order_id=event["client_order_id"],
            exchange_order_id=exchange_order_id,
        )
        self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=order_update)

    async def _process_private_trade_event(self, event: Dict[str, Any]):
        exchange_trading_pair = event["m"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=exchange_trading_pair)
        price = Decimal(event["p"])
        size = Decimal(event["q"])
        trade_type = self._hummingbot_trade_type[event["s"]]
        fee = await self._build_fee_for_event(event=event, trade_type=trade_type)
        trade_update = TradeUpdate(
            trade_id=event["trade_id"],
            client_order_id=event["cid"],
            exchange_order_id=event["order_id"],
            trading_pair=trading_pair,
            fill_timestamp=self._time(),
            fill_price=price,
            fill_base_amount=size,
            fill_quote_amount=price * size,
            fee=fee,
        )

        self._publisher.trigger_event(event_tag=MarketEvent.TradeUpdate, message=trade_update)

    async def _build_fee_for_event(self, event: Dict[str, Any], trade_type: TradeType) -> TradeFeeBase:
        """Builds a TradeFee object from the given event data."""
        exchange_trading_pair = event["m"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=exchange_trading_pair)
        _, quote = split_hb_trading_pair(trading_pair=trading_pair)
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self._connector.trade_fee_schema(),
            trade_type=trade_type,
            percent_token=quote,
            flat_fees=[TokenAmount(token=quote, amount=Decimal("0"))],  # feels will be zero for the foreseeable future
        )
        return fee

    def _time(self):
        return time.time()

    @staticmethod
    def normalize_fraction(decimal_value: Decimal) -> Decimal:
        normalized = decimal_value.normalize()
        sign, digit, exponent = normalized.as_tuple()
        return normalized if exponent <= 0 else normalized.quantize(1)
