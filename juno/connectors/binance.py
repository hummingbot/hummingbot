from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import urllib.parse
from contextlib import suppress
from decimal import Decimal
from types import TracebackType
from typing import Any, Dict, Optional

from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from juno import time
from juno.models import ConnectorException, SavingsProduct

from .binance_paper_trade import _SEC_USER_DATA, BinanceClientException, BinancePaperTradeConnector

_log = logging.getLogger(__name__)

_ERR_INVALID_TIMESTAMP = -1021


class BinanceConnector(BinancePaperTradeConnector):
    def __init__(self, api_key: str, secret_key: str) -> None:
        super().__init__()
        self._api_key = api_key
        self._secret_key_bytes = secret_key.encode("utf-8")

        self._clock = Clock(self)

    async def __aenter__(self) -> BinanceConnector:
        await super().__aenter__()
        await self._clock.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self._clock.__aexit__(exc_type, exc, tb)
        await super().__aexit__(exc_type, exc, tb)

    # Savings.

    async def map_savings_products(self, asset: Optional[str] = None) -> Dict[str, SavingsProduct]:
        # TODO: This endpoint is paginated but only fetches the first page.
        data: Dict[str, Any] = {
            "size": 100,
        }
        if asset is not None:
            data["asset"] = asset
        content = await self._api_request(
            method="GET",
            url="/sapi/v1/lending/daily/product/list",
            data=data,
            security=_SEC_USER_DATA,
        )
        result = {}
        for product in content:
            product_asset = product["asset"]
            result[product_asset] = SavingsProduct(
                product_id=product["productId"],
                status=product["status"],
                asset=product_asset,
                can_purchase=product["canPurchase"],
                can_redeem=product["canRedeem"],
                purchased_amount=Decimal(product["purchasedAmount"]),
                min_purchase_amount=Decimal(product["minPurchaseAmount"]),
                limit=Decimal(product["upLimit"]),
                limit_per_user=Decimal(product["upLimitPerUser"]),
            )
        return result

    async def purchase_savings_product(self, product_id: str, size: Decimal) -> None:
        await self._api_request(
            method="POST",
            url="/sapi/v1/lending/daily/purchase",
            data={
                "productId": product_id,
                "amount": _to_decimal(size),
            },
            security=_SEC_USER_DATA,
        )

    async def redeem_savings_product(self, product_id: str, size: Decimal) -> None:
        await self._api_request(
            method="POST",
            url="/sapi/v1/lending/daily/redeem",
            data={
                "productId": product_id,
                "amount": _to_decimal(size),
                "type": "FAST",  # "FAST" | "NORMAL"
            },
            security=_SEC_USER_DATA,
        )

    # Common.

    async def _authenticate_request(self, headers: Dict[str, str], data: Dict[str, Any]) -> None:
        await self._clock.wait()

        headers["X-MBX-APIKEY"] = self._api_key

        data["timestamp"] = str(time.now() + self._clock.time_diff)

        query_str_bytes = urllib.parse.urlencode(data).encode("utf-8")
        signature = hmac.new(self._secret_key_bytes, query_str_bytes, hashlib.sha256)
        data["signature"] = signature.hexdigest()

    async def _intercept_client_exception(
        self,
        exc: BinanceClientException,
    ) -> None:
        await super()._intercept_client_exception(exc)
        if exc.code == _ERR_INVALID_TIMESTAMP:
            _log.warning("received invalid timestamp; syncing clock before exc")
            self._clock.clear()


class Clock:
    def __init__(self, binance: BinancePaperTradeConnector) -> None:
        self.time_diff = 0
        self._binance = binance
        self._synced = asyncio.Event()
        self._periodic_sync_task: Optional[asyncio.Task[None]] = None
        self._reset_periodic_sync: asyncio.Event = asyncio.Event()

    async def __aenter__(self) -> Clock:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        if self._periodic_sync_task:
            self._periodic_sync_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._periodic_sync_task

    async def wait(self) -> None:
        if not self._periodic_sync_task:
            self._periodic_sync_task = asyncio.create_task(self._periodic_sync())

        await self._synced.wait()

    def clear(self) -> None:
        self._synced.clear()
        if self._periodic_sync_task:
            self._reset_periodic_sync.set()

    async def _periodic_sync(self) -> None:
        while True:
            await self._sync_clock()
            # 6 hours.
            sleep_task = asyncio.create_task(asyncio.sleep(time.HOUR_SEC * 6))
            reset_periodic_sync_task = asyncio.create_task(self._reset_periodic_sync.wait())
            try:
                await asyncio.wait(  # type:ignore
                    [sleep_task, reset_periodic_sync_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                if not sleep_task.done():
                    sleep_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await sleep_task
                if not reset_periodic_sync_task.done():
                    reset_periodic_sync_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await reset_periodic_sync_task
                self._reset_periodic_sync.clear()

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(),
        retry=retry_if_exception_type(ConnectorException),
        before_sleep=before_sleep_log(_log, logging.WARNING),
    )
    async def _sync_clock(self) -> None:
        # https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#check-server-time
        _log.info("syncing clock with Binance")
        before = time.now()
        content = await self._binance._api_request(
            method="GET",
            url="/api/v3/time",
        )
        server_time = content["serverTime"]
        after = time.now()
        # Assume response time is same as request time.
        delay = (after - before) // 2
        local_time = before + delay
        # Adjustment required converting from local time to server time.
        self.time_diff = server_time - local_time
        _log.info(f"found {self.time_diff}ms time difference")
        self._synced.set()


def _to_decimal(value: Decimal) -> str:
    # Converts from scientific notation.
    # 6.4E-7 -> 0.0000_0064
    return f"{value:f}"
