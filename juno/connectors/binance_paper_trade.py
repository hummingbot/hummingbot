from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from decimal import Decimal
from functools import partial
from types import TracebackType
from typing import Any, AsyncIterable, AsyncIterator, Dict, Optional

import aiohttp
import simplejson as json
from aiolimiter import AsyncLimiter
from multidict import CIMultiDictProxy, istr

from juno import time
from juno.http import ClientResponse, ClientSession, connect_refreshing_stream
from juno.models import Candle, ConnectorException, SavingsProduct, Trade

_log = logging.getLogger(__name__)

_BASE_API_URL = "https://api.binance.com"
_BASE_WS_URL = "wss://stream.binance.com:9443"

_SEC_NONE = 0  # Endpoint can be accessed freely.
_SEC_USER_DATA = 2  # Endpoint requires sending a valid API-Key and signature.

_ERR_TOO_MANY_REQUESTS = -1003


class BinancePaperTradeConnector:
    # Capabilities.
    can_stream_historical_candles: bool = True
    can_stream_candles: bool = True

    def __init__(self) -> None:
        self._session = ClientSession(name=type(self).__name__)

        # Rate limiters.
        x = 1.5  # We use this factor to be on the safe side and not use up the entire bucket.
        self._reqs_per_min_limiter = AsyncLimiter(1200, 60 * x)
        self._raw_reqs_limiter = AsyncLimiter(5000, 300 * x)

    async def __aenter__(self) -> BinancePaperTradeConnector:
        await self._session.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self._session.__aexit__(exc_type, exc, tb)

    # Candles.

    def list_candle_intervals(self) -> list[int]:
        return [
            60000,  # 1m
            180000,  # 3m
            300000,  # 5m
            900000,  # 15m
            1800000,  # 30m
            3600000,  # 1h
            7200000,  # 2h
            14400000,  # 4h
            21600000,  # 6h
            28800000,  # 8h
            43200000,  # 12h
            86400000,  # 1d
            259200000,  # 3d
            604800000,  # 1w
            2629746000,  # 1M
        ]

    async def stream_historical_candles(
        self,
        trading_pair: str,
        interval: int,
        start: int,
        end: int,
    ) -> AsyncIterable[Candle]:
        limit = 1000  # Max possible candles per request.
        binance_interval = time.format_interval(interval)
        binance_trading_pair = _to_binance_trading_pair(trading_pair)
        binance_start = start
        binance_end = end - 1
        while True:
            if binance_start > binance_end:
                return
            content = await self._api_request(
                method="GET",
                url="/api/v3/klines",
                data={
                    "symbol": binance_trading_pair,
                    "interval": binance_interval,
                    "startTime": binance_start,
                    "endTime": binance_end,
                    "limit": limit,
                },
            )
            for c in content:
                # Binance can return bad candles where the time does not fall within the requested
                # interval. For example, the second candle of the following query has bad time:
                # https://api.binance.com/api/v3/klines?symbol=ETHBTC&interval=4h&limit=10&startTime=1529971200000&endTime=1530000000000
                candle_time = c[0]
                yield Candle(
                    time=candle_time,
                    open=Decimal(c[1]),
                    high=Decimal(c[2]),
                    low=Decimal(c[3]),
                    close=Decimal(c[4]),
                    volume=Decimal(c[5]),
                )
                binance_start = candle_time + 1
            if len(content) < limit:
                return

    @asynccontextmanager
    async def connect_stream_candles(self, trading_pair: str, interval: int) -> AsyncIterator[AsyncIterable[Candle]]:
        # Binance disconnects a websocket connection every 24h. Therefore, we reconnect every 12h.
        # Note that two streams will send events with matching evt_times.
        # This can be used to switch from one stream to another and avoiding the edge case where
        # we miss out on the very last update to a candle.

        async def inner(ws: AsyncIterable[Any]) -> AsyncIterable[Candle]:
            async for data in ws:
                c = data["k"]
                if c["x"]:  # Closed.
                    yield Candle(
                        time=c["t"],
                        open=Decimal(c["o"]),
                        high=Decimal(c["h"]),
                        low=Decimal(c["l"]),
                        close=Decimal(c["c"]),
                        volume=Decimal(c["v"]),
                    )

        async with self._connect_refreshing_stream(
            url=f"/ws/{_to_binance_ws_trading_pair(trading_pair)}@kline_{time.format_interval(interval)}",
            interval=12 * time.HOUR_MS,
            name="candles",
        ) as ws:
            yield inner(ws)

    # Trades.

    async def stream_historical_trades(self, trading_pair: str, start: int, end: int) -> AsyncIterable[Trade]:
        # Aggregated trades. This means trades executed at the same time, same price and as part of
        # the same order will be aggregated by summing their size.
        batch_start = start
        payload: Dict[str, Any] = {
            "symbol": _to_binance_trading_pair(trading_pair),
        }
        while True:
            batch_end = batch_start + time.HOUR_MS
            payload["startTime"] = batch_start
            payload["endTime"] = min(batch_end, end) - 1  # Inclusive.

            trade_time = None

            content = await self._api_request(
                method="GET",
                url="/api/v3/aggTrades",
                data=payload,
            )
            for t in content:
                trade_time = t["T"]
                assert trade_time < end
                yield Trade(
                    id=t["a"],
                    time=trade_time,
                    price=Decimal(t["p"]),
                    size=Decimal(t["q"]),
                )
            batch_start = trade_time + 1 if trade_time is not None else batch_end
            if batch_start >= end:
                break

    @asynccontextmanager
    async def connect_stream_trades(self, trading_pair: str) -> AsyncIterator[AsyncIterable[Trade]]:
        async def inner(ws: AsyncIterable[Any]) -> AsyncIterable[Trade]:
            async for data in ws:
                yield Trade(
                    id=data["a"],
                    time=data["T"],
                    price=Decimal(data["p"]),
                    size=Decimal(data["q"]),
                )

        async with self._connect_refreshing_stream(
            url=f"/ws/{_to_binance_ws_trading_pair(trading_pair)}@trade",
            interval=12 * time.HOUR_SEC,
            name="trades",
        ) as ws:
            yield inner(ws)

    # Savings.

    async def map_savings_products(self, asset: Optional[str] = None) -> Dict[str, SavingsProduct]:
        return {}

    async def purchase_savings_product(self, product_id: str, size: Decimal) -> None:
        _log.info(f"would have attempted to purchase {size} of {product_id}")

    async def redeem_savings_product(self, product_id: str, size: Decimal) -> None:
        _log.info(f"would have attempted to redeem {size} of {product_id}")

    # Common.

    async def _api_request(
        self,
        method: str,
        url: str,
        weight: int = 1,
        security: int = _SEC_NONE,
        data: Optional[Any] = None,
    ) -> Any:
        limiter_tasks = [
            self._raw_reqs_limiter.acquire(),
            self._reqs_per_min_limiter.acquire(weight),
        ]
        await asyncio.gather(*limiter_tasks)

        kwargs: Dict[str, Any] = {}

        if security == _SEC_USER_DATA:
            headers: Dict[str, str] = {}
            data = data or {}
            await self._authenticate_request(headers, data)
            if headers:
                kwargs["headers"] = headers
        if data:
            kwargs["params" if method == "GET" else "data"] = data

        try:
            response = await self._request(method=method, url=_BASE_API_URL + url, **kwargs)
        except BinanceClientException as exc:
            await self._intercept_client_exception(exc)
            raise

        return await response.json()

    async def _authenticate_request(self, headers: Dict[str, str], data: Dict[str, Any]) -> None:
        pass

    # We don't want to retry here because the caller of this method may need to adjust request
    # params on retry.
    async def _request(self, method: str, url: str, **kwargs: Any) -> ClientResponse:
        try:
            async with self._session.request(method=method, url=url, **kwargs) as response:
                # TODO: If status 50X (502 for example during exchange maintenance), we may
                # want to wait for a some kind of a successful health check before retrying.
                if response.status >= 500:
                    text_content = await response.text()
                    raise ConnectorException(f"Server (5XX) error {response.status} {text_content}")
                if response.status >= 400:
                    try:
                        content = await response.json()
                        code = content.get("code")
                        message = content.get("msg")
                        if code is not None:
                            raise BinanceClientException(code, message, response.headers)
                    except aiohttp.client_exceptions.ContentTypeError:
                        pass
                    text_content = await response.text()
                    raise ConnectorException(f"Client (4XX) error {response.status} {text_content}")
                return response
        except (
            aiohttp.ClientConnectionError,
            aiohttp.ClientPayloadError,
        ) as e:
            _log.warning(f"request exc: {e}")
            raise ConnectorException(str(e))

    @asynccontextmanager
    async def _connect_refreshing_stream(
        self,
        url: str,
        interval: float,
        name: str,
    ) -> AsyncIterator[AsyncIterable[Any]]:
        try:
            async with connect_refreshing_stream(
                self._session,
                url=_BASE_WS_URL + url,
                interval=interval,
                loads=partial(json.loads, use_decimal=True, parse_constant=Decimal),
                take_until=lambda old, new: old["E"] < new["E"],
                name=name,
                raise_on_disconnect=True,
            ) as stream:
                yield stream
        except (
            aiohttp.ClientConnectionError,
            aiohttp.ClientPayloadError,
            aiohttp.ClientResponseError,
            aiohttp.WebSocketError,
        ) as e:
            raise ConnectorException(str(e))

    async def _intercept_client_exception(
        self,
        exc: BinanceClientException,
    ) -> None:
        if exc.code == _ERR_TOO_MANY_REQUESTS:
            retry_after = exc.headers.get(istr("Retry-After"))
            if retry_after:
                _log.info(f"server provided retry-after {retry_after}; sleeping")
                await asyncio.sleep(float(retry_after))


class BinanceClientException(ConnectorException):
    """4XX errors specific to Binance."""

    def __init__(self, code: int, message: Optional[str], headers: CIMultiDictProxy) -> None:
        super().__init__(message)
        self.code = code
        self.headers = headers


def _to_binance_trading_pair(trading_pair: str) -> str:
    return trading_pair.replace("-", "")


def _to_binance_ws_trading_pair(trading_pair: str) -> str:
    return _to_binance_trading_pair(trading_pair).lower()
