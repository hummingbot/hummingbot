from functools import (
    singledispatch,
)
import operator
from typing import (
    TYPE_CHECKING,
    Any,
    Collection,
    Iterable,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from eth_account import (
    Account,
)
from eth_account.signers.local import (
    LocalAccount,
)
from eth_account.types import (
    TransactionDictType as EthAccountTxParams,
)
from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    ChecksumAddress,
    HexStr,
)
from eth_utils import (
    to_checksum_address,
    to_dict,
)
from eth_utils.curried import (
    apply_formatter_if,
)
from eth_utils.toolz import (
    compose,
)
from toolz import (
    curry,
)

from web3._utils.async_transactions import (
    async_fill_nonce,
    async_fill_transaction_defaults,
)
from web3._utils.method_formatters import (
    STANDARD_NORMALIZERS,
)
from web3._utils.rpc_abi import (
    TRANSACTION_PARAMS_ABIS,
    apply_abi_formatters_to_dict,
)
from web3._utils.transactions import (
    fill_nonce,
    fill_transaction_defaults,
)
from web3.exceptions import (
    Web3TypeError,
)
from web3.middleware.base import (
    Web3MiddlewareBuilder,
)
from web3.types import (
    RPCEndpoint,
    TxParams,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )

T = TypeVar("T")

to_hexstr_from_eth_key = operator.methodcaller("to_hex")


def is_eth_key(value: Any) -> bool:
    return isinstance(value, PrivateKey)


key_normalizer = compose(
    apply_formatter_if(is_eth_key, to_hexstr_from_eth_key),
)

_PrivateKey = Union[LocalAccount, PrivateKey, HexStr, bytes]


@to_dict
def gen_normalized_accounts(
    val: Union[_PrivateKey, Collection[_PrivateKey]]
) -> Iterable[Tuple[ChecksumAddress, LocalAccount]]:
    if isinstance(
        val,
        (
            list,
            tuple,
            set,
        ),
    ):
        for i in val:
            account: LocalAccount = to_account(i)
            yield account.address, account
    else:
        account = to_account(val)
        yield account.address, account
        return


@singledispatch
def to_account(val: Any) -> LocalAccount:
    raise Web3TypeError(
        "key must be one of the types: "
        "eth_keys.datatype.PrivateKey, eth_account.signers.local.LocalAccount, "
        "or raw private key as a hex string or byte string. "
        f"Was of type {type(val)}"
    )


@to_account.register(LocalAccount)
def _(val: T) -> T:
    return val


def private_key_to_account(val: _PrivateKey) -> LocalAccount:
    normalized_key = key_normalizer(val)
    return Account.from_key(normalized_key)


to_account.register(PrivateKey, private_key_to_account)
to_account.register(str, private_key_to_account)
to_account.register(bytes, private_key_to_account)


def format_transaction(transaction: TxParams) -> TxParams:
    """
    Format transaction so that it can be used correctly in the signing middleware.

    Converts bytes to hex strings and other types that can be passed to
    the underlying layers. Also has the effect of normalizing 'from' for
    easier comparisons.
    """
    return apply_abi_formatters_to_dict(
        STANDARD_NORMALIZERS, TRANSACTION_PARAMS_ABIS, transaction
    )


class SignAndSendRawMiddlewareBuilder(Web3MiddlewareBuilder):
    _accounts = None
    format_and_fill_tx = None

    @staticmethod
    @curry
    def build(
        private_key_or_account: Union[_PrivateKey, Collection[_PrivateKey]],
        w3: Union["Web3", "AsyncWeb3"],
    ) -> "SignAndSendRawMiddlewareBuilder":
        middleware = SignAndSendRawMiddlewareBuilder(w3)
        middleware._accounts = gen_normalized_accounts(private_key_or_account)
        return middleware

    def request_processor(self, method: "RPCEndpoint", params: Any) -> Any:
        if method != "eth_sendTransaction":
            return method, params
        else:
            w3 = cast("Web3", self._w3)
            if self.format_and_fill_tx is None:
                self.format_and_fill_tx = compose(
                    format_transaction,
                    fill_transaction_defaults(w3),
                    fill_nonce(w3),
                )

            filled_transaction = self.format_and_fill_tx(params[0])
            tx_from = filled_transaction.get("from", None)

            if tx_from is None or (
                tx_from is not None and tx_from not in self._accounts
            ):
                return method, params
            else:
                account = self._accounts[to_checksum_address(tx_from)]
                raw_tx = account.sign_transaction(filled_transaction).raw_transaction

                return (
                    RPCEndpoint("eth_sendRawTransaction"),
                    [raw_tx.to_0x_hex()],
                )

    # -- async -- #

    async def async_request_processor(self, method: "RPCEndpoint", params: Any) -> Any:
        if method != "eth_sendTransaction":
            return method, params

        else:
            w3 = cast("AsyncWeb3", self._w3)

            formatted_transaction = format_transaction(params[0])
            filled_transaction = await async_fill_transaction_defaults(
                w3, formatted_transaction
            )
            filled_transaction = await async_fill_nonce(w3, filled_transaction)
            tx_from = filled_transaction.get("from", None)

            if tx_from is None or (
                tx_from is not None and tx_from not in self._accounts
            ):
                return method, params
            else:
                account = self._accounts[to_checksum_address(tx_from)]
                raw_tx = account.sign_transaction(
                    cast(EthAccountTxParams, filled_transaction)
                ).raw_transaction

                return (
                    RPCEndpoint("eth_sendRawTransaction"),
                    [raw_tx.to_0x_hex()],
                )
