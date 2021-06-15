import websockets
from web3 import Web3
from web3.exceptions import BlockNotFound
from websockets.exceptions import ConnectionClosed
import logging
import ujson
import asyncio

from hexbytes import HexBytes
from web3.datastructures import AttributeDict
from cachetools import TTLCache

from typing import Optional, Dict, AsyncIterable, Any

from contextlib import suppress

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.wallet.ethereum.watcher.base_watcher import BaseWatcher
from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import NewBlocksWatcherEvent


class WSNewBlocksWatcher(BaseWatcher):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    def __init__(self, w3: Web3, websocket_url):
        super().__init__(w3)
        self._network_on = False
        self._nonce: int = 0
        self._current_block_number: int = -1
        self._websocket_url = websocket_url
        self._node_address = None
        self._client: Optional[websockets.WebSocketClientProtocol] = None
        self._fetch_new_blocks_task: Optional[asyncio.Task] = None
        self._block_cache = TTLCache(maxsize=10, ttl=120)

    _nbw_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._nbw_logger is None:
            cls._nbw_logger = logging.getLogger(__name__)
        return cls._nbw_logger

    @property
    def block_number(self) -> int:
        return self._current_block_number

    @property
    def block_cache(self) -> Dict[HexBytes, AttributeDict]:
        cache_dict: Dict[HexBytes, AttributeDict] = dict([(key, self._block_cache[key])
                                                          for key in self._block_cache.keys()])
        return cache_dict

    async def start_network(self):
        if self._fetch_new_blocks_task is not None:
            await self.stop_network()
        else:
            try:
                self._current_block_number = await self.call_async(getattr, self._w3.eth, "blockNumber")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Error fetching newest Ethereum block number.",
                                      app_warning_msg="Error fetching newest Ethereum block number. "
                                                      "Check Ethereum node connection",
                                      exc_info=True)
            await self.connect()
            await self.subscribe(["newHeads"])
            self._fetch_new_blocks_task: asyncio.Task = safe_ensure_future(self.fetch_new_blocks_loop())
            self._network_on = True

    async def stop_network(self):
        if self._fetch_new_blocks_task is not None:
            await self.disconnect()
            self._fetch_new_blocks_task.cancel()
            self._fetch_new_blocks_task = None
            self._network_on = False

    async def connect(self):
        try:
            self._client = await websockets.connect(uri=self._websocket_url)
            return self._client
        except Exception as e:
            self.logger().network(f"ERROR in connection: {e}")

    async def disconnect(self):
        try:
            await self._client.close()
            self._client = None
        except Exception as e:
            self.logger().network(f"ERROR in disconnection: {e}")

    async def _send(self, emit_data) -> int:
        self._nonce += 1
        emit_data["id"] = self._nonce
        await self._client.send(ujson.dumps(emit_data))
        return self._nonce

    async def subscribe(self, params) -> bool:
        emit_data = {
            "method": "eth_subscribe",
            "params": params
        }
        nonce = await self._send(emit_data)
        raw_message = await self._client.recv()
        if raw_message is not None:
            resp = ujson.loads(raw_message)
            if resp.get("id", None) == nonce:
                self._node_address = resp.get("result")
                return True
        return False

    async def _messages(self) -> AsyncIterable[Any]:
        try:
            while True:
                try:
                    raw_msg_str: str = await asyncio.wait_for(self._client.recv(), self.MESSAGE_TIMEOUT)
                    yield raw_msg_str
                except asyncio.TimeoutError:
                    pong_waiter = await self._client.ping()
                    await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await self.disconnect()
            # Reconnect and subscribe in case a disconnect happens
            await self.connect()
            await self.subscribe(["newHeads"])

    async def fetch_new_blocks_loop(self):
        while True:
            try:
                async for raw_message in self._messages():
                    message_json = ujson.loads(raw_message) if raw_message is not None else None
                    if message_json.get("method", None) == "eth_subscription":
                        subscription_result_params = message_json.get("params", None)
                        incoming_block = subscription_result_params.get("result", None) \
                            if subscription_result_params is not None else None
                        if incoming_block is not None:
                            with suppress(BlockNotFound):
                                new_block: AttributeDict = await self.call_async(self._w3.eth.getBlock,
                                                                                 incoming_block.get("hash"), True)
                                self._current_block_number = new_block.get("number")
                                self._block_cache[new_block.get("hash")] = new_block
                                self.trigger_event(NewBlocksWatcherEvent.NewBlocks, [new_block])
            except asyncio.TimeoutError:
                self.logger().network("Timed out fetching new block.", exc_info=True,
                                      app_warning_msg="Timed out fetching new block. "
                                                      "Check wallet network connection")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(f"Error fetching new block: {e}", exc_info=True,
                                      app_warning_msg="Error fetching new block. "
                                                      "Check wallet network connection")
                await asyncio.sleep(30.0)

    async def get_timestamp_for_block(self, block_hash: HexBytes, max_tries: Optional[int] = 10) -> int:
        counter = 0
        block: AttributeDict = None
        if block_hash in self._block_cache.keys():
            block = self._block_cache.get(block_hash)
        else:
            while block is None:
                if counter == max_tries:
                    raise ValueError(f"Block hash {block_hash.hex()} does not exist.")
                counter += 1
                block = self._block_cache.get(block_hash)
                await asyncio.sleep(0.5)
        return block.get("timestamp")
