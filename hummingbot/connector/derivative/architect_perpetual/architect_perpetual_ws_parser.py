from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.core.data_type.common import TradeType


@dataclass
class WsOrderBookDiff:
    trading_pair: str
    update_id: int
    bids: List[Tuple[Decimal, Decimal]]
    asks: List[Tuple[Decimal, Decimal]]
    timestamp: float


@dataclass
class WsTrade:
    trading_pair: str
    trade_id: str
    price: Decimal
    amount: Decimal
    trade_type: TradeType
    timestamp: float


def _to_decimal_tuples(levels: List[List[Any]]) -> List[Tuple[Decimal, Decimal]]:
    return [(Decimal(str(p)), Decimal(str(a))) for p, a in levels]


def parse_depth_update_message(raw: Dict[str, Any], trading_pair: str) -> Optional[WsOrderBookDiff]:
    """Parse a Binance-style depthUpdate event.

    Expected fields (best-effort):
      e: depthUpdate
      u: final update id
      b: bids [[price, amount], ...]
      a: asks [[price, amount], ...]
      E: event time (ms)
    """
    if raw.get("e") != "depthUpdate":
        return None

    update_id = int(raw.get("u") or raw.get("lastUpdateId") or 0)
    bids = _to_decimal_tuples(raw.get("b") or raw.get("bids") or [])
    asks = _to_decimal_tuples(raw.get("a") or raw.get("asks") or [])

    event_time_ms = raw.get("E") or raw.get("eventTime")
    ts = (float(event_time_ms) / 1e3) if event_time_ms is not None else 0.0

    return WsOrderBookDiff(
        trading_pair=trading_pair,
        update_id=update_id,
        bids=bids,
        asks=asks,
        timestamp=ts,
    )


def parse_trade_message(raw: Dict[str, Any], trading_pair: str) -> Optional[WsTrade]:
    """Parse a Binance-style trade event.

    Expected fields (best-effort):
      e: trade
      t: trade id
      p: price
      q: qty
      T: trade time (ms)
      m: is buyer the market maker
    """
    if raw.get("e") != "trade":
        return None

    trade_id = str(raw.get("t") or raw.get("tradeId") or "")
    price = Decimal(str(raw.get("p") or raw.get("price") or "0"))
    qty = Decimal(str(raw.get("q") or raw.get("qty") or raw.get("quantity") or "0"))
    trade_time_ms = raw.get("T") or raw.get("tradeTime")
    ts = (float(trade_time_ms) / 1e3) if trade_time_ms is not None else 0.0

    # Binance semantics: m=True means buyer is maker => trade was a SELL (taker sold)
    is_buyer_maker = bool(raw.get("m"))
    trade_type = TradeType.SELL if is_buyer_maker else TradeType.BUY

    return WsTrade(
        trading_pair=trading_pair,
        trade_id=trade_id,
        price=price,
        amount=qty,
        trade_type=trade_type,
        timestamp=ts,
    )


def build_ws_subscribe_request(streams: List[str], request_id: int = 1) -> Dict[str, Any]:
    """Build a Binance-style SUBSCRIBE request."""
    return {"method": "SUBSCRIBE", "params": streams, "id": request_id}
