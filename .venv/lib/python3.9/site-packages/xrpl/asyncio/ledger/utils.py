"""Helper functions for the ledger module."""

from typing import Any, Dict


def calculate_fee_dynamically(fee_data_set: Dict[str, Any]) -> str:
    """Calculate the transaction fee dynamically
    based on the size of the queue of the node.

    Args:
        fee_data_set (Dict[str, Any]): The result of the `fee` method.

    Returns:
        str: The transaction fee, in drops.
        `Read more about drops <https://xrpl.org/currency-formats.html#xrp-amounts>`_

    Based on fee-calculation code here:
    `<https://gist.github.com/WietseWind/3e9f9339f37a5881978a9661f49b0e52>`_
    """
    current_queue_size = int(fee_data_set["current_queue_size"])
    max_queue_size = int(fee_data_set["max_queue_size"])
    queue_pct = current_queue_size / max_queue_size
    drops = fee_data_set["drops"]
    minimum_fee = int(drops["minimum_fee"])
    median_fee = int(drops["median_fee"])
    open_ledger_fee = int(drops["open_ledger_fee"])

    # calculate the lowest fee the user is able to pay if the queue is empty
    fee_low = round(
        min(
            max(minimum_fee * 1.5, round(max(median_fee, open_ledger_fee) / 500)),
            1000,
        ),
    )
    if queue_pct > 0.1:  # if 'current_queue_size' is >10 % of 'max_queue_size'
        possible_fee_medium = round(
            (minimum_fee + median_fee + open_ledger_fee) / 3,
        )
    elif queue_pct == 0:  # if 'current_queue_size' is 0
        possible_fee_medium = max(
            10 * minimum_fee,
            open_ledger_fee,
        )
    else:
        possible_fee_medium = max(
            10 * minimum_fee,
            round((minimum_fee + median_fee) / 2),
        )
    # calculate the lowest fee the user is able to pay if there are txns in the queue
    fee_medium = round(
        min(
            possible_fee_medium,
            fee_low * 15,
            10000,
        ),
    )
    # calculate the lowest fee the user is able to pay if the txn queue is full
    fee_high = round(
        min(
            max(10 * minimum_fee, round(max(median_fee, open_ledger_fee) * 1.1)),
            100000,
        ),
    )

    if queue_pct == 0:  # if queue is empty
        fee = str(fee_low)
    elif 0 < queue_pct < 1:  # queue has txns in it but is not full
        fee = str(fee_medium)
    else:  # if queue is full
        fee = str(fee_high)

    return fee
