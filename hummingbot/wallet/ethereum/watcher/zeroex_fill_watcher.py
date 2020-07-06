#!/usr/bin/env python

import asyncio
from hexbytes import HexBytes
from decimal import Decimal
from eth_abi.codec import (
    ABICodec,
)
from eth_abi.registry import registry
from eth_bloom import BloomFilter
from eth_utils import remove_0x_prefix
import functools
import logging
from typing import (
    Callable,
    List,
    Dict,
    Set,
    Optional
)
from os.path import join, realpath
import ujson
from web3 import Web3
from web3.datastructures import AttributeDict
from web3._utils.events import get_event_data

from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import (
    NewBlocksWatcherEvent,
    ZeroExEvent,
    ZeroExFillEvent
)
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import safe_ensure_future
from .base_watcher import BaseWatcher
# from .new_blocks_watcher import NewBlocksWatcher
from .websocket_watcher import WSNewBlocksWatcher

with open(realpath(join(__file__, "../../zero_ex/zero_ex_exchange_abi_v3.json"))) as exchange_abi_json:
    exchange_abi: List[any] = ujson.load(exchange_abi_json)

FILL_EVENT = "Fill"
FILL_EVENT_TOPIC = bytes.fromhex("6869791f0a34781b29882982cc39e882768cf2c96995c2a110c577c53bc932d5")


class ZeroExFillWatcher(BaseWatcher):
    _zfew_logger: Optional[HummingbotLogger] = None
    _watch_order_hashes: Dict[str, Callable[[ZeroExFillEvent], None]] = {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._zfew_logger is None:
            cls._zfew_logger = logging.getLogger(__name__)
        return cls._zfew_logger

    def __init__(self,
                 w3: Web3,
                 blocks_watcher: WSNewBlocksWatcher):
        super().__init__(w3)
        self._blocks_watcher: WSNewBlocksWatcher = blocks_watcher
        self._poll_fill_logs_task: asyncio.Task = None
        self._event_forwarder: EventForwarder = EventForwarder(self.did_receive_new_blocks)
        self._new_blocks_queue: asyncio.Queue = asyncio.Queue()
        self._event_cache: Set[HexBytes] = set()
        for abi in exchange_abi:
            if "name" in abi and abi["name"] == FILL_EVENT:
                self._event_abi = abi

    async def start_network(self):
        # This should not watch by default unless queued by a market
        pass

    async def start_watching(self):
        if self._poll_fill_logs_task is not None:
            await self.stop_network()
        self._blocks_watcher.add_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)
        self._poll_fill_logs_task = safe_ensure_future(self.poll_zeroex_logs_loop())

    async def stop_network(self):
        if self._poll_fill_logs_task is not None:
            self._poll_fill_logs_task.cancel()
            self._poll_fill_logs_task = None
        self._blocks_watcher.remove_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)

    async def watch_order_hash(self, order_hash_hex: str, callback: Callable[[ZeroExFillEvent], None]):
        self._watch_order_hashes[remove_0x_prefix(order_hash_hex)] = callback
        if self._poll_fill_logs_task is None:
            await self.start_watching()

    async def unwatch_order_hash(self, order_hash_hex: str):
        order_hash = remove_0x_prefix(order_hash_hex)
        if order_hash in self._watch_order_hashes:
            del self._watch_order_hashes[order_hash]
            if len(self._watch_order_hashes) == 0:
                await self.stop_network()

    def did_receive_new_blocks(self, new_blocks: List[AttributeDict]):
        self._new_blocks_queue.put_nowait(new_blocks)

    async def poll_zeroex_logs_loop(self):
        while True:
            try:
                new_blocks: List[AttributeDict] = await self._new_blocks_queue.get()

                for block in new_blocks:
                    block_bloom_filter = BloomFilter(int.from_bytes(block["logsBloom"], byteorder='big'))
                    if FILL_EVENT_TOPIC in block_bloom_filter:
                        # Potentially a Fill for an order hash we are interested in
                        order_hashes: List[str] = []
                        for order_hash in self._watch_order_hashes:
                            if bytes.fromhex(order_hash) in block_bloom_filter:
                                order_hashes.append("0x" + order_hash)
                        if len(order_hashes) > 0:
                            fill_entries = await self._get_logs({
                                'topics': [
                                    "0x6869791f0a34781b29882982cc39e882768cf2c96995c2a110c577c53bc932d5",
                                    None,
                                    None,
                                    order_hashes
                                ],
                                'blockhash': block["hash"].hex()
                            })

                            for fill_entry in fill_entries:
                                event_data: AttributeDict = get_event_data(ABICodec(registry), self._event_abi, fill_entry)
                                event_data_tx_hash: HexBytes = event_data["transactionHash"]
                                # Skip any duplicates
                                if event_data_tx_hash not in self._event_cache:
                                    await self._handle_event_data(event_data)

                            # Mark all of these as processed now, since each tx may contain multiple Fill logs
                            for fill_entry in fill_entries:
                                event_data_tx_hash: HexBytes = fill_entry["transactionHash"]
                                if event_data_tx_hash not in self._event_cache:
                                    self._event_cache.add(event_data_tx_hash)

            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                continue
            except Exception:
                self.logger().network("Unknown error trying to fetch new events for ZeroEx fills.", exc_info=True,
                                      app_warning_msg="Unknown error trying to fetch new events for ZeroEx fills. "
                                                      "Check wallet network connection")

    async def _get_logs(self,
                        event_filter_params: Dict[str, any],
                        max_tries: Optional[int] = 30) -> List[Dict[str, any]]:
        async_scheduler: AsyncCallScheduler = AsyncCallScheduler.shared_instance()
        count: int = 0
        logs = []
        while True:
            try:
                count += 1
                if count > max_tries:
                    self.logger().debug(
                        f"Error fetching logs from block with filters: '{event_filter_params}'."
                    )
                    break
                logs = await async_scheduler.call_async(
                    functools.partial(self._w3.eth.getLogs, event_filter_params)
                )
                break
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().debug(f"Block not found with filters: '{event_filter_params}'. Retrying...")
                await asyncio.sleep(0.5)
        return logs

    async def _handle_event_data(self, event_data: AttributeDict):
        timestamp: float = float(await self._blocks_watcher.get_timestamp_for_block(event_data["blockHash"]))
        tx_hash: str = event_data["transactionHash"].hex()
        event_args: AttributeDict = event_data["args"]
        order_hash: str = event_args["orderHash"].hex()
        order_hash_hex: str = "0x" + order_hash

        if order_hash in self._watch_order_hashes:
            fill_event = ZeroExFillEvent(timestamp,
                                         tx_hash,
                                         event_args["makerAddress"],
                                         event_args["feeRecipientAddress"],
                                         "0x" + event_args["makerAssetData"].hex(),
                                         "0x" + event_args["takerAssetData"].hex(),
                                         "0x" + event_args["makerFeeAssetData"].hex(),
                                         "0x" + event_args["takerFeeAssetData"].hex(),
                                         order_hash_hex,
                                         event_args["takerAddress"],
                                         event_args["senderAddress"],
                                         Decimal(event_args["makerAssetFilledAmount"]),
                                         Decimal(event_args["takerAssetFilledAmount"]),
                                         Decimal(event_args["makerFeePaid"]),
                                         Decimal(event_args["takerFeePaid"]),
                                         Decimal(event_args["protocolFeePaid"]))

            self.trigger_event(ZeroExEvent.Fill, fill_event)

            # Trigger callback
            self._watch_order_hashes[order_hash](fill_event)
            # Unwatch it
            await self.unwatch_order_hash(order_hash)
