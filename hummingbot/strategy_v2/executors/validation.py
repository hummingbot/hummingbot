"""
Shared validation helpers for the strategy V2 executor configs.

Executor configs validate themselves at construction time, so an impossible
configuration fails fast with a descriptive message instead of producing an
executor that silently misbehaves: a grid whose range is inverted collapses to a
single level, a limit price on the wrong side of the range can never trigger, a
zero order interval divides by zero while sizing a TWAP.

Every helper raises ``ValueError`` (pydantic surfaces it as a ``ValidationError``
on the config) and formats the message the same way: ``<field> (<value>) must ...``.
"""

from decimal import Decimal
from typing import List, Optional, Sequence, Set, Tuple, Union

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType

Number = Union[int, float, Decimal]
NamedValue = Tuple[str, Number]

# Tokens that represent the same underlying asset across venues, so a pair quoted
# with one of them can be traded against a pair quoted with the other.
INTERCHANGEABLE_TOKENS: List[Set[str]] = [
    {"WETH", "ETH"},
    {"WBTC", "BTC"},
    {"WBNB", "BNB"},
    {"WPOL", "POL"},
    {"WAVAX", "AVAX"},
    {"WONE", "ONE"},
    {"USDC", "USDC.E"},
    {"USOL", "SOL"},
    {"UETH", "ETH"},
    {"UBTC", "BTC"},
]


def require_non_empty(field: str, value: Optional[str]) -> None:
    """Validate that a string field is set and not blank."""
    if value is None or not value.strip():
        raise ValueError(f"{field} must not be empty")


def require_positive(field: str, value: Optional[Number]) -> None:
    """Validate that a value is strictly greater than 0. ``None`` is skipped."""
    if value is not None and value <= 0:
        raise ValueError(f"{field} ({value}) must be greater than 0")


def require_non_negative(field: str, value: Optional[Number]) -> None:
    """Validate that a value is not negative. ``None`` is skipped."""
    if value is not None and value < 0:
        raise ValueError(f"{field} ({value}) must be greater than or equal to 0")


def require_at_least(field: str, value: Optional[Number], minimum: Number) -> None:
    """Validate that a value is not below ``minimum``. ``None`` is skipped."""
    if value is not None and value < minimum:
        raise ValueError(f"{field} ({value}) must be greater than or equal to {minimum}")


def require_lower_than(field: str, value: Optional[Number], other_field: str, other_value: Optional[Number]) -> None:
    """Validate that ``value`` is strictly below ``other_value``. ``None`` on either side is skipped."""
    if value is not None and other_value is not None and value >= other_value:
        raise ValueError(f"{field} ({value}) must be lower than {other_field} ({other_value})")


def require_not_above(field: str, value: Optional[Number], other_field: str, other_value: Optional[Number]) -> None:
    """Validate that ``value`` does not exceed ``other_value``. ``None`` on either side is skipped."""
    if value is not None and other_value is not None and value > other_value:
        raise ValueError(f"{field} ({value}) must be lower than or equal to {other_field} ({other_value})")


def require_all_positive(field: str, values: Optional[Sequence[Number]]) -> None:
    """Validate every entry of a sequence, reporting the offending index."""
    if values is None:
        return
    for index, value in enumerate(values):
        require_positive(f"{field}[{index}]", value)


def require_directional_side(side: TradeType, field: str = "side") -> None:
    """Validate that a side is BUY or SELL, i.e. it defines a direction."""
    if side not in (TradeType.BUY, TradeType.SELL):
        raise ValueError(f"{field} ({side.name}) must be either BUY or SELL")


def require_market_order_type(field: str, order_type: OrderType) -> None:
    """Validate that a barrier that has to close immediately is not configured as a limit order."""
    if order_type != OrderType.MARKET:
        raise ValueError(f"{field} ({order_type.name}) must be MARKET")


def require_trading_pair(field: str, trading_pair: Optional[str]) -> None:
    """Validate that a trading pair follows the BASE-QUOTE format used across the codebase."""
    require_non_empty(field, trading_pair)
    tokens = trading_pair.split("-")
    if len(tokens) != 2 or not all(token.strip() for token in tokens):
        raise ValueError(f"{field} ({trading_pair}) must follow the BASE-QUOTE format")


def require_provider(field: str, provider: Optional[str], required: bool = True) -> None:
    """
    Validate that a Gateway provider follows the ``name/type`` format.

    Gateway keys its unified routes by ``connector/type`` (e.g. ``jupiter/router``,
    ``meteora/clmm``) and answers a bare name with a 400. Guessing the type instead
    only moved the failure to execution time — for a close-out swap, that is with
    funds already exposed — so the config has to carry it.

    ``None`` is skipped when ``required`` is False (an optional provider that falls
    back to the network default).
    """
    if provider is None and not required:
        return
    require_non_empty(field, provider)
    name, _, trading_type = provider.partition("/")
    if not name.strip() or not trading_type.strip():
        raise ValueError(
            f"{field} ({provider}) must follow the name/type format, e.g. jupiter/router or meteora/clmm")


def require_stop_price(side: TradeType, field: str, value: Optional[Decimal],
                       boundaries: Sequence[NamedValue]) -> None:
    """
    Validate that a stop-out price sits beyond the losing edge of a price range.

    A long position is stopped out by falling prices, so its stop has to be below every
    boundary of the range; a short position is stopped out by rising prices, so its stop
    has to be above every boundary. A stop on the winning side can never be reached
    before the position is already closed, which makes the config meaningless.
    """
    if value is None:
        return
    require_positive(field, value)
    if side == TradeType.BUY:
        boundary_field, boundary = min(boundaries, key=lambda item: item[1])
        if value >= boundary:
            raise ValueError(
                f"{field} ({value}) must be lower than {boundary_field} ({boundary}) for a BUY side: "
                f"a long is stopped out by falling prices, so the stop has to sit below the range")
    else:
        boundary_field, boundary = max(boundaries, key=lambda item: item[1])
        if value <= boundary:
            raise ValueError(
                f"{field} ({value}) must be higher than {boundary_field} ({boundary}) for a SELL side: "
                f"a short is stopped out by rising prices, so the stop has to sit above the range")


def are_tokens_interchangeable(first_token: str, second_token: str) -> bool:
    """Whether two tokens represent the same underlying asset."""
    same_token_condition = first_token == second_token
    tokens_interchangeable_condition = any(
        {first_token, second_token} <= interchangeable_pair for interchangeable_pair in INTERCHANGEABLE_TOKENS)
    # for now, we will consider all the stablecoins interchangeable
    stable_coins_condition = "USD" in first_token and "USD" in second_token
    return same_token_condition or tokens_interchangeable_condition or stable_coins_condition


def require_interchangeable_pairs(field: str, trading_pair: str, other_field: str, other_trading_pair: str) -> None:
    """Validate that two markets trade the same underlying asset, so one can be closed against the other."""
    require_trading_pair(field, trading_pair)
    require_trading_pair(other_field, other_trading_pair)
    base_asset, _ = split_hb_trading_pair(trading_pair)
    other_base_asset, _ = split_hb_trading_pair(other_trading_pair)
    if not are_tokens_interchangeable(base_asset, other_base_asset):
        raise ValueError(f"{field} ({trading_pair}) and {other_field} ({other_trading_pair}) are not interchangeable: "
                         f"the base assets {base_asset} and {other_base_asset} are different assets")
