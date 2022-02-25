import base64
import os
import socket
from collections import namedtuple
from hashlib import md5
from typing import Callable, Dict, Optional, Tuple

from zero_ex.order_utils import Order as ZeroExOrder

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce_low_res
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

TradeFillOrderDetails = namedtuple("TradeFillOrderDetails", "market exchange_trade_id symbol")


def zrx_order_to_json(order: Optional[ZeroExOrder]) -> Optional[Dict[str, any]]:
    if order is None:
        return None

    retval: Dict[str, any] = {}
    for key, value in order.items():
        if not isinstance(value, bytes):
            retval[key] = value
        else:
            retval[f"__binary__{key}"] = base64.b64encode(value).decode("utf8")
    return retval


def json_to_zrx_order(data: Optional[Dict[str, any]]) -> Optional[ZeroExOrder]:
    if data is None:
        return None

    intermediate: Dict[str, any] = {}
    for key, value in data.items():
        if key.startswith("__binary__"):
            target_key = key.replace("__binary__", "")
            intermediate[target_key] = base64.b64decode(value)
        else:
            intermediate[key] = value
    return ZeroExOrder(intermediate)


def build_api_factory() -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory()
    return api_factory


def split_hb_trading_pair(trading_pair: str) -> Tuple[str, str]:
    base, quote = trading_pair.split("-")
    return base, quote


def combine_to_hb_trading_pair(base: str, quote: str) -> str:
    trading_pair = f"{base}-{quote}"
    return trading_pair


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
    client_instance_id = md5(f"{socket.gethostname()}{os.getpid()}".encode("utf-8")).hexdigest()
    ts_hex = hex(get_tracking_nonce_low_res())[2:]
    client_order_id = f"{hbot_order_id_prefix}{side}{base_str}{quote_str}{ts_hex}{client_instance_id}"
    if max_id_len is not None:
        client_order_id = client_order_id[:max_id_len]
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
