from typing import (
    TYPE_CHECKING,
)

from web3.types import (
    FeeHistory,
    Wei,
)

if TYPE_CHECKING:
    from web3.eth import AsyncEth  # noqa: F401
    from web3.eth import Eth  # noqa: F401

PRIORITY_FEE_MAX = Wei(1500000000)  # 1.5 gwei
PRIORITY_FEE_MIN = Wei(1000000000)  # 1 gwei

# 5th percentile fee history from the last 10 blocks
PRIORITY_FEE_HISTORY_PARAMS = (10, "pending", [5.0])


def _fee_history_priority_fee_estimate(fee_history: FeeHistory) -> Wei:
    # grab only non-zero fees and average against only that list
    non_empty_block_fees = [fee[0] for fee in fee_history["reward"] if fee[0] != 0]

    # prevent division by zero in the extremely unlikely case that all fees within
    # the polled fee history range for the specified percentile are 0
    divisor = len(non_empty_block_fees) if len(non_empty_block_fees) != 0 else 1

    priority_fee_average_for_percentile = Wei(
        round(sum(non_empty_block_fees) / divisor)
    )

    return (  # keep estimated priority fee within a max / min range
        PRIORITY_FEE_MAX
        if priority_fee_average_for_percentile > PRIORITY_FEE_MAX
        else (
            PRIORITY_FEE_MIN
            if priority_fee_average_for_percentile < PRIORITY_FEE_MIN
            else priority_fee_average_for_percentile
        )
    )


def fee_history_priority_fee(eth: "Eth") -> Wei:
    # This is a tested internal call so no need for type hinting. We can keep
    # better consistency between the sync and async calls by unpacking
    # PRIORITY_FEE_HISTORY_PARAMS as constants here.
    fee_history = eth.fee_history(*PRIORITY_FEE_HISTORY_PARAMS)  # type: ignore
    return _fee_history_priority_fee_estimate(fee_history)


async def async_fee_history_priority_fee(async_eth: "AsyncEth") -> Wei:
    # This is a tested internal call so no need for type hinting. We can keep
    # better consistency between the sync and async calls by unpacking
    # PRIORITY_FEE_HISTORY_PARAMS as constants here.
    fee_history = await async_eth.fee_history(*PRIORITY_FEE_HISTORY_PARAMS)  # type: ignore  # noqa: E501
    return _fee_history_priority_fee_estimate(fee_history)
