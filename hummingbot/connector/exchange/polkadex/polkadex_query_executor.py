import asyncio
import json
import logging
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, AsyncIterable, Callable, Dict, List, Optional

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.appsync_auth import AppSyncAuthentication
from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
from graphql import DocumentNode

from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
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
    async def recent_trade(self, market_symbol: str) -> Dict[str, Any]:
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
    async def find_order_by_id(self, order_id: str) -> Dict[str, Any]:
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

    def __init__(
        self,
        throttler: AsyncThrottler,
        auth: AppSyncAuthentication,
        domain: Optional[str] = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._domain = domain
        self._websocket_failure = False
        self._websocket_failure_timestamp = float(0)
        self._restart_initialization = False
        self._throttler = throttler

    async def all_assets(self) -> List[Dict[str, Any]]:
        query = gql(
            """
            query getAllAssets($limit: Int, $nextToken: String) {
                getAllAssets(limit: $limit, nextToken: $nextToken) {
                    items {
                        asset_id
                        name
                    }
                    nextToken
                }
            }
            """
        )

        return await self._query_all_pages(
            query=query,
            parameters=None,
            field_name="getAllAssets",
            throttler_limit_id=CONSTANTS.ALL_ASSETS_LIMIT_ID
        )

    async def all_markets(self) -> List[Dict[str, Any]]:
        query = gql(
            """
            query MyQuery {
                getAllMarkets {
                    items {
                        market
                        min_volume
                        price_tick_size
                        qty_step_size
                    }
                }
            }
            """
        )

        return (
            await self._execute_query(
                query=query,
                parameters=None,
                field_name="getAllMarkets",
                throttler_limit_id=CONSTANTS.ALL_MARKETS_LIMIT_ID)
        )["items"]

    async def get_orderbook(self, market_symbol: str) -> List[Dict[str, Any]]:
        query = gql(
            """
            query getOrderbook($market: String!, $limit: Int, $nextToken: String) {
              getOrderbook(market: $market, limit: $limit, nextToken: $nextToken) {
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

        parameters = {
            "market": market_symbol,
        }

        return await self._query_all_pages(
            query=query,
            parameters=parameters,
            field_name="getOrderbook",
            throttler_limit_id=CONSTANTS.ORDERBOOK_LIMIT_ID
        )

    async def main_account_from_proxy(self, proxy_account=str) -> str:
        # "proxy account" is actually a "trade account"
        query = gql(
            """
            query findUserByTradeAccount($trade_account: String!) {
              findUserByTradeAccount(trade_account: $trade_account) {
                items {
                  main
                }
              }
            }
            """
        )

        parameters = {
            "trade_account": proxy_account,
        }

        return (await self._execute_query(
            query=query,
            parameters=parameters,
            field_name="findUserByTradeAccount",
            throttler_limit_id=CONSTANTS.FIND_USER_LIMIT_ID
        ))["items"][0]["main"]

    async def recent_trade(self, market_symbol: str) -> Dict[str, Any]:
        query = gql(
            """
            query listRecentTrades($market: String!, $limit: Int, $nextToken: String) {
              listRecentTrades(m: $market, limit: $limit, nextToken: $nextToken) {
                items {
                    p
                }
              }
            }
            """
        )

        parameters = {
            "market": market_symbol,
            "limit": 1,
        }

        return (await self._execute_query(
            query=query,
            parameters=parameters,
            field_name="listRecentTrades",
            throttler_limit_id=CONSTANTS.PUBLIC_TRADES_LIMIT_ID
        ))["items"][0]

    async def get_all_balances_by_main_account(self, main_account: str) -> List[Dict[str, Any]]:
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

        parameters = {
            "main": main_account,
        }

        return (await self._execute_query(
            query=query,
            parameters=parameters,
            field_name="getAllBalancesByMainAccount",
            throttler_limit_id=CONSTANTS.ALL_BALANCES_LIMIT_ID
        ))["items"]

    async def get_order_fills_by_main_account(
        self,
        from_timestamp: float,
        to_timestamp: float,
        main_account: str,
    ) -> List[Dict[str, Any]]:
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
                        maker_id
                        p
                        q
                        stid
                        t
                        taker_id
                        trade_id
                    }
                    nextToken
                }
            }
            """
        )

        parameters = {
            "main_account": main_account,
            "from": self._timestamp_to_aws_datetime_string(timestamp=from_timestamp),
            "to": self._timestamp_to_aws_datetime_string(timestamp=to_timestamp),
        }

        return await self._query_all_pages(
            query=query,
            parameters=parameters,
            field_name="listTradesByMainAccount",
            throttler_limit_id=CONSTANTS.ALL_FILLS_LIMIT_ID
        )

    async def place_order(self, polkadex_order: Dict[str, Any], signature: Dict[str, Any]) -> Optional[str]:
        """
        :return: Exchange order ID in case of success, None otherwise
        """
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

        parameters = {
            "payload": json.dumps({"PlaceOrder": input_parameters}),
        }

        response = await self._execute_query(
            query=query,
            parameters=parameters,
            field_name="place_order",
            throttler_limit_id=CONSTANTS.PLACE_ORDER_LIMIT_ID
        )

        # TODO (dmitry): leave only one format once PolkaDEX team would apply the change on their end
        # so currently the format is like
        # {'place_order': '{"is_success":true,"body":"exchange order id here"}'}
        # but the new format would be simple JSON
        # {"place_order": {"is_success":true,"body":"exchange order id here"}}
        # so currently we have to support both of them

        if isinstance(response, str):
            response = json.loads(response)

        exchange_order_id = None
        if response["is_success"]:
            exchange_order_id = response["body"]

        return exchange_order_id

    async def cancel_order(
        self,
        order_id: str,
        market_symbol: str,
        main_address: str,
        proxy_address: str,
        signature: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
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

        parameters = {
            "payload": json.dumps({"CancelOrder": input_parameters}),
        }

        try:
            return await self._execute_query(
                query=query,
                parameters=parameters,
                field_name="cancel_order",
                throttler_limit_id=CONSTANTS.CANCEL_ORDER_LIMIT_ID
            )
        except Exception:
            self.logger().error(f"Failed to cancel order {order_id}; query parameters: {parameters}")
            raise

    async def find_order_by_id(self, order_id: str) -> Dict[str, Any]:
        query = gql(
            """
            query FindOrderById($order_id: String!) {
                findOrderById(order_id: $order_id) {
                    fq
                    id
                    st
                }
            }
            """
        )

        parameters = {
            "order_id": order_id,
        }

        return await self._execute_query(
            query=query,
            parameters=parameters,
            field_name="findOrderById",
            # TODO (dmitry): define separate limit
            throttler_limit_id=CONSTANTS.ORDER_UPDATE_LIMIT_ID
        )

    async def list_open_orders_by_main_account(self, main_account: str) -> List[Dict[str, Any]]:
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
                    nextToken
                }
            }
        """
        )

        parameters = {
            "main_account": main_account,
        }

        return await self._query_all_pages(
            query=query,
            parameters=parameters,
            field_name="listOpenOrdersByMainAccount",
            throttler_limit_id=CONSTANTS.LIST_OPEN_ORDERS_LIMIT_ID
        )

    async def listen_to_orderbook_updates(self, events_handler: Callable, market_symbol: str):
        while True:
            try:
                stream_name = f"{market_symbol}-{CONSTANTS.ORDERBOOK_UPDATES_STREAM_NAME}"
                async for event in self._subscribe_to_stream(stream_name=stream_name):
                    events_handler(event=event, market_symbol=market_symbol)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error listening to order book updates from Polkadex. Error: {e}",
                    exc_info=True
                )
                sys.exit()
                # TODO (dmitry): add proper handling of exceptions to all WS listeners
                # await self.websocket_connect_failure()

    async def websocket_connect_failure(self):
        self.logger().info(f"Websocket connect failure.{self._websocket_failure}")
        if self._websocket_failure:
            if abs(self._websocket_failure_timestamp - datetime.utcnow().timestamp()) > float(10):
                self._restart_initialization = True
        else:
            await self.set_websocket_failure_timestamp()

    async def set_websocket_failure_timestamp(self):
        self._websocket_failure_timestamp = datetime.utcnow().timestamp()
        self._websocket_failure = True

    async def listen_to_public_trades(self, events_handler: Callable, market_symbol: str):
        while True:
            try:
                stream_name = f"{market_symbol}-{CONSTANTS.RECENT_TRADES_STREAM_NAME}"
                async for event in self._subscribe_to_stream(stream_name=stream_name):
                    events_handler(event=event)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error listening to public trades from Polkadex. Error: {e}",
                    exc_info=True
                )
                sys.exit()
                await self.websocket_connect_failure()

    async def listen_to_private_events(self, events_handler: Callable, address: str):
        while True:
            try:
                async for event in self._subscribe_to_stream(stream_name=address):
                    events_handler(event=event)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error listening to private updates from Polkadex. Error: {e}",
                    exc_info=True
                )
                sys.exit()

    async def _execute_query(
        self,
        query: DocumentNode,
        parameters: Optional[Dict[str, Any]],
        field_name: str,
        throttler_limit_id: str
    ):
        async with self._throttler.execute_task(limit_id=throttler_limit_id):
            url = CONSTANTS.GRAPHQL_ENDPOINTS[self._domain]

            transport = AIOHTTPTransport(url=url, auth=self._auth)
            async with Client(transport=transport, fetch_schema_from_transport=False) as session:
                result = await session.execute(query, variable_values=parameters, parse_result=True)

            return result[field_name]

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

        url = CONSTANTS.GRAPHQL_WS_ENDPOINTS[self._domain]
        transport = AppSyncWebsocketsTransport(url=url, auth=self._auth)

        async with Client(transport=transport, fetch_schema_from_transport=False) as session:
            async for result in session.subscribe(query, variable_values=variables, parse_result=True):
                yield result

    @staticmethod
    def _timestamp_to_aws_datetime_string(timestamp: float) -> str:
        timestamp_string = datetime.utcfromtimestamp(timestamp).isoformat(timespec="milliseconds") + "Z"
        return timestamp_string

    async def _query_all_pages(
        self,
        query: DocumentNode,
        parameters: Optional[Dict[str, Any]],
        field_name: str,
        throttler_limit_id: str,
        limit: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Most of the PolkaDEX API endpoints return paginated result. The pagination mechanism is based on two parameters:
        `limit` and `nextToken`. First one is used to limit the number of entries on a page, the second one identifies
        the next page. This function iterates through all the pages to get 100% of data.

        IMPORTANT considerations:

        * by default we set the page size to 300 entries, but in most of the cases PolkaDEX APIs will limit response
        body size to 1MB

        :param query: GraphQL query
        :param parameters: query parameters
        :param field_name: name of GraphQL field
        :param throttler_limit_id: the string identifier for a throttling limit
        :param limit: page size
        """
        if parameters is None:
            parameters = {}

        parameters["limit"] = limit

        # execute first query and get nextToken from the response
        data = await self._execute_query(query, parameters, field_name, throttler_limit_id)
        items = data["items"]
        next_token = data["nextToken"]

        while next_token:
            parameters["nextToken"] = next_token
            data = await self._execute_query(query, parameters, field_name, throttler_limit_id)
            items += data["items"]
            next_token = data["nextToken"]

        return items
