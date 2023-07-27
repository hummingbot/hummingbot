import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

from bidict import bidict
from gql.transport.appsync_auth import AppSyncJWTAuthentication
from substrateinterface import Keypair, KeypairType, SubstrateInterface

from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS, polkadex_utils
from hummingbot.connector.exchange.polkadex.polkadex_events import PolkadexOrderBookEvent
from hummingbot.connector.exchange.polkadex.polkadex_query_executor import GrapQLQueryExecutor
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.pubsub import Enum, PubSub
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class PolkadexDataSource:
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    def __init__(self, seed_phrase: str, domain: Optional[str] = CONSTANTS.DEFAULT_DOMAIN):
        self._domain = domain
        graphql_host = CONSTANTS.GRAPHQL_ENDPOINTS[self._domain]
        netloc_host = urlparse(graphql_host).netloc
        self._keypair = None
        self._user_main_address = None
        if seed_phrase is not None and len(seed_phrase) > 0:
            self._keypair = Keypair.create_from_mnemonic(
                seed_phrase, CONSTANTS.POLKADEX_SS58_PREFIX, KeypairType.SR25519
            )
            self._user_proxy_address = self._keypair.ss58_address
            self._auth = AppSyncJWTAuthentication(netloc_host, self._user_proxy_address)
        else:
            self._user_proxy_address = "no_address"
            self._auth = AppSyncJWTAuthentication(netloc_host, "no_address")

        self._substrate_interface = SubstrateInterface(
            url=CONSTANTS.BLOCKCHAIN_URLS[self._domain],
            ss58_format=CONSTANTS.POLKADEX_SS58_PREFIX,
            type_registry=CONSTANTS.CUSTOM_TYPES,
            auto_discover=False,
        )
        self._query_executor = GrapQLQueryExecutor(auth=self._auth, domain=self._domain)

        self._publisher = PubSub()
        self._last_received_message_time = 0
        # We create a throttler instance here just to have a fully valid instance from the first moment.
        # The connector using this data source should replace the throttler with the one used by the connector.
        self._throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self._events_listening_tasks = []
        self._assets_map: Optional[Dict[str, str]] = None

        self._polkadex_order_type = {
            OrderType.MARKET: "MARKET",
            OrderType.LIMIT: "LIMIT",
            OrderType.LIMIT_MAKER: "LIMIT",
        }
        self._polkadex_trade_type = {
            TradeType.BUY: "Bid",
            TradeType.SELL: "Ask",
        }

    def is_started(self) -> bool:
        return len(self._events_listening_tasks) > 0

    async def start(self, market_symbols: List[str]):
        if len(self._events_listening_tasks) > 0:
            raise AssertionError("Polkadex datasource is already listening to events and can't be started again")

        main_address = await self.user_main_address()

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

        self._events_listening_tasks.append(
            asyncio.create_task(
                self._query_executor.listen_to_private_events(
                    events_handler=self._process_private_event, address=self._user_proxy_address
                )
            )
        )
        self._events_listening_tasks.append(
            asyncio.create_task(
                self._query_executor.listen_to_private_events(
                    events_handler=self._process_private_event, address=main_address
                )
            )
        )

    async def stop(self):
        for task in self._events_listening_tasks:
            task.cancel()
        self._events_listening_tasks = []

    def configure_throttler(self, throttler: AsyncThrottlerBase):
        self._throttler = throttler

    def last_received_message_time(self) -> float:
        return self._last_received_message_time

    def add_listener(self, event_tag: Enum, listener: EventListener):
        self._publisher.add_listener(event_tag=event_tag, listener=listener)

    def remove_listener(self, event_tag: Enum, listener: EventListener):
        self._publisher.remove_listener(event_tag=event_tag, listener=listener)

    async def exchange_status(self):
        all_assets = await self.assets_map()

        if len(all_assets) > 0:
            result = NetworkStatus.CONNECTED
        else:
            result = NetworkStatus.NOT_CONNECTED

        return result

    async def assets_map(self) -> Dict[str, str]:
        if self._assets_map is None:
            async with self._throttler.execute_task(limit_id=CONSTANTS.ALL_ASSETS_LIMIT_ID):
                all_assets = await self._query_executor.all_assets()
            self._assets_map = {
                asset["asset_id"]: polkadex_utils.normalized_asset_name(
                    asset_id=asset["asset_id"], asset_name=asset["name"]
                )
                for asset in all_assets["getAllAssets"]["items"]
            }

            if len(self._assets_map) > 0:
                self._assets_map[
                    "polkadex"
                ] = "PDEX"  # required due to inconsistent token name in private balance event

        return self._assets_map

    async def symbols_map(self) -> Mapping[str, str]:
        symbols_map = bidict()
        assets_map = await self.assets_map()

        async with self._throttler.execute_task(limit_id=CONSTANTS.ALL_MARKETS_LIMIT_ID):
            markets = await self._query_executor.all_markets()

        for market_info in markets["getAllMarkets"]["items"]:
            try:
                base_asset, quote_asset = market_info["market"].split("-")
                base = assets_map[base_asset]
                quote = assets_map[quote_asset]
                symbols_map[market_info["market"]] = combine_to_hb_trading_pair(base=base, quote=quote)
            except KeyError:
                continue
        return symbols_map

    async def all_trading_rules(self) -> List[TradingRule]:
        async with self._throttler.execute_task(limit_id=CONSTANTS.ALL_MARKETS_LIMIT_ID):
            markets = await self._query_executor.all_markets()

        trading_rules = []
        for market_info in markets["getAllMarkets"]["items"]:
            try:
                trading_pair = market_info["market"]
                min_order_size = Decimal(market_info["min_order_qty"])
                max_order_size = Decimal(market_info["max_order_qty"])
                min_order_price = Decimal(market_info["min_order_price"])
                amount_increment = Decimal(market_info["qty_step_size"])
                price_increment = Decimal(market_info["price_tick_size"])
                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_order_size,
                        max_order_size=max_order_size,
                        min_price_increment=price_increment,
                        min_base_amount_increment=amount_increment,
                        min_quote_amount_increment=price_increment,
                        min_notional_size=min_order_size * min_order_price,
                        min_order_value=min_order_size * min_order_price,
                    )
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule: {market_info}. Skipping...")

        return trading_rules

    async def order_book_snapshot(self, market_symbol: str, trading_pair: str) -> OrderBookMessage:
        async with self._throttler.execute_task(limit_id=CONSTANTS.ORDERBOOK_LIMIT_ID):
            snapshot_data = await self._query_executor.get_orderbook(market_symbol=market_symbol)

        orderbook_entries = snapshot_data["getOrderbook"]["items"]

        timestamp = self._time()
        update_id = -1
        bids = []
        asks = []

        for orderbook_entry in orderbook_entries:
            price = Decimal(str(orderbook_entry["p"]))
            amount = Decimal(str(orderbook_entry["q"]))

            if orderbook_entry["s"] == "Bid":
                bids.append((price, amount))
            else:
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

    async def user_main_address(self):
        if self._user_main_address is None:
            async with self._throttler.execute_task(limit_id=CONSTANTS.FIND_USER_LIMIT_ID):
                self._user_main_address = await self._query_executor.main_account_from_proxy(
                    proxy_account=self._user_proxy_address,
                )
        return self._user_main_address

    async def last_price(self, market_symbol: str) -> float:
        async with self._throttler.execute_task(limit_id=CONSTANTS.PUBLIC_TRADES_LIMIT_ID):
            response = await self._query_executor.recent_trades(market_symbol=market_symbol, limit=1)
        last_price = response["getRecentTrades"]["items"][0]["p"]

        return float(last_price)

    async def all_balances(self) -> List[Dict[str, Any]]:
        result = []
        assets_map = await self.assets_map()
        main_account = await self.user_main_address()
        async with self._throttler.execute_task(limit_id=CONSTANTS.ALL_BALANCES_LIMIT_ID):
            balances = await self._query_executor.get_all_balances_by_main_account(main_account=main_account)

        for token_balance in balances["getAllBalancesByMainAccount"]["items"]:
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
        translated_client_order_id = f"0x{client_order_id.encode('utf-8').hex()}"
        price = round(price, 4)
        amount = round(amount, 4)
        timestamp = self._time()
        order_parameters = {
            "user": self._user_proxy_address,
            "main_account": main_account,
            "pair": market_symbol,
            "qty": f"{amount:f}"[:12],
            "price": f"{price:f}"[:12],
            "quote_order_quantity": "0",
            "timestamp": int(timestamp),
            "client_order_id": translated_client_order_id,
            "order_type": self._polkadex_order_type[order_type],
            "side": self._polkadex_trade_type[trade_type],
        }

        place_order_request = self._substrate_interface.create_scale_object("OrderPayload").encode(order_parameters)
        signature = self._keypair.sign(place_order_request)

        async with self._throttler.execute_task(limit_id=CONSTANTS.PLACE_ORDER_LIMIT_ID):
            response = await self._query_executor.place_order(
                polkadex_order=order_parameters,
                signature={"Sr25519": signature.hex()},
            )

        exchange_order_id = response["place_order"]

        if exchange_order_id is None:
            raise ValueError(f"Error in Polkadex creating order {client_order_id}")

        return exchange_order_id, timestamp

    async def cancel_order(self, order: InFlightOrder, market_symbol: str, timestamp: float) -> bool:
        cancel_request = self._substrate_interface.create_scale_object("H256").encode(order.exchange_order_id)
        signature = self._keypair.sign(cancel_request)

        async with self._throttler.execute_task(limit_id=CONSTANTS.CANCEL_ORDER_LIMIT_ID):
            cancel_result = await self._query_executor.cancel_order(
                order_id=order.exchange_order_id,
                market_symbol=market_symbol,
                proxy_address=self._user_proxy_address,
                signature={"Sr25519": signature.hex()},
            )

        if cancel_result["cancel_order"]:
            success = True
        else:
            success = False

        return success

    async def order_updates_from_account(self, from_time: float) -> List[OrderUpdate]:
        order_updates = []
        async with self._throttler.execute_task(limit_id=CONSTANTS.BATCH_ORDER_UPDATES_LIMIT_ID):
            response = await self._query_executor.list_order_history_by_account(
                main_account=self._user_proxy_address,
                from_time=from_time,
                to_time=self._time(),
            )

            for order_info in response["listOrderHistorybyMainAccount"]["items"]:
                new_state = CONSTANTS.ORDER_STATE[order_info["st"]]
                filled_amount = Decimal(order_info["fq"])
                if new_state == OrderState.OPEN and filled_amount > 0:
                    new_state = OrderState.PARTIALLY_FILLED
                order_update = OrderUpdate(
                    client_order_id=order_info["cid"],
                    exchange_order_id=order_info["id"],
                    trading_pair=order_info["m"],
                    update_timestamp=self._time(),
                    new_state=new_state,
                )
                order_updates.append(order_update)

        return order_updates

    async def order_update(self, order: InFlightOrder, market_symbol: str) -> OrderUpdate:
        async with self._throttler.execute_task(limit_id=CONSTANTS.ORDER_UPDATE_LIMIT_ID):
            response = await self._query_executor.find_order_by_main_account(
                main_account=self._user_proxy_address,
                market_symbol=market_symbol,
                order_id=order.exchange_order_id,
            )

        order_info = response["findOrderByMainAccount"]

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

    def _process_order_book_event(self, event: Dict[str, Any], market_symbol: str):
        diff_data = json.loads(event["websocket_streams"]["data"])
        timestamp = self._time()
        update_id = -1
        bids = []
        asks = []

        for diff_update in diff_data["changes"]:
            update_id = max(update_id, diff_update[3])
            price_amount_pair = (diff_update[1], diff_update[2])
            if diff_update[0] == "Bid":
                bids.append(price_amount_pair)
            else:
                asks.append(price_amount_pair)

        order_book_message_content = {
            "trading_pair": market_symbol,
            "update_id": update_id,
            "bids": bids,
            "asks": asks,
        }
        diff_message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=order_book_message_content,
            timestamp=timestamp,
        )
        self._publisher.trigger_event(
            event_tag=PolkadexOrderBookEvent.OrderBookDataSourceUpdateEvent, message=diff_message
        )

    def _process_recent_trades_event(self, event: Dict[str, Any]):
        trade_data = json.loads(event["websocket_streams"]["data"])

        symbol = trade_data["m"]
        timestamp = int(trade_data["t"]) * 1e-3
        trade_type = float(TradeType.SELL.value)  # Unfortunately Polkadex does not indicate the trade side
        message_content = {
            "trade_id": trade_data["tid"],
            "trading_pair": symbol,
            "trade_type": trade_type,
            "amount": Decimal(str(trade_data["q"])),
            "price": Decimal(str(trade_data["p"])),
        }
        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=message_content,
            timestamp=timestamp,
        )
        self._publisher.trigger_event(
            event_tag=PolkadexOrderBookEvent.PublicTradeEvent, message=trade_message
        )

    def _process_private_event(self, event: Dict[str, Any]):
        event_data = json.loads(event["websocket_streams"]["data"])

        if event_data["type"] == "SetBalance":
            safe_ensure_future(self._process_balance_event(event=event_data))
        elif event_data["type"] == "Order":
            safe_ensure_future(self._process_private_order_update_event(event=event_data))

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

        client_order_id = event["client_order_id"]
        exchange_order_id = event["id"]
        trading_pair = event["pair"]
        fee_amount = Decimal(event["fee"])
        fill_price = Decimal(event["avg_filled_price"])
        fill_amount = Decimal(event["filled_quantity"])
        fill_quote_amount = Decimal(event["filled_quantity"])

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=TradeFeeSchema(),
            trade_type=TradeType.BUY if event["side"] == "Bid" else TradeType.SELL,
            flat_fees=[TokenAmount(amount=fee_amount, token=None)],
        )
        trade_update = TradeUpdate(
            trade_id=str(event["event_id"]),
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            fill_timestamp=self._time(),
            fill_price=fill_price,
            fill_base_amount=fill_amount,
            fill_quote_amount=fill_quote_amount,
            fee=fee,
        )

        self._publisher.trigger_event(event_tag=MarketEvent.TradeUpdate, message=trade_update)

        client_order_id = event["client_order_id"]
        order_state = CONSTANTS.ORDER_STATE[event["status"]]
        if order_state == OrderState.OPEN and fill_amount > 0:
            order_state = OrderState.PARTIALLY_FILLED
        order_update = OrderUpdate(
            trading_pair=trading_pair,
            update_timestamp=self._time(),
            new_state=order_state,
            client_order_id=client_order_id,
            exchange_order_id=event["id"],
        )
        self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=order_update)

    def _time(self):
        return time.time()
