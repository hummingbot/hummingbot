from typing import (
    TYPE_CHECKING,
    Dict,
    Optional,
    Union,
    cast,
)

from eth_typing import (
    ChecksumAddress,
)
from eth_utils.toolz import (
    assoc,
    merge,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.transactions import (
    prepare_replacement_transaction,
)
from web3._utils.utility_methods import (
    any_in_dict,
)
from web3.constants import (
    DYNAMIC_FEE_TXN_PARAMS,
)
from web3.exceptions import (
    Web3ValueError,
)
from web3.types import (
    BlockIdentifier,
    TxData,
    TxParams,
    Wei,
    _Hash32,
)

if TYPE_CHECKING:
    from web3.eth import AsyncEth  # noqa: F401
    from web3.main import (  # noqa: F401
        AsyncWeb3,
    )


# unused vars present in these funcs because they all need to have the same signature
async def _estimate_gas(
    async_w3: "AsyncWeb3", tx: TxParams, _defaults: Dict[str, Union[bytes, int]]
) -> int:
    return await async_w3.eth.estimate_gas(tx)


async def _max_fee_per_gas(
    async_w3: "AsyncWeb3", tx: TxParams, defaults: Dict[str, Union[bytes, int]]
) -> Wei:
    block = await async_w3.eth.get_block("latest")
    max_priority_fee = tx.get(
        "maxPriorityFeePerGas", defaults.get("maxPriorityFeePerGas")
    )
    return Wei(int(max_priority_fee) + (2 * int(block["baseFeePerGas"])))


async def _max_priority_fee_gas(
    async_w3: "AsyncWeb3", _tx: TxParams, _defaults: Dict[str, Union[bytes, int]]
) -> Wei:
    return await async_w3.eth.max_priority_fee


async def _chain_id(
    async_w3: "AsyncWeb3", _tx: TxParams, _defaults: Dict[str, Union[bytes, int]]
) -> int:
    return await async_w3.eth.chain_id


TRANSACTION_DEFAULTS = {
    "value": 0,
    "data": b"",
    "gas": _estimate_gas,
    "gasPrice": lambda async_w3, tx, _defaults: async_w3.eth.generate_gas_price(tx),
    "maxPriorityFeePerGas": _max_priority_fee_gas,
    "maxFeePerGas": _max_fee_per_gas,
    "chainId": _chain_id,
}


async def get_block_gas_limit(
    web3_eth: "AsyncEth", block_identifier: Optional[BlockIdentifier] = None
) -> int:
    block = await web3_eth.get_block(block_identifier or "latest")
    return block["gasLimit"]


async def get_buffered_gas_estimate(
    async_w3: "AsyncWeb3", transaction: TxParams, gas_buffer: int = 100000
) -> int:
    gas_estimate_transaction = cast(TxParams, dict(**transaction))

    gas_estimate = await async_w3.eth.estimate_gas(gas_estimate_transaction)

    gas_limit = await get_block_gas_limit(async_w3.eth)

    if gas_estimate > gas_limit:
        raise Web3ValueError(
            "Gas estimate for transaction is higher than current network gas limits. "
            f"Transaction could not be sent. Estimated: {gas_estimate}. "
            f"Current gas limit: {gas_limit}"
        )

    return min(gas_limit, gas_estimate + gas_buffer)


async def async_fill_nonce(async_w3: "AsyncWeb3", transaction: TxParams) -> TxParams:
    if "from" in transaction and "nonce" not in transaction:
        tx_count = await async_w3.eth.get_transaction_count(
            cast(ChecksumAddress, transaction["from"]),
            block_identifier="pending",
        )
        return assoc(transaction, "nonce", tx_count)
    return transaction


async def async_fill_transaction_defaults(
    async_w3: "AsyncWeb3", transaction: TxParams
) -> TxParams:
    """
    If async_w3 is None, fill as much as possible while offline
    """
    strategy_based_gas_price = async_w3.eth.generate_gas_price(transaction)

    is_dynamic_fee_transaction = strategy_based_gas_price is None and (
        "gasPrice" not in transaction  # default to dynamic fee transaction
        or any_in_dict(DYNAMIC_FEE_TXN_PARAMS, transaction)
    )

    defaults: Dict[str, Union[bytes, int]] = {}
    for key, default_getter in TRANSACTION_DEFAULTS.items():
        if key not in transaction:
            if (
                is_dynamic_fee_transaction
                and key == "gasPrice"
                or not is_dynamic_fee_transaction
                and key in DYNAMIC_FEE_TXN_PARAMS
            ):
                # do not set default max fees if legacy txn or
                # gas price if dynamic fee txn
                continue

            if callable(default_getter):
                if async_w3 is None:
                    raise Web3ValueError(
                        f"You must specify a '{key}' value in the transaction"
                    )
                if key == "gasPrice":
                    # `generate_gas_price()` is on the `BaseEth` class and does not
                    # need to be awaited
                    default_val = default_getter(async_w3, transaction, defaults)
                else:
                    default_val = await default_getter(async_w3, transaction, defaults)
            else:
                default_val = default_getter

            defaults[key] = default_val
    return merge(defaults, transaction)


async def async_get_required_transaction(
    async_w3: "AsyncWeb3", transaction_hash: _Hash32
) -> TxData:
    current_transaction = await async_w3.eth.get_transaction(transaction_hash)
    if not current_transaction:
        raise Web3ValueError(
            f"Supplied transaction with hash {transaction_hash!r} does not exist"
        )
    return current_transaction


async def async_replace_transaction(
    async_w3: "AsyncWeb3", current_transaction: TxData, new_transaction: TxParams
) -> HexBytes:
    new_transaction = prepare_replacement_transaction(
        async_w3, current_transaction, new_transaction
    )
    return await async_w3.eth.send_transaction(new_transaction)
