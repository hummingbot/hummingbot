import asyncio
from collections import OrderedDict
import cytoolz
import functools
from hexbytes import HexBytes
from eth_bloom import BloomFilter
import logging
from typing import (
    Dict,
    List,
    Optional,
    Set
)
from web3 import Web3
from web3.datastructures import AttributeDict
from web3._utils.contracts import find_matching_event_abi
from web3._utils.events import get_event_data
from web3._utils.filters import construct_event_filter_params
from eth_abi.codec import (
    ABICodec,
)
from eth_abi.registry import registry

from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger

DEFAULT_WINDOW_SIZE = 100


class ContractEventLogger:
    _cel_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cel_logger is None:
            cls._cel_logger = logging.getLogger(__name__)
        return cls._cel_logger

    def __init__(self,
                 w3: Web3,
                 address: str,
                 contract_abi: List[Dict[str, any]],
                 block_events_window_size: Optional[int] = DEFAULT_WINDOW_SIZE):

        super().__init__()
        self._w3: Web3 = w3
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._block_events_window_size = block_events_window_size
        self._address: str = address
        self._contract_abi: List[Dict[str, any]] = contract_abi
        self._event_abi_map: Dict[str, Dict[str, any]] = {}
        self._event_cache: Set[HexBytes] = set()
        self._block_events: OrderedDict = OrderedDict()

    @property
    def address(self) -> str:
        return self._address

    @property
    def contract_abi(self) -> List[Dict[str, any]]:
        return self._contract_abi

    async def get_new_entries_from_logs(self,
                                        event_name: str,
                                        blocks: List[AttributeDict]) -> List[AttributeDict]:
        event_abi: Dict[str, any] = self._event_abi_map.get(event_name, None)
        if event_abi is None:
            event_abi = find_matching_event_abi(self._contract_abi, event_name=event_name)
            self._event_abi_map[event_name] = event_abi

        _, event_filter_params = construct_event_filter_params(event_abi,
                                                               contract_address=self._address,
                                                               abi_codec=ABICodec(registry))
        tasks = []
        for block in blocks:
            block_bloom_filter = BloomFilter(int.from_bytes(block["logsBloom"], byteorder='big'))
            check_block = True
            for topic in event_filter_params["topics"]:
                if not bytes.fromhex(topic.lstrip("0x")) in block_bloom_filter:
                    check_block = False
                    break
            if check_block:
                event_filter_params["blockHash"] = block["hash"].hex()
                tasks.append(self._get_logs(event_filter_params))

        new_entries = []
        if len(tasks) > 0:
            raw_logs = await safe_gather(*tasks, return_exceptions=True)
            logs: List[any] = list(cytoolz.concat(raw_logs))
            for log in logs:
                event_data: AttributeDict = get_event_data(ABICodec(registry), event_abi, log)
                event_data_block_number: int = event_data["blockNumber"]
                event_data_tx_hash: HexBytes = event_data["transactionHash"]
                if event_data_tx_hash not in self._event_cache:
                    if event_data_block_number not in self._block_events:
                        self._block_events[event_data_block_number] = [event_data_tx_hash]
                    else:
                        self._block_events[event_data_block_number].append(event_data_tx_hash)
                    self._event_cache.add(event_data_tx_hash)
                    new_entries.append(event_data)
                else:
                    self.logger().debug(
                        f"Duplicate event transaction hash found - '{event_data_tx_hash.hex()}'."
                    )

            while len(self._block_events) > self._block_events_window_size:
                tx_hashes: List[HexBytes] = self._block_events.popitem(last=False)[1]
                for tx_hash in tx_hashes:
                    self._event_cache.remove(tx_hash)
        return new_entries

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
