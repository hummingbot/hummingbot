import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, AsyncIterable, Callable, Dict, Optional

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.appsync_auth import AppSyncAuthentication
from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
from graphql import DocumentNode

from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class BaseQueryExecutor(ABC):
    @abstractmethod
    async def all_assets(self):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def all_markets(self):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def get_orderbook(self, market_symbol: str) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def main_account_from_proxy(self, proxy_account=str) -> str:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def recent_trades(self, market_symbol: str, limit: int) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def get_all_balances_by_main_account(self, main_account: str) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def get_order_fills_by_main_account(
        self, from_timestamp: float, to_timestamp: float, main_account: str
    ) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def place_order(self, polkadex_order: Dict[str, Any], signature: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def cancel_order(
        self,
        order_id: str,
        market_symbol: str,
        proxy_address: str,
        main_address: str,
        signature: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def list_order_history_by_account(
        self, main_account: str, from_time: float, to_time: float
    ) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def find_order_by_main_account(self, main_account: str, market_symbol: str, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def list_open_orders_by_main_account(self, main_account: str) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def listen_to_orderbook_updates(self, events_handler: Callable, market_symbol: str):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def listen_to_public_trades(self, events_handler: Callable, market_symbol: str):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def listen_to_private_events(self, events_handler: Callable, address: str):
        raise NotImplementedError  # pragma: no cover


class GrapQLQueryExecutor(BaseQueryExecutor):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    def __init__(self, auth: AppSyncAuthentication, domain: Optional[str] = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth = auth
        self._domain = domain
        self._client = None
        self._ws_session = None

    async def create_ws_session(self):
        url = CONSTANTS.GRAPHQL_ENDPOINTS[self._domain]
        transport = AppSyncWebsocketsTransport(url=url, auth=self._auth)
        self._client = Client(transport=transport, fetch_schema_from_transport=False)
        self._ws_session = await self._client.connect_async(reconnecting=True)

    async def all_assets(self):
        query = gql(
            """
            query GetAllAssets {
                getAllAssets {
                    items {
                        asset_id
                        name
                    }
                }
            }
            """
        )

        parameters = {}
        result = await self._execute_query(query=query, parameters=parameters)
        return result

    async def all_markets(self):
        query = gql(
            """
            query MyQuery {
                getAllMarkets {
                    items {
                        market
                        max_order_price
                        min_order_price
                        min_order_qty
                        max_order_qty
                        price_tick_size
                        qty_step_size
                        base_asset_precision
                        quote_asset_precision
                    }
                }
            }
            """
        )

        parameters = {}
        result = await self._execute_query(query=query, parameters=parameters)
        return result

    async def get_orderbook(self, market_symbol: str) -> Dict[str, Any]:
        query = gql(
            """
            query getOrderbook($market: String!, $limit: Int, $nextToken: String) {
              getOrderbook(market: $market, limit: $limit, nextToken: $nextToken) {
                nextToken
                items {
                  p
                  q
                  s
                  stid
                }
                nextToken
              }
            }
            """
        )

        parameters = {"market": market_symbol}

        result = await self._execute_query(query=query, parameters=parameters)
        return result

    async def main_account_from_proxy(self, proxy_account=str) -> str:
        query = gql(
            """
            query findUserByProxyAccount($proxy_account: String!) {
                findUserByProxyAccount(proxy_account: $proxy_account) {
                    items {
                        hash_key
                        range_key
                        stid
                    }
                }
            }
            """
        )
        parameters = {"proxy_account": proxy_account}

        result = await self._execute_query(query=query, parameters=parameters)
        main_account = result["findUserByProxyAccount"]["items"][0]["range_key"]
        return main_account

    async def recent_trades(self, market_symbol: str, limit: int) -> Dict[str, Any]:
        query = gql(
            """
            query getRecentTrades($market: String!, $limit: Int, $nextToken: String) {
              getRecentTrades(m: $market, limit: $limit, nextToken: $nextToken) {
                items {
                    isReverted
                    m
                    p
                    q
                    t
                }
              }
            }
            """
        )

        parameters = {"market": market_symbol, "limit": limit}

        result = await self._execute_query(query=query, parameters=parameters)
        return result

    async def get_all_balances_by_main_account(self, main_account: str) -> Dict[str, Any]:
        query = gql(
            """
            query GetAllBalancesByMainAccount($main: String!) {
                getAllBalancesByMainAccount(main_account: $main) {
                    items {
                        a
                        f
                        r
                    }
                }
            }
            """
        )

        parameters = {"main": main_account}

        result = await self._execute_query(query=query, parameters=parameters)
        return result

    async def get_order_fills_by_main_account(
        self, from_timestamp: float, to_timestamp: float, main_account: str
    ) -> Dict[str, Any]:
        query = gql(
            """
            query listTradesByMainAccount(
                $main_account:String!
                $limit: Int
                $from: AWSDateTime!
                $to: AWSDateTime!
                $nextToken: String
            ) {
                listTradesByMainAccount(
                    main_account: $main_account
                    from: $from
                    to: $to
                    limit: $limit
                    nextToken: $nextToken
                ) {
                    items {
                        isReverted
                        m
                        m_id
                        p
                        q
                        stid
                        t
                        t_id
                        trade_id
                    }
                }
            }
            """
        )

        parameters = {
            "main_account": main_account,
            "from": self._timestamp_to_aws_datetime_string(timestamp=from_timestamp),
            "to": self._timestamp_to_aws_datetime_string(timestamp=to_timestamp),
        }

        result = await self._execute_query(query=query, parameters=parameters)

        return result

    async def place_order(self, polkadex_order: Dict[str, Any], signature: Dict[str, Any]) -> Dict[str, Any]:
        query = gql(
            """
            mutation PlaceOrder($payload: String!) {
                place_order(input: {payload: $payload})
            }
            """
        )

        input_parameters = [
            polkadex_order,
            signature,
        ]
        parameters = {"payload": json.dumps({"PlaceOrder": input_parameters})}

        result = await self._execute_query(query=query, parameters=parameters)
        return result

    async def cancel_order(
        self,
        order_id: str,
        market_symbol: str,
        main_address: str,
        proxy_address: str,
        signature: Dict[str, Any],
    ) -> Dict[str, Any]:
        query = gql(
            """
            mutation CancelOrder($payload: String!) {
                cancel_order(input: {payload: $payload})
            }
            """
        )

        input_parameters = [
            order_id,
            main_address,
            proxy_address,
            market_symbol,
            signature,
        ]
        parameters = {"payload": json.dumps({"CancelOrder": input_parameters})}

        result = await self._execute_query(query=query, parameters=parameters)
        return result

    async def list_order_history_by_account(
        self, main_account: str, from_time: float, to_time: float
    ) -> Dict[str, Any]:
        query = gql(
            """
            query ListOrderHistory(
                $main_account:String!
                $limit: Int
                $from: AWSDateTime!
                $to: AWSDateTime!
                $nextToken: String
            ) {
                listOrderHistorybyMainAccount(
                    main_account: $main_account
                    from: $from
                    to: $to
                    limit: $limit
                    nextToken: $nextToken
                ) {
                    items {
                        u
                        cid
                        id
                        t
                        m
                        s
                        ot
                        st
                        p
                        q
                        afp
                        fq
                        fee
                        isReverted
                    }
                }
            }
            """
        )

        parameters = {
            "main_account": main_account,
            "to": self._timestamp_to_aws_datetime_string(timestamp=to_time),
            "from": self._timestamp_to_aws_datetime_string(timestamp=from_time),
        }

        result = await self._execute_query(query=query, parameters=parameters)
        return result

    async def find_order_by_main_account(self, main_account: str, market_symbol: str, order_id: str) -> Dict[str, Any]:
        query = gql(
            """
            query FindOrder($main_account: String!, $market: String!, $order_id: String!) {
                findOrderByMainAccount(main_account: $main_account, market: $market, order_id: $order_id) {
                    afp
                    cid
                    fee
                    fq
                    id
                    isReverted
                    m
                    ot
                    p
                    q
                    s
                    st
                    stid
                    t
                    u
                }
            }
        """
        )

        parameters = {
            "main_account": main_account,
            "market": market_symbol,
            "order_id": order_id,
        }

        result = await self._execute_query(query=query, parameters=parameters)
        return result

    async def list_open_orders_by_main_account(self, main_account: str) -> Dict[str, Any]:
        query = gql(
            """
            query ListOpenOrdersByMainAccount($main_account: String!, $limit: Int, $nextToken: String) {
                listOpenOrdersByMainAccount(main_account: $main_account, limit: $limit, nextToken: $nextToken) {
                    items {
                        u
                        cid
                        id
                        t
                        m
                        s
                        ot
                        st
                        p
                        q
                        afp
                        fq
                        fee
                        stid
                        isReverted
                    }
                }
            }
        """
        )

        parameters = {"main_account": main_account}

        result = await self._execute_query(query=query, parameters=parameters)
        return result

    async def listen_to_orderbook_updates(self, events_handler: Callable, market_symbol: str):
        while True:
            try:
                stream_name = f"{market_symbol}-{CONSTANTS.ORDERBOOK_UPDATES_STREAM_NAME}"
                async for event in self._subscribe_to_stream(stream_name=stream_name):
                    events_handler(event=event, market_symbol=market_symbol)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error listening to order book updates from Polkadex", exc_info=True)

    async def listen_to_public_trades(self, events_handler: Callable, market_symbol: str):
        while True:
            try:
                stream_name = f"{market_symbol}-{CONSTANTS.RECENT_TRADES_STREAM_NAME}"
                async for event in self._subscribe_to_stream(stream_name=stream_name):
                    events_handler(event=event)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error listening to public trades from Polkadex", exc_info=True)

    async def listen_to_private_events(self, events_handler: Callable, address: str):
        while True:
            try:
                async for event in self._subscribe_to_stream(stream_name=address):
                    events_handler(event=event)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error listening to private updates from Polkadex", exc_info=True)

    async def _execute_query(
        self,
        query: DocumentNode,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        # Extract host from url
        url = CONSTANTS.GRAPHQL_ENDPOINTS[self._domain]

        transport = AIOHTTPTransport(url=url, auth=self._auth)
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:
            result = await session.execute(query, variable_values=parameters, parse_result=True)

        return result

    async def _subscribe_to_stream(self, stream_name: str) -> AsyncIterable:
        query = gql(
            """
            subscription WebsocketStreamsMessage($name: String!) {
                websocket_streams(name: $name) {
                    data
                }
            }
            """
        )
        variables = {"name": stream_name}

        async for result in self._ws_session.subscribe(query, variable_values=variables, parse_result=True):
            yield result

    @staticmethod
    def _timestamp_to_aws_datetime_string(timestamp: float) -> str:
        timestamp_string = datetime.utcfromtimestamp(timestamp).isoformat(timespec="milliseconds") + "Z"
        return timestamp_string
