import asyncio
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

import grpc
from neutronx_sdk import ChainTxError, OrderRequest, TxSender
from neutronx_sdk.orders import (
    BATCH_CANCEL_MAX_IDS,
    BATCH_PLACE_MAX_ORDERS,
    batch_cancel_orders_msg,
    batch_place_orders_msg,
    is_batchable,
    place_order_msg,
)
from neutronx_sdk.tx import (
    PlaceOrderOutcome,
    orders_within_prefill_ceiling,
    parse_batch_cancel_outcome,
    parse_batch_place_outcomes,
    parse_place_order_outcomes,
)

from hummingbot.connector.derivative.neutronx_perpetual import neutronx_perpetual_constants as CONSTANTS
from hummingbot.logger import HummingbotLogger

MAX_PLACES_PER_TX = BATCH_PLACE_MAX_ORDERS


@dataclass(frozen=True)
class PlacedOrder:
    order_id: int
    status: str
    filled: Decimal


class CancelOutcome(str, Enum):
    CANCELLED = "cancelled"
    GONE = "gone"
    REJECTED = "rejected"


@dataclass(frozen=True)
class CancelledOrder:
    order_id: int
    outcome: CancelOutcome


@dataclass
class _Pending:
    places: List[OrderRequest] = field(default_factory=list)
    place_futures: List[asyncio.Future] = field(default_factory=list)
    cancels: Dict[int, List[asyncio.Future]] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.places) + len(self.cancels)


