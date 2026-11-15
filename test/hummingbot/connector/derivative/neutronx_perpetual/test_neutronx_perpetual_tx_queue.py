import asyncio
from decimal import Decimal
from test.hummingbot.connector.derivative.neutronx_perpetual.fixtures import WALLET
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock

import grpc
from neutronx_sdk import ChainTxError, OrderRequest, Side, TimeInForce
from neutronx_sdk.node import TxResult
from neutronx_sdk.proto import new

from hummingbot.connector.derivative.neutronx_perpetual.data_sources.tx_queue import CancelOutcome, OrderTxQueue


def _request(client_id: int, time_in_force: TimeInForce = TimeInForce.GTC) -> OrderRequest:
    return OrderRequest(
        pair="BTC/USDC",
        side=Side.BUY,
        price=Decimal(65000),
        quantity=Decimal("0.01"),
        leverage=Decimal(3),
        time_in_force=time_in_force,
        client_id=client_id,
    )


def _result(*responses: Any) -> TxResult:
    return TxResult(
        tx_hash="AB",
        height=10,
        gas_used=1,
        gas_wanted=1,
        raw_log="",
        events=(),
        msg_responses=tuple(r.SerializeToString() for r in responses),
    )


def _placed(*order_ids: int) -> Any:
    return new(
        "neutronx.orderbook.v1.MsgBatchPlaceOrdersResponse",
        results=[new("neutronx.orderbook.v1.MsgPlaceOrderResponse", order_id=i, status="open") for i in order_ids],
    )


class OrderTxQueueTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.sender = MagicMock()
        self.sender.wallet = WALLET
        self.sender.estimate_gas = AsyncMock(return_value=200_000)
        self.sender.send = AsyncMock()
        self.queue = OrderTxQueue(self.sender, max_places_per_tx=30, flush_interval=0.01)
        self.queue.start()

    async def asyncTearDown(self) -> None:
        await self.queue.stop()
        await super().asyncTearDown()

    def _sent_msgs(self, call: int = 0) -> List[Any]:
        return list(self.sender.send.call_args_list[call].args[0])

    async def test_places_and_cancels_share_one_tx(self):
        cancel_response = new(
            "neutronx.orderbook.v1.MsgBatchCancelOrdersResponse", cancelled_ids=[1], gone_ids=[2], rejected_ids=[3]
        )
        self.sender.send.return_value = _result(cancel_response, _placed(71, 72))
        results = await asyncio.gather(
            self.queue.place(_request(11)),
            self.queue.place(_request(12)),
            self.queue.cancel(1),
            self.queue.cancel(2),
            self.queue.cancel(3),
            self.queue.cancel(1),
        )
        self.assertEqual([71, 72], [r.order_id for r in results[:2]])
        outcomes = [r.outcome for r in results[2:]]
        self.assertEqual(
            [CancelOutcome.CANCELLED, CancelOutcome.GONE, CancelOutcome.REJECTED, CancelOutcome.CANCELLED], outcomes
        )
        self.sender.send.assert_awaited_once()
        msgs = self._sent_msgs()
        self.assertEqual("neutronx.orderbook.v1.MsgBatchCancelOrders", msgs[0].DESCRIPTOR.full_name)
        self.assertEqual([1, 2, 3], list(msgs[0].order_ids))
        self.assertEqual(2, len(msgs[1].orders))
        self.assertEqual(200_000, self.sender.send.call_args.kwargs["gas_limit"])

    async def test_ioc_orders_leave_the_batch_messages_to_their_own_tx(self):
        single = new("neutronx.orderbook.v1.MsgPlaceOrderResponse", order_id=81, status="filled", filled="10000000000000000")
        cancel_response = new("neutronx.orderbook.v1.MsgBatchCancelOrdersResponse", cancelled_ids=[4])

        async def send(msgs, gas_limit):
            names = [msg.DESCRIPTOR.full_name for msg in msgs]
            if names == ["neutronx.orderbook.v1.MsgPlaceOrder"]:
                return _result(single)
            return _result(cancel_response, _placed(80))

        self.sender.send.side_effect = send
        gtc, ioc, cancelled = await asyncio.gather(
            self.queue.place(_request(11)),
            self.queue.place(_request(12, TimeInForce.IOC)),
            self.queue.cancel(4),
        )
        self.assertEqual((80, 81, Decimal("0.01")), (gtc.order_id, ioc.order_id, ioc.filled))
        self.assertIs(CancelOutcome.CANCELLED, cancelled.outcome)
        txs = sorted([msg.DESCRIPTOR.full_name for msg in call.args[0]] for call in self.sender.send.call_args_list)
        self.assertEqual(
            [
                ["neutronx.orderbook.v1.MsgBatchCancelOrders", "neutronx.orderbook.v1.MsgBatchPlaceOrders"],
                ["neutronx.orderbook.v1.MsgPlaceOrder"],
            ],
            txs,
        )
        ioc_tx = next(call.args[0] for call in self.sender.send.call_args_list if len(call.args[0]) == 1)
        self.assertEqual("IOC", ioc_tx[0].time_in_force)

    async def test_a_refused_ioc_tx_does_not_fail_the_batch_beside_it(self):
        async def send(msgs, gas_limit):
            if msgs[0].DESCRIPTOR.full_name == "neutronx.orderbook.v1.MsgPlaceOrder":
                raise ChainTxError(5, "reduce-only order requires open position")
            return _result(_placed(90))

        self.sender.send.side_effect = send
        gtc, ioc = await asyncio.gather(
            self.queue.place(_request(11)), self.queue.place(_request(12, TimeInForce.IOC)), return_exceptions=True
        )
        self.assertEqual(90, gtc.order_id)
        self.assertIsInstance(ioc, ChainTxError)

    async def test_ioc_alone_is_a_single_place(self):
        self.sender.send.return_value = _result(new("neutronx.orderbook.v1.MsgPlaceOrderResponse", order_id=90))
        placed = await self.queue.place(_request(13, TimeInForce.IOC))
        self.assertEqual(90, placed.order_id)
        self.assertEqual(["neutronx.orderbook.v1.MsgPlaceOrder"], [m.DESCRIPTOR.full_name for m in self._sent_msgs()])

    async def test_places_respect_the_per_tx_cap(self):
        queue = OrderTxQueue(self.sender, max_places_per_tx=2, flush_interval=0.01)
        queue.start()
        self.sender.send.side_effect = [_result(_placed(1, 2)), _result(_placed(3))]
        results = await asyncio.gather(*(queue.place(_request(i)) for i in (11, 12, 13)))
        await queue.stop()
        self.assertEqual([1, 2, 3], [r.order_id for r in results])
        self.assertEqual(2, self.sender.send.await_count)

    async def test_batches_fit_the_prefill_floor_under_the_gas_ceiling(self):
        queue = OrderTxQueue(self.sender, max_places_per_tx=50, gas_ceiling=300_000, flush_interval=0.01)
        queue.start()
        self.sender.send.side_effect = [_result(_placed(1, 2)), _result(_placed(3))]
        results = await asyncio.gather(*(queue.place(_request(i)) for i in (11, 12, 13)))
        await queue.stop()
        self.assertEqual([1, 2, 3], [r.order_id for r in results])
        self.assertEqual([2, 1], [len(call.args[0][0].orders) for call in self.sender.send.call_args_list])

    async def test_cancels_by_id_take_their_chain_charge_from_the_batch_room(self):
        queue = OrderTxQueue(self.sender, max_places_per_tx=50, gas_ceiling=320_000, flush_interval=0.01)
        queue.start()
        cancel_response = new("neutronx.orderbook.v1.MsgBatchCancelOrdersResponse", cancelled_ids=[1, 2])
        self.sender.send.side_effect = [_result(cancel_response, _placed(1)), _result(_placed(2, 3))]
        results = await asyncio.gather(
            queue.cancel(1), queue.cancel(2), *(queue.place(_request(i)) for i in (11, 12, 13))
        )
        await queue.stop()
        self.assertEqual([1, 2, 3], [r.order_id for r in results[2:]])
        first, second = (call.args[0] for call in self.sender.send.call_args_list)
        self.assertEqual(([1, 2], 1), (list(first[0].order_ids), len(first[1].orders)))
        self.assertEqual(2, len(second[0].orders))

    async def test_a_tiny_ceiling_still_sends_one_order(self):
        queue = OrderTxQueue(self.sender, gas_ceiling=100_000, flush_interval=0.01)
        queue.start()
        self.sender.send.return_value = _result(_placed(7))
        placed = await queue.place(_request(11))
        await queue.stop()
        self.assertEqual(7, placed.order_id)

    async def test_refused_batch_is_split_into_single_orders(self):
        error = grpc.aio.AioRpcError(grpc.StatusCode.UNKNOWN, grpc.aio.Metadata(), grpc.aio.Metadata(), "bad order")
        self.sender.estimate_gas.side_effect = [error, 100_000, ChainTxError(28, "collateral insufficient")]
        self.sender.send.return_value = _result(_placed(9))
        good, bad = await asyncio.gather(
            self.queue.place(_request(11)), self.queue.place(_request(12)), return_exceptions=True
        )
        self.assertEqual(9, good.order_id)
        self.assertIsInstance(bad, ChainTxError)

    async def test_cancel_of_a_gone_order_leaves_the_rest_of_the_batch_together(self):
        missing = ChainTxError(10, f"ante cancel {WALLET.address} order 2: order not found", tx_hash="1A")
        cancel_response = new("neutronx.orderbook.v1.MsgBatchCancelOrdersResponse", cancelled_ids=[1, 3])
        self.sender.send.side_effect = [missing, _result(cancel_response, _placed(71))]
        placed, first, gone, third = await asyncio.gather(
            self.queue.place(_request(11)), self.queue.cancel(1), self.queue.cancel(2), self.queue.cancel(3)
        )
        self.assertEqual(71, placed.order_id)
        self.assertEqual(
            [CancelOutcome.CANCELLED, CancelOutcome.GONE, CancelOutcome.CANCELLED],
            [first.outcome, gone.outcome, third.outcome],
        )
        self.assertEqual(2, self.sender.send.await_count)
        retry = self._sent_msgs(1)
        self.assertEqual([1, 3], list(retry[0].order_ids))
        self.assertEqual(1, len(retry[1].orders))

    async def test_lone_cancel_of_a_gone_order_is_gone_not_an_error(self):
        self.sender.send.side_effect = ChainTxError(10, f"ante cancel {WALLET.address} order 5: order not found")
        cancelled = await self.queue.cancel(5)
        self.assertIs(CancelOutcome.GONE, cancelled.outcome)
        self.sender.send.assert_awaited_once()

    async def test_unrelated_missing_order_still_splits_the_batch(self):
        missing = ChainTxError(10, f"ante cancel {WALLET.address} order 99: order not found")
        cancel_response = new("neutronx.orderbook.v1.MsgBatchCancelOrdersResponse", cancelled_ids=[7])
        self.sender.send.side_effect = [missing, _result(cancel_response), _result(_placed(72))]
        cancelled, placed = await asyncio.gather(self.queue.cancel(7), self.queue.place(_request(11)))
        self.assertEqual((CancelOutcome.CANCELLED, 72), (cancelled.outcome, placed.order_id))
        self.assertEqual(3, self.sender.send.await_count)

    async def test_missing_order_id_fails_that_order(self):
        self.sender.send.return_value = _result(_placed(0))
        with self.assertRaises(IOError):
            await self.queue.place(_request(11))

    async def test_unexpected_errors_fail_the_whole_batch(self):
        self.sender.send.side_effect = RuntimeError("node down")
        results = await asyncio.gather(
            self.queue.place(_request(11)), self.queue.cancel(5), return_exceptions=True
        )
        self.assertTrue(all(isinstance(r, RuntimeError) for r in results))

    async def test_stopped_queue_refuses_work(self):
        await self.queue.stop()
        with self.assertRaises(ConnectionError):
            await self.queue.place(_request(11))
        self.assertFalse(self.queue.running)
