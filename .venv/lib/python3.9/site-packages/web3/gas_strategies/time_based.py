import collections
import math
import operator
from typing import (
    Iterable,
    Sequence,
    Tuple,
    cast,
)

from eth_typing import (
    ChecksumAddress,
)
from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    curry,
    groupby,
    sliding_window,
)
from hexbytes import (
    HexBytes,
)

from web3 import (
    Web3,
)
from web3._utils.math import (
    percentile,
)
from web3.exceptions import (
    InsufficientData,
    Web3ValidationError,
)
from web3.types import (
    BlockNumber,
    GasPriceStrategy,
    TxData,
    TxParams,
    Wei,
)

MinerData = collections.namedtuple(
    "MinerData", ["miner", "num_blocks", "min_gas_price", "low_percentile_gas_price"]
)
Probability = collections.namedtuple("Probability", ["gas_price", "prob"])


def _get_avg_block_time(w3: Web3, sample_size: int) -> float:
    latest = w3.eth.get_block("latest")

    constrained_sample_size = min(sample_size, latest["number"])
    if constrained_sample_size == 0:
        raise Web3ValidationError("Constrained sample size is 0")

    oldest = w3.eth.get_block(BlockNumber(latest["number"] - constrained_sample_size))
    return (latest["timestamp"] - oldest["timestamp"]) / constrained_sample_size


def _get_weighted_avg_block_time(w3: Web3, sample_size: int) -> float:
    latest_block_number = w3.eth.get_block("latest")["number"]
    constrained_sample_size = min(sample_size, latest_block_number)
    if constrained_sample_size == 0:
        raise Web3ValidationError("Constrained sample size is 0")
    oldest_block = w3.eth.get_block(
        BlockNumber(latest_block_number - constrained_sample_size)
    )
    oldest_block_number = oldest_block["number"]
    prev_timestamp = oldest_block["timestamp"]
    weighted_sum = 0.0
    sum_of_weights = 0.0
    for i in range(oldest_block_number + 1, latest_block_number + 1):
        curr_timestamp = w3.eth.get_block(BlockNumber(i))["timestamp"]
        time = curr_timestamp - prev_timestamp
        weight = (i - oldest_block_number) / constrained_sample_size
        weighted_sum += time * weight
        sum_of_weights += weight
        prev_timestamp = curr_timestamp
    return weighted_sum / sum_of_weights


def _get_raw_miner_data(
    w3: Web3, sample_size: int
) -> Iterable[Tuple[ChecksumAddress, HexBytes, Wei]]:
    latest = w3.eth.get_block("latest", full_transactions=True)

    for transaction in latest["transactions"]:
        transaction = cast(TxData, transaction)
        yield (latest["miner"], latest["hash"], transaction["gasPrice"])

    block = latest

    for _ in range(sample_size - 1):
        if block["number"] == 0:
            break

        # we intentionally trace backwards using parent hashes rather than
        # block numbers to make caching the data easier to implement.
        block = w3.eth.get_block(block["parentHash"], full_transactions=True)
        for transaction in block["transactions"]:
            transaction = cast(TxData, transaction)
            yield (block["miner"], block["hash"], transaction["gasPrice"])


def _aggregate_miner_data(
    raw_data: Iterable[Tuple[ChecksumAddress, HexBytes, Wei]]
) -> Iterable[MinerData]:
    data_by_miner = groupby(0, raw_data)

    for miner, miner_data in data_by_miner.items():
        _, block_hashes, gas_prices = map(set, zip(*miner_data))
        try:
            # types ignored b/c mypy has trouble inferring gas_prices: Sequence[Wei]
            price_percentile = percentile(gas_prices, percentile=20)  # type: ignore
        except InsufficientData:
            price_percentile = min(gas_prices)
        yield MinerData(
            miner,
            len(set(block_hashes)),
            min(gas_prices),
            price_percentile,
        )


@to_tuple
def _compute_probabilities(
    miner_data: Iterable[MinerData], wait_blocks: int, sample_size: int
) -> Iterable[Probability]:
    """
    Computes the probabilities that a txn will be accepted at each of the gas
    prices accepted by the miners.
    """
    miner_data_by_price = tuple(
        sorted(
            miner_data,
            key=operator.attrgetter("low_percentile_gas_price"),
            reverse=True,
        )
    )
    for idx in range(len(miner_data_by_price)):
        low_percentile_gas_price = miner_data_by_price[idx].low_percentile_gas_price
        num_blocks_accepting_price = sum(
            m.num_blocks for m in miner_data_by_price[idx:]
        )
        inv_prob_per_block = (sample_size - num_blocks_accepting_price) / sample_size
        probability_accepted = 1 - inv_prob_per_block**wait_blocks
        yield Probability(low_percentile_gas_price, probability_accepted)


