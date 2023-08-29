import gzip
import json
import os
import platform
from collections import namedtuple
from hashlib import md5
from typing import Any, Callable, Dict, Optional, Tuple

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.utils.tracking_nonce import NonceCreator, get_tracking_nonce
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSResponse
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase

TradeFillOrderDetails = namedtuple("TradeFillOrderDetails", "market exchange_trade_id symbol")


def build_api_factory(throttler: AsyncThrottlerBase) -> WebAssistantsFactory:
    throttler = throttler or AsyncThrottler(rate_limits=[])
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def split_hb_trading_pair(trading_pair: str) -> Tuple[str, str]:
    base, quote = trading_pair.split("-")
    return base, quote


def combine_to_hb_trading_pair(base: str, quote: str) -> str:
    trading_pair = f"{base}-{quote}"
    return trading_pair


def validate_trading_pair(trading_pair: str) -> bool:
    valid = False
    if "-" in trading_pair and len(trading_pair.split("-")) == 2:
        valid = True
    return valid


def _bot_instance_id() -> str:
    return md5(f"{platform.uname()}_pid:{os.getpid()}_ppid:{os.getppid()}".encode("utf-8")).hexdigest()


def get_new_client_order_id(
    is_buy: bool, trading_pair: str, hbot_order_id_prefix: str = "", max_id_len: Optional[int] = None
) -> str:
    """
    Creates a client order id for a new order

    Note: If the need for much shorter IDs arises, an option is to concatenate the host name, the PID,
    and the nonce, and hash the result.

    :param is_buy: True if the order is a buy order, False otherwise
    :param trading_pair: the trading pair the order will be operating with
    :param hbot_order_id_prefix: The hummingbot-specific identifier for the given exchange
    :param max_id_len: The maximum length of the ID string.
    :return: an identifier for the new order to be used in the client
    """
    side = "B" if is_buy else "S"
    symbols = split_hb_trading_pair(trading_pair)
    base = symbols[0].upper()
    quote = symbols[1].upper()
    base_str = f"{base[0]}{base[-1]}"
    quote_str = f"{quote[0]}{quote[-1]}"
    client_instance_id = _bot_instance_id()
    ts_hex = hex(get_tracking_nonce())[2:]
    client_order_id = f"{hbot_order_id_prefix}{side}{base_str}{quote_str}{ts_hex}{client_instance_id}"

    if max_id_len is not None:
        id_prefix = f"{hbot_order_id_prefix}{side}{base_str}{quote_str}"
        suffix_max_length = max_id_len - len(id_prefix)
        if suffix_max_length < len(ts_hex):
            id_suffix = md5(f"{ts_hex}{client_instance_id}".encode()).hexdigest()
            client_order_id = f"{id_prefix}{id_suffix[:suffix_max_length]}"
        else:
            client_order_id = client_order_id[:max_id_len]
    return client_order_id


def get_new_numeric_client_order_id(nonce_creator: NonceCreator, max_id_bit_count: Optional[int] = None) -> int:
    hexa_hash = _bot_instance_id()
    host_part = int(hexa_hash, 16)
    client_order_id = int(f"{host_part}{nonce_creator.get_tracking_nonce()}")
    if max_id_bit_count:
        max_int = 2 ** max_id_bit_count - 1
        client_order_id &= max_int
    return client_order_id


class TimeSynchronizerRESTPreProcessor(RESTPreProcessorBase):
    """
    This pre processor is intended to be used in those connectors that require synchronization with the server time
    to accept API requests. It ensures the synchronizer has at least one server time sample before being used.
    """

    def __init__(self, synchronizer: TimeSynchronizer, time_provider: Callable):
        super().__init__()
        self._synchronizer = synchronizer
        self._time_provider = time_provider

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        await self._synchronizer.update_server_time_if_not_initialized(time_provider=self._time_provider())
        return request


class GZipCompressionWSPostProcessor(WSPostProcessorBase):
    """
    Performs the necessary response processing from both public and private websocket streams.
    """

    async def post_process(self, response: WSResponse) -> WSResponse:
        if not isinstance(response.data, bytes):
            # Unlike Market WebSocket, the return data of Account and Order Websocket are not compressed by GZIP.
            return response
        encoded_msg: bytes = gzip.decompress(response.data)
        msg: Dict[str, Any] = json.loads(encoded_msg.decode("utf-8"))

        return WSResponse(data=msg)
