import functools
import re
import time
import typing
import uuid

from typing import Optional

from hummingbot.core.event.events import OrderType, TradeType
from .client.asyncio import AsyncIdexClient


EXCHANGE_NAME = "idex"


def no_arg_cache(_f=None, *, for_seconds=30):
    def decorator(f):
        @functools.wraps(f)
        async def wrapper():
            now = time.time()
            result, created = getattr(f, "_result", (None, None))
            if not result or (created + for_seconds) < now:
                result = await f()
                setattr(f, "_result", (result, now))
            return result
        return wrapper
    if _f:
        return decorator(_f)
    return decorator


@no_arg_cache
async def get_assets() -> typing.List[str]:
    return [asset.symbol for asset in (await AsyncIdexClient().public.get_assets())]


@no_arg_cache
async def get_markets() -> typing.List[str]:
    return [item.market for item in (await AsyncIdexClient().public.get_markets())]


@no_arg_cache
async def get_trading_pair_splitter() -> typing.Pattern:
    pairs = await get_assets()
    return re.compile(rf"^(\w+)-?({'|'.join(pairs)})$")


async def to_idex_pair(pair: str) -> Optional[str]:
    pattern = await get_trading_pair_splitter()
    matcher = pattern.match(pair)
    if matcher:
        return f"{matcher.group(1)}-{matcher.group(2)}"
    return None


HB_ORDER_TYPE_MAP = {
    OrderType.MARKET: "market",
    OrderType.LIMIT: "limit",
    OrderType.LIMIT_MAKER: "limitMaker",
}


def to_idex_order_type(
        order_type: typing.Literal[
            OrderType.MARKET,
            OrderType.LIMIT,
            OrderType.LIMIT_MAKER]):
    return HB_ORDER_TYPE_MAP[order_type]


IDEX_ORDER_TYPE_MAP = {
    "market": OrderType.MARKET,
    "limit": OrderType.LIMIT,
    "limitMaker": OrderType.LIMIT_MAKER,
}


def from_idex_order_type(order_type: str):
    return IDEX_ORDER_TYPE_MAP[order_type]


IDEX_TRADE_TYPE_MAP = {
    "buy": TradeType.BUY,
    "sell": TradeType.SELL,
}


def from_idex_trade_type(side: str):
    return IDEX_TRADE_TYPE_MAP[side]


def create_id():
    return str(uuid.uuid4())