def _compute_gas_price(
    probabilities: Sequence[Probability], desired_probability: float
) -> Wei:
    """
    Given a sorted range of ``Probability`` named-tuples returns a gas price
    computed based on where the ``desired_probability`` would fall within the
    range.

    :param probabilities: An iterable of `Probability` named-tuples
        sorted in reverse order.
    :param desired_probability: A floating point representation of the desired
        probability. (e.g. ``85% -> 0.85``)
    """
    first = probabilities[0]
    last = probabilities[-1]

    if desired_probability >= first.prob:
        return Wei(int(first.gas_price))
    elif desired_probability <= last.prob:
        return Wei(int(last.gas_price))

    for left, right in sliding_window(2, probabilities):
        if desired_probability < right.prob:
            continue
        elif desired_probability > left.prob:
            # This code block should never be reachable as it would indicate
            # that we already passed by the probability window in which our
            # `desired_probability` is located.
            raise Exception("Invariant")

        adj_prob = desired_probability - right.prob
        window_size = left.prob - right.prob
        position = adj_prob / window_size
        gas_window_size = left.gas_price - right.gas_price
        gas_price = int(math.ceil(right.gas_price + gas_window_size * position))
        return Wei(gas_price)
    else:
        # The initial `if/else` clause in this function handles the case where
        # the `desired_probability` is either above or below the min/max
        # probability found in the `probabilities`.
        #
        # With these two cases handled, the only way this code block should be
        # reachable would be if the `probabilities` were not sorted correctly.
        # Otherwise, the `desired_probability` **must** fall between two of the
        # values in the `probabilities``.
        raise Exception("Invariant")


@curry
def construct_time_based_gas_price_strategy(
    max_wait_seconds: int,
    sample_size: int = 120,
    probability: int = 98,
    weighted: bool = False,
) -> GasPriceStrategy:
    """
    A gas pricing strategy that uses recently mined block data to derive a gas
    price for which a transaction is likely to be mined within X seconds with
    probability P. If the weighted kwarg is True, more recent block
    times will be more heavily weighted.

    :param max_wait_seconds: The desired maximum number of seconds the
        transaction should take to mine.
    :param sample_size: The number of recent blocks to sample
    :param probability: An integer representation of the desired probability
        that the transaction will be mined within ``max_wait_seconds``.  0 means 0%
        and 100 means 100%.
    """

    def time_based_gas_price_strategy(w3: Web3, transaction_params: TxParams) -> Wei:
        # return gas price when no transactions available to sample
        if w3.eth.get_block("latest")["number"] == 0:
            return w3.eth.gas_price

        if weighted:
            avg_block_time = _get_weighted_avg_block_time(w3, sample_size=sample_size)
        else:
            avg_block_time = _get_avg_block_time(w3, sample_size=sample_size)

        wait_blocks = int(math.ceil(max_wait_seconds / avg_block_time))
        raw_miner_data = _get_raw_miner_data(w3, sample_size=sample_size)
        miner_data = _aggregate_miner_data(raw_miner_data)

        probabilities = _compute_probabilities(
            miner_data,
            wait_blocks=wait_blocks,
            sample_size=sample_size,
        )

        gas_price = _compute_gas_price(probabilities, probability / 100)
        return gas_price

    return time_based_gas_price_strategy


# fast: mine within 1 minute
fast_gas_price_strategy = construct_time_based_gas_price_strategy(
    max_wait_seconds=60,
    sample_size=120,
)
# medium: mine within 10 minutes
medium_gas_price_strategy = construct_time_based_gas_price_strategy(
    max_wait_seconds=600,
    sample_size=120,
)
# slow: mine within 1 hour (60 minutes)
slow_gas_price_strategy = construct_time_based_gas_price_strategy(
    max_wait_seconds=60 * 60,
    sample_size=120,
)
# glacial: mine within the next 24 hours.
glacial_gas_price_strategy = construct_time_based_gas_price_strategy(
    max_wait_seconds=24 * 60 * 60,
    sample_size=720,
)
