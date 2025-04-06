from typing import (
    Optional,
    Sequence,
)

from web3.exceptions import (
    InsufficientData,
    Web3ValueError,
)


def percentile(
    values: Optional[Sequence[int]] = None, percentile: Optional[float] = None
) -> float:
    """Calculates a simplified weighted average percentile"""
    if values in [None, tuple(), []] or len(values) < 1:
        raise InsufficientData(
            f"Expected a sequence of at least 1 integers, got {values!r}"
        )
    if percentile is None:
        raise Web3ValueError(f"Expected a percentile choice, got {percentile}")
    if percentile < 0 or percentile > 100:
        raise Web3ValueError("percentile must be in the range [0, 100]")

    sorted_values = sorted(values)

    index = len(values) * percentile / 100 - 1
    if index < 0:
        return sorted_values[0]

    fractional = index % 1
    if fractional == 0:
        return sorted_values[int(index)]

    integer = int(index - fractional)
    lower = sorted_values[integer]
    higher = sorted_values[integer + 1]
    return lower + fractional * (higher - lower)