class OrderTxQueue:
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        sender: TxSender,
        *,
        max_places_per_tx: int = MAX_PLACES_PER_TX,
        gas_ceiling: int = CONSTANTS.DEFAULT_TX_GAS_CEILING,
        flush_interval: float = CONSTANTS.TX_FLUSH_INTERVAL,
    ) -> None:
        self._sender = sender
        self._max_places = max(1, min(max_places_per_tx, MAX_PLACES_PER_TX))
        self._gas_ceiling = gas_ceiling
        self._flush_interval = flush_interval
        self._pending = _Pending()
        self._wakeup = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if not self.running:
            self._task = asyncio.ensure_future(self._run())

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._fail_all(self._take(), ConnectionError("the NeutronX transaction queue stopped"))

    async def place(self, request: OrderRequest) -> PlacedOrder:
        future = self._future()
        self._pending.places.append(request)
        self._pending.place_futures.append(future)
        self._wakeup.set()
        return await future

    async def cancel(self, order_id: int) -> CancelledOrder:
        future = self._future()
        self._pending.cancels.setdefault(order_id, []).append(future)
        self._wakeup.set()
        return await future

    def _future(self) -> asyncio.Future:
        if not self.running:
            raise ConnectionError("the NeutronX transaction queue is not running")
        return asyncio.get_running_loop().create_future()

    async def _run(self) -> None:
        while True:
            await self._wakeup.wait()
            await asyncio.sleep(self._flush_interval)
            self._wakeup.clear()
            batch = self._take()
            if batch.size:
                await asyncio.gather(*(self._submit(part) for part in self._by_kind(batch)))
            if self._pending.size:
                self._wakeup.set()

    def _take(self) -> _Pending:
        pending = self._pending
        cancels = list(pending.cancels.items())[:BATCH_CANCEL_MAX_IDS]
        room = orders_within_prefill_ceiling(self._gas_ceiling, self._cancel_msgs(order_id for order_id, _ in cancels))
        places = min(self._max_places, room if room or cancels else 1)
        batch = _Pending(
            places=pending.places[:places],
            place_futures=pending.place_futures[:places],
            cancels=dict(cancels),
        )
        self._pending = _Pending(
            places=pending.places[places:],
            place_futures=pending.place_futures[places:],
            cancels=dict(list(pending.cancels.items())[len(cancels):]),
        )
        return batch

    @staticmethod
    def _by_kind(batch: _Pending) -> List[_Pending]:
        resting = _Pending(cancels=batch.cancels)
        immediate = _Pending()
        for request, future in zip(batch.places, batch.place_futures):
            part = resting if is_batchable(request) else immediate
            part.places.append(request)
            part.place_futures.append(future)
        return [part for part in (immediate, resting) if part.size]

    async def _submit(self, batch: _Pending) -> None:
        try:
            await self._send(batch)
        except (grpc.aio.AioRpcError, ChainTxError) as error:
            rest = self._drop_missing_cancels(batch, error)
            if rest is not None:
                if rest.size:
                    await self._submit(rest)
                return
            if batch.size == 1:
                self._fail_all(batch, error)
                return
            self.logger().warning(f"NeutronX batch of {batch.size} was refused, sending each alone: {error}")
            for single in self._split(batch):
                await self._submit(single)
        except Exception as error:
            self._fail_all(batch, error)

    async def _send(self, batch: _Pending) -> None:
        creator = self._sender.wallet.address
        batched = [i for i, request in enumerate(batch.places) if is_batchable(request)]
        singles = [i for i, request in enumerate(batch.places) if not is_batchable(request)]
        msgs = self._cancel_msgs(batch.cancels)
        if batched:
            msgs.append(batch_place_orders_msg(creator, [batch.places[i] for i in batched]))
        msgs.extend(place_order_msg(creator, batch.places[i]) for i in singles)
        gas_limit = await self._sender.estimate_gas(msgs, ceiling=self._gas_ceiling)
        result = await self._sender.send(msgs, gas_limit=gas_limit)
        responses = list(result.msg_responses)
        cursor = 1 if batch.cancels else 0
        self._resolve_cancels(batch, responses[:cursor])
        if batched:
            self._resolve_places(batch, batched, parse_batch_place_outcomes(responses[cursor:cursor + 1]))
            cursor += 1
        self._resolve_places(batch, singles, parse_place_order_outcomes(responses[cursor:]))

    def _cancel_msgs(self, order_ids: Iterable[int]) -> List[Any]:
        ids = list(order_ids)
        return [batch_cancel_orders_msg(self._sender.wallet.address, ids)] if ids else []

    def _resolve_cancels(self, batch: _Pending, responses: List[bytes]) -> None:
        outcome = parse_batch_cancel_outcome(responses)
        cancelled = set(outcome.cancelled_ids) if outcome else set()
        gone = set(outcome.gone_ids) if outcome else set()
        for order_id, futures in batch.cancels.items():
            if order_id in cancelled:
                result = CancelOutcome.CANCELLED
            elif order_id in gone:
                result = CancelOutcome.GONE
            else:
                result = CancelOutcome.REJECTED
            self._resolve_cancel(order_id, futures, result)

    @staticmethod
    def _resolve_cancel(order_id: int, futures: List[asyncio.Future], outcome: CancelOutcome) -> None:
        for future in futures:
            if not future.done():
                future.set_result(CancelledOrder(order_id=order_id, outcome=outcome))

    @staticmethod
    def _resolve_places(batch: _Pending, indexes: List[int], outcomes: List[PlaceOrderOutcome]) -> None:
        for position, index in enumerate(indexes):
            future = batch.place_futures[index]
            if future.done():
                continue
            outcome = outcomes[position] if position < len(outcomes) else None
            if outcome is None or outcome.order_id <= 0:
                future.set_exception(IOError("the chain returned no order id for a placed order"))
                continue
            future.set_result(PlacedOrder(order_id=outcome.order_id, status=outcome.status, filled=outcome.filled))

    @classmethod
    def _drop_missing_cancels(cls, batch: _Pending, error: Exception) -> Optional[_Pending]:
        missing = set(error.missing_order_ids) if isinstance(error, ChainTxError) else set()
        gone = missing & set(batch.cancels)
        if not gone:
            return None
        for order_id in gone:
            cls._resolve_cancel(order_id, batch.cancels[order_id], CancelOutcome.GONE)
        return _Pending(
            places=batch.places,
            place_futures=batch.place_futures,
            cancels={order_id: futures for order_id, futures in batch.cancels.items() if order_id not in gone},
        )

    @staticmethod
    def _split(batch: _Pending) -> List[_Pending]:
        singles = [
            _Pending(cancels={order_id: futures}) for order_id, futures in batch.cancels.items()
        ]
        singles.extend(
            _Pending(places=[request], place_futures=[future])
            for request, future in zip(batch.places, batch.place_futures)
        )
        return singles

    @staticmethod
    def _fail_all(batch: _Pending, error: BaseException) -> None:
        futures = list(batch.place_futures)
        for cancel_futures in batch.cancels.values():
            futures.extend(cancel_futures)
        for future in futures:
            if not future.done():
                future.set_exception(error)
