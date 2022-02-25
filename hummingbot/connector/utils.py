import base64
from collections import namedtuple
from typing import Callable, Dict, Optional, Tuple

from zero_ex.order_utils import Order as ZeroExOrder

from hummingbot.connector.time_synchronizer import TimeSynchronizer
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


class TimeSynchronizerRESTPreProcessor(RESTPreProcessorBase):

    def __init__(self, synchronizer: TimeSynchronizer, time_provider: Callable):
        super().__init__()
        self._synchronizer = synchronizer
        self._time_provider = time_provider

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        await self._synchronizer.update_server_time_if_not_initialized(time_provider=self._time_provider())
        return request
