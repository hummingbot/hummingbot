import pytest
import asyncio
import json
import math
from random import (
    randint,
)
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    Type,
    Union,
    cast,
)

import eth_abi as abi
from eth_typing import (
    BlockNumber,
    ChecksumAddress,
    HexAddress,
    HexStr,
)
from eth_utils import (
    is_boolean,
    is_bytes,
    is_checksum_address,
    is_dict,
    is_integer,
    is_list_like,
    is_same_address,
    is_string,
    remove_0x_prefix,
    to_bytes,
)
from eth_utils.toolz import (
    assoc,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.ens import (
    ens_addresses,
)
from web3._utils.error_formatters_utils import (
    PANIC_ERROR_CODES,
)
from web3._utils.fee_utils import (
    PRIORITY_FEE_MIN,
)
from web3._utils.method_formatters import (
    to_hex_if_integer,
)
from web3._utils.module_testing.module_testing_utils import (
    assert_contains_log,
    async_mock_offchain_lookup_request_response,
    flaky_geth_dev_mining,
    mock_offchain_lookup_request_response,
)
from web3._utils.module_testing.utils import (
    RequestMocker,
)
from web3._utils.type_conversion import (
    to_hex_if_bytes,
)
from web3.exceptions import (
    BlockNotFound,
    ContractCustomError,
    ContractLogicError,
    ContractPanicError,
    InvalidAddress,
    InvalidTransaction,
    MultipleFailedRequests,
    NameNotFound,
    OffchainLookup,
    TimeExhausted,
    TooManyRequests,
    TransactionNotFound,
    TransactionTypeMismatch,
    Web3RPCError,
    Web3ValidationError,
    Web3ValueError,
)
from web3.middleware import (
    ExtraDataToPOAMiddleware,
    SignAndSendRawMiddlewareBuilder,
)
from web3.types import (
    ENS,
    BlockData,
    FilterParams,
    Nonce,
    RPCEndpoint,
    StateOverrideParams,
    SyncStatus,
    TxData,
    TxParams,
    Wei,
)

UNKNOWN_ADDRESS = ChecksumAddress(
    HexAddress(HexStr("0xdEADBEeF00000000000000000000000000000000"))
)

UNKNOWN_HASH = HexStr(
    "0xdeadbeef00000000000000000000000000000000000000000000000000000000"
)
# "test offchain lookup" as an abi-encoded string
OFFCHAIN_LOOKUP_TEST_DATA = "0x0000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000001474657374206f6666636861696e206c6f6f6b7570000000000000000000000000"  # noqa: E501
OFFCHAIN_LOOKUP_4BYTE_DATA = "0x556f1830"
OFFCHAIN_LOOKUP_RETURN_DATA = "00000000000000000000000000000000000000000000000000000000000000a000000000000000000000000000000000000000000000000000000000000001a0da96d05a0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002200000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000a0000000000000000000000000000000000000000000000000000000000000002c68747470733a2f2f776562332e70792f676174657761792f7b73656e6465727d2f7b646174617d2e6a736f6e0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001768747470733a2f2f776562332e70792f6761746577617900000000000000000000000000000000000000000000000000000000000000000000000000000000600000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000001474657374206f6666636861696e206c6f6f6b757000000000000000000000000000000000000000000000000000000000000000000000000000000000000000600000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000001474657374206f6666636861696e206c6f6f6b7570000000000000000000000000"  # noqa: E501
# "web3py" as an abi-encoded string
WEB3PY_AS_HEXBYTES = "0x000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000067765623370790000000000000000000000000000000000000000000000000000"  # noqa: E501

RLP_ACCESS_LIST = [
    (
        "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae",
        (
            "0x0000000000000000000000000000000000000000000000000000000000000003",
            "0x0000000000000000000000000000000000000000000000000000000000000007",
        ),
    ),
    ("0xbb9bc244d798123fde783fcc1c72d3bb8c189413", ()),
]

RPC_ACCESS_LIST = [
    {
        "address": "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae",
        "storageKeys": (
            "0x0000000000000000000000000000000000000000000000000000000000000003",
            "0x0000000000000000000000000000000000000000000000000000000000000007",
        ),
    },
    {"address": "0xbb9bc244d798123fde783fcc1c72d3bb8c189413", "storageKeys": ()},
]

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch  # noqa: F401

    from web3.contract import (  # noqa: F401
        AsyncContract,
        Contract,
    )
    from web3.main import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )


def abi_encoded_offchain_lookup_contract_address(
    w3: Union["Web3", "AsyncWeb3"],
    offchain_lookup_contract: Union["Contract", "AsyncContract"],
) -> HexAddress:
    return HexAddress(
        remove_0x_prefix(
            w3.to_hex(
                abi.encode(
                    ["address"],
                    [to_bytes(hexstr=offchain_lookup_contract.address)],
                )
            )
        )
    )


class AsyncEthModuleTest:
    @pytest.mark.asyncio
    async def test_eth_gas_price(self, async_w3: "AsyncWeb3") -> None:
        gas_price = await async_w3.eth.gas_price

        assert gas_price > 0

    @pytest.mark.asyncio
    async def test_is_connected(self, async_w3: "AsyncWeb3") -> None:
        is_connected = await async_w3.is_connected()
        assert is_connected is True

    @pytest.mark.asyncio
    async def test_eth_send_transaction_legacy(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": await async_w3.eth.gas_price,
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)
        txn = await async_w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 21000
        assert txn["gasPrice"] == txn_params["gasPrice"]

    @pytest.mark.asyncio
    async def test_eth_modify_transaction_legacy(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": async_w3.to_wei(
                1, "gwei"
            ),  # must be greater than base_fee post London
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)

        modified_txn_hash = await async_w3.eth.modify_transaction(
            txn_hash, gasPrice=(cast(Wei, txn_params["gasPrice"] * 2)), value=Wei(2)
        )
        modified_txn = await async_w3.eth.get_transaction(modified_txn_hash)

        assert is_same_address(
            modified_txn["from"], cast(ChecksumAddress, txn_params["from"])
        )
        assert is_same_address(
            modified_txn["to"], cast(ChecksumAddress, txn_params["to"])
        )
        assert modified_txn["value"] == 2
        assert modified_txn["gas"] == 21000
        assert modified_txn["gasPrice"] == cast(int, txn_params["gasPrice"]) * 2

    @pytest.mark.asyncio
    async def test_eth_modify_transaction(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxPriorityFeePerGas": async_w3.to_wei(1, "gwei"),
            "maxFeePerGas": async_w3.to_wei(2, "gwei"),
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)

        modified_txn_hash = await async_w3.eth.modify_transaction(
            txn_hash,
            value=Wei(2),
            maxPriorityFeePerGas=(cast(Wei, txn_params["maxPriorityFeePerGas"] * 2)),
            maxFeePerGas=(cast(Wei, txn_params["maxFeePerGas"] * 2)),
        )
        modified_txn = await async_w3.eth.get_transaction(modified_txn_hash)

        assert is_same_address(
            modified_txn["from"], cast(ChecksumAddress, txn_params["from"])
        )
        assert is_same_address(
            modified_txn["to"], cast(ChecksumAddress, txn_params["to"])
        )
        assert modified_txn["value"] == 2
        assert modified_txn["gas"] == 21000
        assert (
            modified_txn["maxPriorityFeePerGas"]
            == cast(Wei, txn_params["maxPriorityFeePerGas"]) * 2
        )
        assert modified_txn["maxFeePerGas"] == cast(Wei, txn_params["maxFeePerGas"]) * 2

    @pytest.mark.asyncio
    async def test_async_eth_sign_transaction(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": async_w3.to_wei(2, "gwei"),
            "maxPriorityFeePerGas": async_w3.to_wei(1, "gwei"),
            "nonce": Nonce(0),
        }
        result = await async_w3.eth.sign_transaction(txn_params)
        signatory_account = async_w3.eth.account.recover_transaction(result["raw"])
        assert async_keyfile_account_address_dual_type == signatory_account
        assert result["tx"]["to"] == txn_params["to"]
        assert result["tx"]["value"] == txn_params["value"]
        assert result["tx"]["gas"] == txn_params["gas"]
        assert result["tx"]["maxFeePerGas"] == txn_params["maxFeePerGas"]
        assert (
            result["tx"]["maxPriorityFeePerGas"] == txn_params["maxPriorityFeePerGas"]
        )
        assert result["tx"]["nonce"] == txn_params["nonce"]

    @pytest.mark.asyncio
    async def test_eth_sign_typed_data(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
        async_skip_if_testrpc: Callable[["AsyncWeb3"], None],
    ) -> None:
        validJSONMessage = """
            {
                "types": {
                    "EIP712Domain": [
                        {"name": "name", "type": "string"},
                        {"name": "version", "type": "string"},
                        {"name": "chainId", "type": "uint256"},
                        {"name": "verifyingContract", "type": "address"}
                    ],
                    "Person": [
                        {"name": "name", "type": "string"},
                        {"name": "wallet", "type": "address"}
                    ],
                    "Mail": [
                        {"name": "from", "type": "Person"},
                        {"name": "to", "type": "Person"},
                        {"name": "contents", "type": "string"}
                    ]
                },
                "primaryType": "Mail",
                "domain": {
                    "name": "Ether Mail",
                    "version": "1",
                    "chainId": "0x01",
                    "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC"
                },
                "message": {
                    "from": {
                        "name": "Cow",
                        "wallet": "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826"
                    },
                    "to": {
                        "name": "Bob",
                        "wallet": "0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB"
                    },
                    "contents": "Hello, Bob!"
                }
            }
        """
        async_skip_if_testrpc(async_w3)
        signature = HexBytes(
            await async_w3.eth.sign_typed_data(
                async_keyfile_account_address_dual_type, json.loads(validJSONMessage)
            )
        )
        assert len(signature) == 32 + 32 + 1

    @pytest.mark.asyncio
    async def test_invalid_eth_sign_typed_data(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
        async_skip_if_testrpc: Callable[["AsyncWeb3"], None],
    ) -> None:
        async_skip_if_testrpc(async_w3)
        invalid_typed_message = """
            {
                "types": {
                    "EIP712Domain": [
                        {"name": "name", "type": "string"},
                        {"name": "version", "type": "string"},
                        {"name": "chainId", "type": "uint256"},
                        {"name": "verifyingContract", "type": "address"}
                    ],
                    "Person": [
                        {"name": "name", "type": "string"},
                        {"name": "wallet", "type": "address"}
                    ],
                    "Mail": [
                        {"name": "from", "type": "Person"},
                        {"name": "to", "type": "Person[2]"},
                        {"name": "contents", "type": "string"}
                    ]
                },
                "primaryType": "Mail",
                "domain": {
                    "name": "Ether Mail",
                    "version": "1",
                    "chainId": "0x01",
                    "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC"
                },
                "message": {
                    "from": {
                        "name": "Cow",
                        "wallet": "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826"
                    },
                    "to": [{
                        "name": "Bob",
                        "wallet": "0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB"
                    }],
                    "contents": "Hello, Bob!"
                }
            }
        """
        with pytest.raises(
            Web3ValueError,
            match=r".*Expected 2 items for array type Person\[2\], got 1 items.*",
        ):
            await async_w3.eth.sign_typed_data(
                async_keyfile_account_address_dual_type,
                json.loads(invalid_typed_message),
            )

    @pytest.mark.asyncio
    async def test_async_eth_sign_transaction_legacy(
        self, async_w3: "AsyncWeb3", async_keyfile_account_address: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address,
            "to": async_keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": await async_w3.eth.gas_price,
            "nonce": Nonce(0),
        }
        result = await async_w3.eth.sign_transaction(txn_params)
        signatory_account = async_w3.eth.account.recover_transaction(result["raw"])
        assert async_keyfile_account_address == signatory_account
        assert result["tx"]["to"] == txn_params["to"]
        assert result["tx"]["value"] == txn_params["value"]
        assert result["tx"]["gas"] == txn_params["gas"]
        assert result["tx"]["gasPrice"] == txn_params["gasPrice"]
        assert result["tx"]["nonce"] == txn_params["nonce"]

    @pytest.mark.asyncio
    async def test_async_eth_sign_transaction_hex_fees(
        self, async_w3: "AsyncWeb3", async_keyfile_account_address: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address,
            "to": async_keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": hex(async_w3.to_wei(2, "gwei")),
            "maxPriorityFeePerGas": hex(async_w3.to_wei(1, "gwei")),
            "nonce": Nonce(0),
        }
        result = await async_w3.eth.sign_transaction(txn_params)
        signatory_account = async_w3.eth.account.recover_transaction(result["raw"])
        assert async_keyfile_account_address == signatory_account
        assert result["tx"]["to"] == txn_params["to"]
        assert result["tx"]["value"] == txn_params["value"]
        assert result["tx"]["gas"] == txn_params["gas"]
        assert result["tx"]["maxFeePerGas"] == int(str(txn_params["maxFeePerGas"]), 16)
        assert result["tx"]["maxPriorityFeePerGas"] == int(
            str(txn_params["maxPriorityFeePerGas"]), 16
        )
        assert result["tx"]["nonce"] == txn_params["nonce"]

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="async name_to_address_middleware has not been implemented yet"
    )
    async def test_async_eth_sign_transaction_ens_names(
        self, async_w3: "AsyncWeb3", async_keyfile_account_address: ChecksumAddress
    ) -> None:
        with ens_addresses(
            async_w3, {"unlocked-account.eth": async_keyfile_account_address}
        ):
            txn_params: TxParams = {
                "from": "unlocked-account.eth",
                "to": "unlocked-account.eth",
                "value": Wei(1),
                "gas": 21000,
                "maxFeePerGas": async_w3.to_wei(2, "gwei"),
                "maxPriorityFeePerGas": async_w3.to_wei(1, "gwei"),
                "nonce": Nonce(0),
            }
            result = await async_w3.eth.sign_transaction(txn_params)
            signatory_account = async_w3.eth.account.recover_transaction(result["raw"])
            assert async_keyfile_account_address == signatory_account
            assert result["tx"]["to"] == async_keyfile_account_address
            assert result["tx"]["value"] == txn_params["value"]
            assert result["tx"]["gas"] == txn_params["gas"]
            assert result["tx"]["maxFeePerGas"] == txn_params["maxFeePerGas"]
            assert (
                result["tx"]["maxPriorityFeePerGas"]
                == txn_params["maxPriorityFeePerGas"]
            )
            assert result["tx"]["nonce"] == txn_params["nonce"]

    @pytest.mark.asyncio
    async def test_eth_send_transaction(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": async_w3.to_wei(3, "gwei"),
            "maxPriorityFeePerGas": async_w3.to_wei(1, "gwei"),
        }

        txn_hash = await async_w3.eth.send_transaction(txn_params)
        txn = await async_w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 21000
        assert txn["maxFeePerGas"] == txn_params["maxFeePerGas"]
        assert txn["maxPriorityFeePerGas"] == txn_params["maxPriorityFeePerGas"]
        assert txn["gasPrice"] <= txn["maxFeePerGas"]  # effective gas price

    @pytest.mark.asyncio
    async def test_eth_send_transaction_default_fees(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
        }

        txn_hash = await async_w3.eth.send_transaction(txn_params)
        txn = await async_w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 21000
        assert is_integer(txn["maxPriorityFeePerGas"])
        assert is_integer(txn["maxFeePerGas"])
        assert txn["gasPrice"] <= txn["maxFeePerGas"]  # effective gas price

    @pytest.mark.asyncio
    async def test_eth_send_transaction_hex_fees(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": hex(250 * 10**9),
            "maxPriorityFeePerGas": hex(2 * 10**9),
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)
        txn = await async_w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 21000
        assert txn["maxFeePerGas"] == 250 * 10**9
        assert txn["maxPriorityFeePerGas"] == 2 * 10**9

    @pytest.mark.asyncio
    async def test_eth_send_transaction_no_gas(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "maxFeePerGas": Wei(250 * 10**9),
            "maxPriorityFeePerGas": Wei(2 * 10**9),
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)
        txn = await async_w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 121000  # 21000 + buffer

    @pytest.mark.asyncio
    async def test_eth_send_transaction_with_gas_price(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": Wei(1),
            "maxFeePerGas": Wei(250 * 10**9),
            "maxPriorityFeePerGas": Wei(2 * 10**9),
        }
        with pytest.raises(TransactionTypeMismatch):
            await async_w3.eth.send_transaction(txn_params)

    @pytest.mark.asyncio
    async def test_eth_send_transaction_no_priority_fee(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": Wei(250 * 10**9),
        }
        with pytest.raises(
            InvalidTransaction, match="maxPriorityFeePerGas must be defined"
        ):
            await async_w3.eth.send_transaction(txn_params)

    @pytest.mark.asyncio
    async def test_eth_send_transaction_no_max_fee(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        maxPriorityFeePerGas = async_w3.to_wei(2, "gwei")
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxPriorityFeePerGas": maxPriorityFeePerGas,
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)
        txn = await async_w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 21000

        block = await async_w3.eth.get_block("latest")
        assert txn["maxFeePerGas"] == maxPriorityFeePerGas + 2 * block["baseFeePerGas"]

    @pytest.mark.asyncio
    async def test_eth_send_transaction_max_fee_less_than_tip(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": Wei(1 * 10**9),
            "maxPriorityFeePerGas": Wei(2 * 10**9),
        }
        with pytest.raises(
            InvalidTransaction, match="maxFeePerGas must be >= maxPriorityFeePerGas"
        ):
            await async_w3.eth.send_transaction(txn_params)

    @pytest.mark.asyncio
    async def test_validation_middleware_chain_id_mismatch(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        wrong_chain_id = 1234567890
        actual_chain_id = await async_w3.eth.chain_id

        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": async_w3.to_wei(2, "gwei"),
            "maxPriorityFeePerGas": async_w3.to_wei(1, "gwei"),
            "chainId": wrong_chain_id,
        }
        with pytest.raises(
            Web3ValidationError,
            match=f"The transaction declared chain ID {wrong_chain_id}, "
            f"but the connected node is on {actual_chain_id}",
        ):
            await async_w3.eth.send_transaction(txn_params)

    @pytest.mark.asyncio
    async def test_ExtraDataToPOAMiddleware(
        self, async_w3: "AsyncWeb3", request_mocker: Type[RequestMocker]
    ) -> None:
        async_w3.middleware_onion.inject(ExtraDataToPOAMiddleware, "poa", layer=0)
        extra_data = f"0x{'ff' * 33}"

        async with request_mocker(
            async_w3,
            mock_results={"eth_getBlockByNumber": {"extraData": extra_data}},
        ):
            block = await async_w3.eth.get_block("latest")

        assert "extraData" not in block
        assert block["proofOfAuthorityData"] == to_bytes(hexstr=extra_data)

        # clean up
        async_w3.middleware_onion.remove("poa")

    @pytest.mark.asyncio
    async def test_async_eth_send_raw_transaction(
        self, async_w3: "AsyncWeb3", keyfile_account_pkey: HexStr
    ) -> None:
        keyfile_account = async_w3.eth.account.from_key(keyfile_account_pkey)
        txn = {
            "chainId": 131277322940537,  # the chainId set for the fixture
            "from": keyfile_account.address,
            "to": keyfile_account.address,
            "value": Wei(0),
            "gas": 21000,
            "nonce": await async_w3.eth.get_transaction_count(
                keyfile_account.address, "pending"
            ),
            "gasPrice": 10**9,
        }
        signed = keyfile_account.sign_transaction(txn)
        txn_hash = await async_w3.eth.send_raw_transaction(signed.raw_transaction)
        assert txn_hash == HexBytes(signed.hash)

    @pytest.mark.asyncio
    async def test_async_sign_and_send_raw_middleware(
        self, async_w3: "AsyncWeb3", keyfile_account_pkey: HexStr
    ) -> None:
        keyfile_account = async_w3.eth.account.from_key(keyfile_account_pkey)
        txn: TxParams = {
            "from": keyfile_account.address,
            "to": keyfile_account.address,
            "value": Wei(0),
            "gas": 21000,
        }
        async_w3.middleware_onion.inject(
            SignAndSendRawMiddlewareBuilder.build(keyfile_account), "signing", layer=0
        )
        txn_hash = await async_w3.eth.send_transaction(txn)
        assert isinstance(txn_hash, HexBytes)

        # clean up
        async_w3.middleware_onion.remove("signing")

    @pytest.mark.asyncio
    async def test_GasPriceStrategyMiddleware(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
        }
        two_gwei_in_wei = async_w3.to_wei(2, "gwei")

        def gas_price_strategy(w3: "Web3", txn: TxParams) -> Wei:
            return two_gwei_in_wei

        async_w3.eth.set_gas_price_strategy(gas_price_strategy)

        txn_hash = await async_w3.eth.send_transaction(txn_params)
        txn = await async_w3.eth.get_transaction(txn_hash)

        assert txn["gasPrice"] == two_gwei_in_wei
        async_w3.eth.set_gas_price_strategy(None)  # reset strategy

    @pytest.mark.asyncio
    async def test_gas_price_strategy_middleware_hex_value(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
        }
        two_gwei_in_wei = async_w3.to_wei(2, "gwei")

        def gas_price_strategy(_w3: "Web3", _txn: TxParams) -> str:
            return hex(two_gwei_in_wei)

        async_w3.eth.set_gas_price_strategy(gas_price_strategy)  # type: ignore

        txn_hash = await async_w3.eth.send_transaction(txn_params)
        txn = await async_w3.eth.get_transaction(txn_hash)

        assert txn["gasPrice"] == two_gwei_in_wei
        async_w3.eth.set_gas_price_strategy(None)  # reset strategy

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "max_fee", (1000000000, None), ids=["with_max_fee", "without_max_fee"]
    )
    async def test_gas_price_from_strategy_bypassed_for_dynamic_fee_txn(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
        max_fee: Wei,
    ) -> None:
        max_priority_fee = async_w3.to_wei(1, "gwei")
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxPriorityFeePerGas": max_priority_fee,
        }
        if max_fee is not None:
            txn_params = assoc(txn_params, "maxFeePerGas", max_fee)

        def gas_price_strategy(w3: "Web3", txn: TxParams) -> Wei:
            return async_w3.to_wei(2, "gwei")

        async_w3.eth.set_gas_price_strategy(gas_price_strategy)

        txn_hash = await async_w3.eth.send_transaction(txn_params)
        txn = await async_w3.eth.get_transaction(txn_hash)

        latest_block = await async_w3.eth.get_block("latest")
        assert (
            txn["maxFeePerGas"] == max_fee
            if max_fee is not None
            else 2 * latest_block["baseFeePerGas"] + max_priority_fee
        )
        assert txn["maxPriorityFeePerGas"] == max_priority_fee
        assert txn["gasPrice"] <= txn["maxFeePerGas"]  # effective gas price

        async_w3.eth.set_gas_price_strategy(None)  # reset strategy

    @pytest.mark.asyncio
    async def test_gas_price_from_strategy_bypassed_for_dynamic_fee_txn_no_tip(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": Wei(1000000000),
        }

        def gas_price_strategy(_w3: "Web3", _txn: TxParams) -> Wei:
            return async_w3.to_wei(2, "gwei")

        async_w3.eth.set_gas_price_strategy(gas_price_strategy)

        with pytest.raises(
            InvalidTransaction, match="maxPriorityFeePerGas must be defined"
        ):
            await async_w3.eth.send_transaction(txn_params)

        async_w3.eth.set_gas_price_strategy(None)  # reset strategy

    @pytest.mark.asyncio
    async def test_eth_estimate_gas(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        gas_estimate = await async_w3.eth.estimate_gas(
            {
                "from": async_keyfile_account_address_dual_type,
                "to": async_keyfile_account_address_dual_type,
                "value": Wei(1),
            }
        )
        assert is_integer(gas_estimate)
        assert gas_estimate > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "params",
        (
            {
                "nonce": 1,  # int
                "balance": 1,  # int
                "code": HexStr("0x"),  # HexStr
                # with state
                "state": {HexStr(f"0x{'00' * 32}"): HexStr(f"0x{'00' * 32}")},
            },
            {
                "nonce": HexStr("0x1"),  # HexStr
                "balance": HexStr("0x1"),  # HexStr
                "code": b"\x00",  # bytes
                # with stateDiff
                "stateDiff": {HexStr(f"0x{'00' * 32}"): HexStr(f"0x{'00' * 32}")},
            },
        ),
    )
    async def test_eth_estimate_gas_with_override_param_type_check(
        self,
        async_w3: "AsyncWeb3",
        async_math_contract: "AsyncContract",
        params: StateOverrideParams,
    ) -> None:
        accounts = await async_w3.eth.accounts
        txn_params: TxParams = {"from": accounts[0]}

        # assert does not raise
        await async_w3.eth.estimate_gas(
            txn_params, None, {async_math_contract.address: params}
        )

    @pytest.mark.asyncio
    async def test_eth_fee_history(self, async_w3: "AsyncWeb3") -> None:
        fee_history = await async_w3.eth.fee_history(1, "latest", [50])
        assert is_list_like(fee_history["baseFeePerGas"])
        assert is_list_like(fee_history["gasUsedRatio"])
        assert is_integer(fee_history["oldestBlock"])
        assert fee_history["oldestBlock"] >= 0
        assert is_list_like(fee_history["reward"])
        if len(fee_history["reward"]) > 0:
            assert is_list_like(fee_history["reward"][0])

    @pytest.mark.asyncio
    async def test_eth_fee_history_with_integer(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        fee_history = await async_w3.eth.fee_history(
            1, async_empty_block["number"], [50]
        )
        assert is_list_like(fee_history["baseFeePerGas"])
        assert is_list_like(fee_history["gasUsedRatio"])
        assert is_integer(fee_history["oldestBlock"])
        assert fee_history["oldestBlock"] >= 0
        assert is_list_like(fee_history["reward"])
        if len(fee_history["reward"]) > 0:
            assert is_list_like(fee_history["reward"][0])

    @pytest.mark.asyncio
    async def test_eth_fee_history_no_reward_percentiles(
        self, async_w3: "AsyncWeb3"
    ) -> None:
        fee_history = await async_w3.eth.fee_history(1, "latest")
        assert is_list_like(fee_history["baseFeePerGas"])
        assert is_list_like(fee_history["gasUsedRatio"])
        assert is_integer(fee_history["oldestBlock"])
        assert fee_history["oldestBlock"] >= 0

    @pytest.mark.asyncio
    async def test_eth_max_priority_fee(self, async_w3: "AsyncWeb3") -> None:
        max_priority_fee = await async_w3.eth.max_priority_fee
        assert is_integer(max_priority_fee)

    @pytest.mark.asyncio
    async def test_eth_max_priority_fee_with_fee_history_calculation(
        self, async_w3: "AsyncWeb3", request_mocker: Type[RequestMocker]
    ) -> None:
        async with request_mocker(
            async_w3,
            mock_errors={RPCEndpoint("eth_maxPriorityFeePerGas"): {}},
            mock_results={RPCEndpoint("eth_feeHistory"): {"reward": [[0]]}},
        ):
            with pytest.warns(
                UserWarning,
                match=(
                    "There was an issue with the method eth_maxPriorityFeePerGas. "
                    "Calculating using eth_feeHistory."
                ),
            ):
                priority_fee = await async_w3.eth.max_priority_fee
                assert is_integer(priority_fee)
                assert priority_fee == PRIORITY_FEE_MIN

    @pytest.mark.asyncio
    async def test_eth_getBlockByHash(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        block = await async_w3.eth.get_block(async_empty_block["hash"])
        assert block["hash"] == async_empty_block["hash"]

    @pytest.mark.asyncio
    async def test_eth_getBlockByHash_not_found(self, async_w3: "AsyncWeb3") -> None:
        with pytest.raises(BlockNotFound):
            await async_w3.eth.get_block(UNKNOWN_HASH)

    @pytest.mark.asyncio
    async def test_eth_getBlockByHash_pending(self, async_w3: "AsyncWeb3") -> None:
        block = await async_w3.eth.get_block("pending")
        assert block["hash"] is None

    @pytest.mark.asyncio
    async def test_eth_getBlockByNumber_with_integer(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        block = await async_w3.eth.get_block(async_empty_block["number"])
        assert block["number"] == async_empty_block["number"]

    @pytest.mark.asyncio
    async def test_eth_getBlockByNumber_latest(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        block = await async_w3.eth.get_block("latest")
        assert block["hash"] is not None

    @pytest.mark.asyncio
    async def test_eth_getBlockByNumber_not_found(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        with pytest.raises(BlockNotFound):
            await async_w3.eth.get_block(BlockNumber(12345))

    @pytest.mark.asyncio
    async def test_eth_getBlockByNumber_pending(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        block = await async_w3.eth.get_block("pending")
        assert block["hash"] is None

    @pytest.mark.asyncio
    async def test_eth_getBlockByNumber_earliest(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        genesis_block = await async_w3.eth.get_block(BlockNumber(0))
        block = await async_w3.eth.get_block("earliest")
        assert block["number"] == 0
        assert block["hash"] == genesis_block["hash"]

    @pytest.mark.asyncio
    async def test_eth_getBlockByNumber_safe(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        block = await async_w3.eth.get_block("safe")
        assert block is not None
        assert isinstance(block["number"], int)

    @pytest.mark.asyncio
    async def test_eth_getBlockByNumber_finalized(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        block = await async_w3.eth.get_block("finalized")
        assert block is not None
        assert isinstance(block["number"], int)

    @pytest.mark.asyncio
    async def test_eth_getBlockReceipts_hash(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        receipts = await async_w3.eth.get_block_receipts(async_empty_block["hash"])
        assert isinstance(receipts, list)

    @pytest.mark.asyncio
    async def test_eth_getBlockReceipts_not_found(self, async_w3: "AsyncWeb3") -> None:
        with pytest.raises(BlockNotFound):
            await async_w3.eth.get_block_receipts(UNKNOWN_HASH)

    @pytest.mark.asyncio
    async def test_eth_getBlockReceipts_with_integer(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        receipts = await async_w3.eth.get_block_receipts(async_empty_block["number"])
        assert isinstance(receipts, list)

    @pytest.mark.asyncio
    async def test_eth_getBlockReceipts_safe(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        receipts = await async_w3.eth.get_block_receipts("safe")
        assert isinstance(receipts, list)

    @pytest.mark.asyncio
    async def test_eth_getBlockReceipts_finalized(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        receipts = await async_w3.eth.get_block_receipts("finalized")
        assert isinstance(receipts, list)

    @pytest.mark.asyncio
    async def test_eth_get_block_by_number_full_transactions(
        self, async_w3: "AsyncWeb3", async_block_with_txn: BlockData
    ) -> None:
        block = await async_w3.eth.get_block(async_block_with_txn["number"], True)
        transaction = cast(TxData, block["transactions"][0])
        assert transaction["hash"] == async_block_with_txn["transactions"][0]

    @pytest.mark.asyncio
    async def test_eth_get_raw_transaction(
        self, async_w3: "AsyncWeb3", mined_txn_hash: HexStr
    ) -> None:
        raw_transaction = await async_w3.eth.get_raw_transaction(mined_txn_hash)
        assert is_bytes(raw_transaction)

    @pytest.mark.asyncio
    async def test_eth_get_raw_transaction_raises_error(
        self, async_w3: "AsyncWeb3"
    ) -> None:
        with pytest.raises(
            TransactionNotFound, match=f"Transaction with hash: '{UNKNOWN_HASH}'"
        ):
            await async_w3.eth.get_raw_transaction(UNKNOWN_HASH)

    @pytest.mark.asyncio
    async def test_eth_get_raw_transaction_by_block(
        self,
        async_w3: "AsyncWeb3",
        async_block_with_txn: BlockData,
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        # eth_getRawTransactionByBlockNumberAndIndex: block identifier
        await async_w3.eth.send_transaction(
            {
                "from": async_keyfile_account_address_dual_type,
                "to": async_keyfile_account_address_dual_type,
                "value": Wei(1),
            }
        )

        async def wait_for_block_with_txn() -> HexBytes:
            while True:
                try:
                    return await async_w3.eth.get_raw_transaction_by_block("latest", 0)
                except TransactionNotFound:
                    await asyncio.sleep(0.1)
                    continue

        raw_txn = await asyncio.wait_for(wait_for_block_with_txn(), timeout=5)
        assert is_bytes(raw_txn)

        # eth_getRawTransactionByBlockNumberAndIndex: block number
        async_block_with_txn_number = async_block_with_txn["number"]
        raw_transaction = await async_w3.eth.get_raw_transaction_by_block(
            async_block_with_txn_number, 0
        )
        assert is_bytes(raw_transaction)

        # eth_getRawTransactionByBlockHashAndIndex: block hash
        async_block_with_txn_hash = async_block_with_txn["hash"]
        raw_transaction = await async_w3.eth.get_raw_transaction_by_block(
            async_block_with_txn_hash, 0
        )
        assert is_bytes(raw_transaction)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("unknown_block_num_or_hash", (1234567899999, UNKNOWN_HASH))
    async def test_eth_get_raw_transaction_by_block_raises_error(
        self, async_w3: "AsyncWeb3", unknown_block_num_or_hash: Union[int, HexBytes]
    ) -> None:
        with pytest.raises(
            TransactionNotFound,
            match=(
                f"Transaction index: 0 on block id: "
                f"{to_hex_if_integer(unknown_block_num_or_hash)!r} "
                f"not found."
            ),
        ):
            await async_w3.eth.get_raw_transaction_by_block(
                unknown_block_num_or_hash, 0
            )

    @pytest.mark.asyncio
    async def test_eth_get_raw_transaction_by_block_raises_error_block_identifier(
        self, async_w3: "AsyncWeb3"
    ) -> None:
        unknown_identifier = "unknown"
        with pytest.raises(
            Web3ValueError,
            match=(
                "Value did not match any of the recognized block identifiers: "
                f"{unknown_identifier}"
            ),
        ):
            # type ignored because we are testing an invalid block identifier
            await async_w3.eth.get_raw_transaction_by_block(unknown_identifier, 0)  # type: ignore  # noqa: E501

    @pytest.mark.asyncio
    async def test_eth_get_balance(self, async_w3: "AsyncWeb3") -> None:
        accounts = await async_w3.eth.accounts
        account = accounts[0]

        with pytest.raises(InvalidAddress):
            await async_w3.eth.get_balance(
                ChecksumAddress(HexAddress(HexStr(account.lower())))
            )

        balance = await async_w3.eth.get_balance(account)

        assert is_integer(balance)
        assert balance >= 0

    @pytest.mark.asyncio
    async def test_eth_get_code(
        self, async_w3: "AsyncWeb3", async_math_contract_address: ChecksumAddress
    ) -> None:
        code = await async_w3.eth.get_code(async_math_contract_address)
        assert isinstance(code, HexBytes)
        assert len(code) > 0

    @pytest.mark.asyncio
    async def test_eth_get_code_invalid_address(
        self,
        async_w3: "AsyncWeb3",
        async_math_contract: "AsyncContract",
    ) -> None:
        with pytest.raises(InvalidAddress):
            await async_w3.eth.get_code(
                ChecksumAddress(HexAddress(HexStr(async_math_contract.address.lower())))
            )

    @pytest.mark.asyncio
    async def test_eth_get_code_with_block_identifier(
        self, async_w3: "AsyncWeb3", async_emitter_contract: "AsyncContract"
    ) -> None:
        block_id = await async_w3.eth.block_number
        code = await async_w3.eth.get_code(async_emitter_contract.address, block_id)
        assert isinstance(code, HexBytes)
        assert len(code) > 0

    @pytest.mark.asyncio
    async def test_eth_create_access_list(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
        async_math_contract: "AsyncContract",
    ) -> None:
        # build txn
        txn = await async_math_contract.functions.incrementCounter(1).build_transaction(
            {"from": async_keyfile_account_address_dual_type}
        )

        # create access list
        response = await async_w3.eth.create_access_list(txn)

        assert is_dict(response)
        access_list = response["accessList"]
        assert len(access_list) > 0
        assert access_list[0]["address"] is not None
        assert is_checksum_address(access_list[0]["address"])
        assert len(access_list[0]["storageKeys"][0]) == 66
        assert int(response["gasUsed"]) >= 0

        # assert the result can be used directly in a transaction dict
        txn["accessList"] = response["accessList"]
        txn["gas"] = response["gasUsed"]

        # send txn with access list
        await async_w3.eth.send_transaction(txn)

    @pytest.mark.asyncio
    async def test_eth_get_transaction_count(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        transaction_count = await async_w3.eth.get_transaction_count(
            async_keyfile_account_address_dual_type
        )
        assert is_integer(transaction_count)
        assert transaction_count >= 0

    @pytest.mark.asyncio
    async def test_eth_call(
        self, async_w3: "AsyncWeb3", async_math_contract: "AsyncContract"
    ) -> None:
        accounts = await async_w3.eth.accounts
        account = accounts[0]

        txn_params = async_math_contract._prepare_transaction(
            abi_element_identifier="add",
            fn_args=(7, 11),
            transaction={"from": account, "to": async_math_contract.address},
        )
        call_result = await async_w3.eth.call(txn_params)
        assert is_string(call_result)
        (result,) = async_w3.codec.decode(["uint256"], call_result)
        assert result == 18

    @pytest.mark.asyncio
    async def test_eth_call_with_override_code(
        self,
        async_w3: "AsyncWeb3",
        async_revert_contract: "AsyncContract",
    ) -> None:
        accounts = await async_w3.eth.accounts
        account = accounts[0]
        txn_params = async_revert_contract._prepare_transaction(
            abi_element_identifier="normalFunction",
            transaction={"from": account, "to": async_revert_contract.address},
        )
        call_result = await async_w3.eth.call(txn_params)
        (result,) = async_w3.codec.decode(["bool"], call_result)
        assert result is True

        # override runtime bytecode: `normalFunction` returns `false`
        override_code = HexStr(
            "0x6080604052348015600f57600080fd5b5060043610603c5760003560e01c8063185c38a4146041578063c06a97cb146049578063d67e4b84146051575b600080fd5b60476071565b005b604f60df565b005b605760e4565b604051808215151515815260200191505060405180910390f35b6040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601b8152602001807f46756e6374696f6e20686173206265656e2072657665727465642e000000000081525060200191505060405180910390fd5b600080fd5b60008090509056fea2646970667358221220bb71e9e9a2e271cd0fbe833524a3ea67df95f25ea13aef5b0a761fa52b538f1064736f6c63430006010033"  # noqa: E501
        )
        call_result = await async_w3.eth.call(
            txn_params,
            "latest",
            {async_revert_contract.address: {"code": override_code}},
        )
        (result,) = async_w3.codec.decode(["bool"], call_result)
        assert result is False

        # test bytes

        bytes_call_result = await async_w3.eth.call(
            txn_params,
            "latest",
            {async_revert_contract.address: {"code": to_bytes(hexstr=override_code)}},
        )
        (bytes_result,) = async_w3.codec.decode(["bool"], bytes_call_result)
        assert bytes_result is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "params",
        (
            {
                "nonce": 1,  # int
                "balance": 1,  # int
                "code": HexStr("0x"),  # HexStr
                # with state
                "state": {HexStr(f"0x{'00' * 32}"): HexStr(f"0x{'00' * 32}")},
            },
            {
                "nonce": HexStr("0x1"),  # HexStr
                "balance": HexStr("0x1"),  # HexStr
                "code": b"\x00",  # bytes
                # with stateDiff
                "stateDiff": {HexStr(f"0x{'00' * 32}"): HexStr(f"0x{'00' * 32}")},
            },
        ),
    )
    async def test_eth_call_with_override_param_type_check(
        self,
        async_w3: "AsyncWeb3",
        async_math_contract: "AsyncContract",
        params: StateOverrideParams,
    ) -> None:
        accounts = await async_w3.eth.accounts
        txn_params: TxParams = {"from": accounts[0]}

        # assert does not raise
        await async_w3.eth.call(
            txn_params, "latest", {async_math_contract.address: params}
        )

    @pytest.mark.asyncio
    async def test_eth_call_with_0_result(
        self, async_w3: "AsyncWeb3", async_math_contract: "AsyncContract"
    ) -> None:
        accounts = await async_w3.eth.accounts
        txn_params = async_math_contract._prepare_transaction(
            abi_element_identifier="add",
            fn_args=(0, 0),
            transaction={"from": accounts[0], "to": async_math_contract.address},
        )
        call_result = await async_w3.eth.call(txn_params)
        assert is_string(call_result)
        (result,) = async_w3.codec.decode(["uint256"], call_result)
        assert result == 0

    @pytest.mark.asyncio
    async def test_eth_call_revert_with_msg(
        self,
        async_w3: "AsyncWeb3",
        async_revert_contract: "AsyncContract",
        async_keyfile_account_address: ChecksumAddress,
    ) -> None:
        txn_params = async_revert_contract._prepare_transaction(
            abi_element_identifier="revertWithMessage",
            transaction={
                "from": async_keyfile_account_address,
                "to": async_revert_contract.address,
            },
        )
        with pytest.raises(
            ContractLogicError, match="execution reverted: Function has been reverted"
        ):
            await async_w3.eth.call(txn_params)

    @pytest.mark.asyncio
    async def test_eth_call_revert_without_msg(
        self,
        async_w3: "AsyncWeb3",
        async_revert_contract: "AsyncContract",
        async_keyfile_account_address: ChecksumAddress,
    ) -> None:
        with pytest.raises(ContractLogicError, match="execution reverted"):
            txn_params = async_revert_contract._prepare_transaction(
                abi_element_identifier="revertWithoutMessage",
                transaction={
                    "from": async_keyfile_account_address,
                    "to": async_revert_contract.address,
                },
            )
            await async_w3.eth.call(txn_params)

    @pytest.mark.asyncio
    async def test_eth_call_revert_custom_error_with_msg(
        self,
        async_w3: "AsyncWeb3",
        async_revert_contract: "AsyncContract",
        async_keyfile_account_address: ChecksumAddress,
    ) -> None:
        data = async_revert_contract.encode_abi(
            abi_element_identifier="UnauthorizedWithMessage",
            args=["You are not authorized"],
        )
        txn_params = async_revert_contract._prepare_transaction(
            abi_element_identifier="customErrorWithMessage",
            transaction={
                "from": async_keyfile_account_address,
                "to": async_revert_contract.address,
            },
        )
        with pytest.raises(ContractCustomError, match=data):
            await async_w3.eth.call(txn_params)

    @pytest.mark.asyncio
    async def test_eth_call_revert_custom_error_without_msg(
        self,
        async_w3: "AsyncWeb3",
        async_revert_contract: "AsyncContract",
        async_keyfile_account_address: ChecksumAddress,
    ) -> None:
        data = async_revert_contract.encode_abi(abi_element_identifier="Unauthorized")
        txn_params = async_revert_contract._prepare_transaction(
            abi_element_identifier="customErrorWithoutMessage",
            transaction={
                "from": async_keyfile_account_address,
                "to": async_revert_contract.address,
            },
        )
        with pytest.raises(ContractCustomError, match=data):
            await async_w3.eth.call(txn_params)

    @pytest.mark.parametrize(
        "panic_error,params",
        (
            ("01", []),
            ("11", []),
            ("12", [0]),
            ("21", [-1]),
            ("22", []),
            ("31", []),
            ("32", []),
            ("41", []),
            ("51", []),
        ),
    )
    @pytest.mark.asyncio
    async def test_contract_panic_errors(
        self,
        async_w3: "AsyncWeb3",
        async_panic_errors_contract: "AsyncContract",
        panic_error: str,
        params: List[Any],
    ) -> None:
        method = getattr(
            async_panic_errors_contract.functions,
            f"errorCode{panic_error}",
        )
        error_msg = PANIC_ERROR_CODES[panic_error]

        with pytest.raises(ContractPanicError, match=re.escape(error_msg)):
            await method(*params).call()

    @pytest.mark.asyncio
    async def test_eth_call_offchain_lookup(
        self,
        async_w3: "AsyncWeb3",
        async_offchain_lookup_contract: "AsyncContract",
        async_keyfile_account_address: ChecksumAddress,
        monkeypatch: "MonkeyPatch",
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            async_offchain_lookup_contract.address
        ).lower()

        async_mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/{OFFCHAIN_LOOKUP_TEST_DATA}.json",  # noqa: E501
            mocked_json_data=WEB3PY_AS_HEXBYTES,
        )
        response_caller = await async_offchain_lookup_contract.caller().testOffchainLookup(  # noqa: E501 type: ignore
            OFFCHAIN_LOOKUP_TEST_DATA
        )
        response_function_call = await async_offchain_lookup_contract.functions.testOffchainLookup(  # noqa: E501 type: ignore
            OFFCHAIN_LOOKUP_TEST_DATA
        ).call()
        assert async_w3.codec.decode(["string"], response_caller)[0] == "web3py"
        assert async_w3.codec.decode(["string"], response_function_call)[0] == "web3py"

    @pytest.mark.asyncio
    async def test_eth_call_offchain_lookup_raises_when_ccip_read_is_disabled(
        self,
        async_w3: "AsyncWeb3",
        async_offchain_lookup_contract: "AsyncContract",
    ) -> None:
        return_data = (
            OFFCHAIN_LOOKUP_4BYTE_DATA
            + abi_encoded_offchain_lookup_contract_address(
                async_w3, async_offchain_lookup_contract
            )
            + OFFCHAIN_LOOKUP_RETURN_DATA
        )
        # test AsyncContractCaller
        with pytest.raises(OffchainLookup) as e:
            await async_offchain_lookup_contract.caller(
                ccip_read_enabled=False
            ).testOffchainLookup(OFFCHAIN_LOOKUP_TEST_DATA)
        assert e.value.data == return_data

        # test AsyncContractFunction call
        with pytest.raises(OffchainLookup) as excinfo:
            await async_offchain_lookup_contract.functions.testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            ).call(ccip_read_enabled=False)
        assert excinfo.value.data == return_data

        # test global flag on the provider
        async_w3.provider.global_ccip_read_enabled = False

        with pytest.raises(OffchainLookup) as exc_info:
            await async_offchain_lookup_contract.functions.testOffchainLookup(  # noqa: E501 type: ignore
                OFFCHAIN_LOOKUP_TEST_DATA
            ).call()
        assert exc_info.value.data == return_data

        async_w3.provider.global_ccip_read_enabled = True  # cleanup

    @pytest.mark.asyncio
    async def test_eth_call_offchain_lookup_call_flag_overrides_provider_flag(
        self,
        async_w3: "AsyncWeb3",
        async_offchain_lookup_contract: "AsyncContract",
        async_keyfile_account_address: ChecksumAddress,
        monkeypatch: "MonkeyPatch",
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            async_offchain_lookup_contract.address
        ).lower()

        async_mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/{OFFCHAIN_LOOKUP_TEST_DATA}.json",  # noqa: E501
            mocked_json_data=WEB3PY_AS_HEXBYTES,
        )

        async_w3.provider.global_ccip_read_enabled = False

        response = await async_offchain_lookup_contract.functions.testOffchainLookup(
            OFFCHAIN_LOOKUP_TEST_DATA
        ).call(ccip_read_enabled=True)
        assert async_w3.codec.decode(["string"], response)[0] == "web3py"

        async_w3.provider.global_ccip_read_enabled = True  # cleanup

    @pytest.mark.asyncio
    @pytest.mark.parametrize("max_redirects", range(-1, 4))
    async def test_eth_call_offchain_lookup_raises_if_max_redirects_is_less_than_4(
        self,
        async_w3: "AsyncWeb3",
        async_offchain_lookup_contract: "AsyncContract",
        max_redirects: int,
    ) -> None:
        default_max_redirects = async_w3.provider.ccip_read_max_redirects

        async_w3.provider.ccip_read_max_redirects = max_redirects
        with pytest.raises(Web3ValueError, match="at least 4"):
            await async_offchain_lookup_contract.caller().testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            )

        async_w3.provider.ccip_read_max_redirects = default_max_redirects  # cleanup

    @pytest.mark.asyncio
    async def test_eth_call_offchain_lookup_raises_for_improperly_formatted_rest_request_response(  # noqa: E501
        self,
        async_w3: "AsyncWeb3",
        async_offchain_lookup_contract: "AsyncContract",
        async_keyfile_account_address: ChecksumAddress,
        monkeypatch: "MonkeyPatch",
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            async_offchain_lookup_contract.address
        ).lower()

        async_mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/{OFFCHAIN_LOOKUP_TEST_DATA}.json",  # noqa: E501
            mocked_json_data=WEB3PY_AS_HEXBYTES,
            json_data_field="not_data",
        )
        with pytest.raises(Web3ValidationError, match="missing 'data' field"):
            await async_offchain_lookup_contract.caller().testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code_non_4xx_error", [100, 300, 500, 600])
    async def test_eth_call_offchain_lookup_tries_next_url_for_non_4xx_error_status_and_tests_POST(  # noqa: E501
        self,
        async_w3: "AsyncWeb3",
        async_offchain_lookup_contract: "AsyncContract",
        async_keyfile_account_address: ChecksumAddress,
        monkeypatch: "MonkeyPatch",
        status_code_non_4xx_error: int,
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            async_offchain_lookup_contract.address
        ).lower()

        # The next url in our test contract doesn't contain '{data}', triggering
        # the POST request logic. The idea here is to return a bad status for the
        # first url (GET) and a success status for the second call (POST) to test
        # both that we move on to the next url with non-4xx status and that the
        # POST logic is also working as expected.
        async_mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/{OFFCHAIN_LOOKUP_TEST_DATA}.json",  # noqa: E501
            mocked_status_code=status_code_non_4xx_error,
            mocked_json_data=WEB3PY_AS_HEXBYTES,
        )
        async_mock_offchain_lookup_request_response(
            monkeypatch,
            http_method="POST",
            mocked_request_url="https://web3.py/gateway",
            mocked_status_code=200,
            mocked_json_data=WEB3PY_AS_HEXBYTES,
            sender=normalized_contract_address,
            calldata=OFFCHAIN_LOOKUP_TEST_DATA,
        )
        response = await async_offchain_lookup_contract.caller().testOffchainLookup(
            OFFCHAIN_LOOKUP_TEST_DATA
        )
        assert async_w3.codec.decode(["string"], response)[0] == "web3py"

    @pytest.mark.asyncio
    async def test_eth_call_offchain_lookup_calls_raise_for_status_for_4xx_status_code(
        self,
        async_w3: "AsyncWeb3",
        async_offchain_lookup_contract: "AsyncContract",
        async_keyfile_account_address: ChecksumAddress,
        monkeypatch: "MonkeyPatch",
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            async_offchain_lookup_contract.address
        ).lower()

        async_mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/{OFFCHAIN_LOOKUP_TEST_DATA}.json",  # noqa: E501
            mocked_status_code=randint(400, 499),
            mocked_json_data=WEB3PY_AS_HEXBYTES,
        )
        with pytest.raises(Exception, match="called raise_for_status\\(\\)"):
            await async_offchain_lookup_contract.caller().testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            )

    @pytest.mark.asyncio
    async def test_eth_call_offchain_lookup_raises_when_all_supplied_urls_fail(
        self,
        async_offchain_lookup_contract: "AsyncContract",
    ) -> None:
        # GET and POST requests should fail since responses are not mocked
        with pytest.raises(
            MultipleFailedRequests, match="Offchain lookup failed for supplied urls"
        ):
            await async_offchain_lookup_contract.caller().testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            )

    @pytest.mark.asyncio
    async def test_eth_call_continuous_offchain_lookup_raises_with_too_many_requests(
        self,
        async_offchain_lookup_contract: "AsyncContract",
        monkeypatch: "MonkeyPatch",
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            async_offchain_lookup_contract.address
        ).lower()

        async_mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/0x.json",  # noqa: E501
        )
        with pytest.raises(TooManyRequests, match="Too many CCIP read redirects"):
            await async_offchain_lookup_contract.caller().continuousOffchainLookup()  # noqa: E501 type: ignore

    @pytest.mark.asyncio
    async def test_eth_simulate_v1(self, async_w3: "AsyncWeb3") -> None:
        simulate_result = await async_w3.eth.simulate_v1(
            {
                "blockStateCalls": [
                    {
                        "blockOverrides": {
                            "baseFeePerGas": Wei(10),
                        },
                        "stateOverrides": {
                            "0xc100000000000000000000000000000000000000": {
                                "balance": Wei(500000000),
                            }
                        },
                        "calls": [
                            {
                                "from": "0xc100000000000000000000000000000000000000",
                                "to": "0xc100000000000000000000000000000000000000",
                                "maxFeePerGas": Wei(10),
                                "maxPriorityFeePerGas": Wei(10),
                            }
                        ],
                    }
                ],
                "validation": True,
                "traceTransfers": True,
            },
            "latest",
        )

        assert len(simulate_result) == 1

        result = simulate_result[0]
        assert result.get("baseFeePerGas") == 10

        calls_result = result.get("calls")
        assert calls_result is not None
        assert len(calls_result) == 1
        call_entry = calls_result[0]

        assert all(
            key in call_entry for key in ("returnData", "logs", "gasUsed", "status")
        )
        assert call_entry["status"] == 1
        assert call_entry["gasUsed"] == int("0x5208", 16)

    @pytest.mark.asyncio
    async def test_async_eth_chain_id(self, async_w3: "AsyncWeb3") -> None:
        chain_id = await async_w3.eth.chain_id
        # chain id value from geth fixture genesis file
        assert chain_id == 131277322940537

    @pytest.mark.asyncio
    async def test_async_eth_get_transaction_receipt_mined(
        self,
        async_w3: "AsyncWeb3",
        async_block_with_txn: BlockData,
        mined_txn_hash: HexStr,
    ) -> None:
        receipt = await async_w3.eth.get_transaction_receipt(mined_txn_hash)
        assert is_dict(receipt)
        assert receipt["blockNumber"] == async_block_with_txn["number"]
        assert receipt["blockHash"] == async_block_with_txn["hash"]
        assert receipt["transactionIndex"] == 0
        assert receipt["transactionHash"] == HexBytes(mined_txn_hash)
        assert is_checksum_address(receipt["to"])
        assert receipt["from"] is not None
        assert is_checksum_address(receipt["from"])

        effective_gas_price = receipt["effectiveGasPrice"]
        assert isinstance(effective_gas_price, int)
        assert effective_gas_price > 0

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_get_transaction_receipt_unmined(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_hash = await async_w3.eth.send_transaction(
            {
                "from": async_keyfile_account_address_dual_type,
                "to": async_keyfile_account_address_dual_type,
                "value": Wei(1),
                "gas": 21000,
                "maxFeePerGas": async_w3.to_wei(3, "gwei"),
                "maxPriorityFeePerGas": async_w3.to_wei(1, "gwei"),
            }
        )
        with pytest.raises(TransactionNotFound):
            await async_w3.eth.get_transaction_receipt(txn_hash)

    @pytest.mark.asyncio
    async def test_async_eth_get_transaction_receipt_with_log_entry(
        self,
        async_w3: "AsyncWeb3",
        async_block_with_txn_with_log: BlockData,
        async_emitter_contract: "AsyncContract",
        txn_hash_with_log: HexStr,
    ) -> None:
        receipt = await async_w3.eth.wait_for_transaction_receipt(txn_hash_with_log)
        assert is_dict(receipt)
        assert receipt["blockNumber"] == async_block_with_txn_with_log["number"]
        assert receipt["blockHash"] == async_block_with_txn_with_log["hash"]
        assert receipt["transactionIndex"] == 0
        assert receipt["transactionHash"] == HexBytes(txn_hash_with_log)

        assert len(receipt["logs"]) == 1
        log_entry = receipt["logs"][0]

        assert log_entry["blockNumber"] == async_block_with_txn_with_log["number"]
        assert log_entry["blockHash"] == async_block_with_txn_with_log["hash"]
        assert log_entry["logIndex"] == 0
        assert is_same_address(log_entry["address"], async_emitter_contract.address)
        assert log_entry["transactionIndex"] == 0
        assert log_entry["transactionHash"] == HexBytes(txn_hash_with_log)

    @pytest.mark.asyncio
    async def test_async_eth_wait_for_transaction_receipt_mined(
        self,
        async_w3: "AsyncWeb3",
        async_block_with_txn: BlockData,
        mined_txn_hash: HexStr,
    ) -> None:
        receipt = await async_w3.eth.wait_for_transaction_receipt(mined_txn_hash)
        assert is_dict(receipt)
        assert receipt["blockNumber"] == async_block_with_txn["number"]
        assert receipt["blockHash"] == async_block_with_txn["hash"]
        assert receipt["transactionIndex"] == 0
        assert receipt["transactionHash"] == HexBytes(mined_txn_hash)
        assert is_checksum_address(receipt["to"])
        assert receipt["from"] is not None
        assert is_checksum_address(receipt["from"])

        effective_gas_price = receipt["effectiveGasPrice"]
        assert isinstance(effective_gas_price, int)
        assert effective_gas_price > 0

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_wait_for_transaction_receipt_unmined(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_hash = await async_w3.eth.send_transaction(
            {
                "from": async_keyfile_account_address_dual_type,
                "to": async_keyfile_account_address_dual_type,
                "value": Wei(1),
                "gas": 21000,
                "maxFeePerGas": async_w3.to_wei(3, "gwei"),
                "maxPriorityFeePerGas": async_w3.to_wei(1, "gwei"),
            }
        )

        timeout = 0.01
        with pytest.raises(TimeExhausted) as exc_info:
            await async_w3.eth.wait_for_transaction_receipt(txn_hash, timeout=timeout)

        assert (_ in str(exc_info) for _ in [repr(txn_hash), timeout])

    @pytest.mark.asyncio
    async def test_async_eth_wait_for_transaction_receipt_with_log_entry(
        self,
        async_w3: "AsyncWeb3",
        async_block_with_txn_with_log: BlockData,
        async_emitter_contract: "AsyncContract",
        txn_hash_with_log: HexStr,
    ) -> None:
        receipt = await async_w3.eth.wait_for_transaction_receipt(txn_hash_with_log)
        assert is_dict(receipt)
        assert receipt["blockNumber"] == async_block_with_txn_with_log["number"]
        assert receipt["blockHash"] == async_block_with_txn_with_log["hash"]
        assert receipt["transactionIndex"] == 0
        assert receipt["transactionHash"] == HexBytes(txn_hash_with_log)

        assert len(receipt["logs"]) == 1
        log_entry = receipt["logs"][0]

        assert log_entry["blockNumber"] == async_block_with_txn_with_log["number"]
        assert log_entry["blockHash"] == async_block_with_txn_with_log["hash"]
        assert log_entry["logIndex"] == 0
        assert is_same_address(log_entry["address"], async_emitter_contract.address)
        assert log_entry["transactionIndex"] == 0
        assert log_entry["transactionHash"] == HexBytes(txn_hash_with_log)

    @pytest.mark.asyncio
    async def test_async_eth_accounts(self, async_w3: "AsyncWeb3") -> None:
        accounts = await async_w3.eth.accounts
        assert is_list_like(accounts)
        assert len(accounts) != 0
        assert all(is_checksum_address(account) for account in accounts)

    @pytest.mark.asyncio
    async def test_async_eth_blob_base_fee(self, async_w3: "AsyncWeb3") -> None:
        blob_base_fee = await async_w3.eth.blob_base_fee
        assert is_integer(blob_base_fee)
        assert blob_base_fee >= 0

    @pytest.mark.asyncio
    async def test_async_eth_get_logs_without_logs(
        self, async_w3: "AsyncWeb3", async_block_with_txn_with_log: BlockData
    ) -> None:
        # Test with block range

        filter_params: FilterParams = {
            "fromBlock": BlockNumber(0),
            "toBlock": BlockNumber(async_block_with_txn_with_log["number"] - 1),
        }
        result = await async_w3.eth.get_logs(filter_params)
        assert len(result) == 0

        # the range is wrong
        filter_params = {
            "fromBlock": async_block_with_txn_with_log["number"],
            "toBlock": BlockNumber(async_block_with_txn_with_log["number"] - 1),
        }
        with pytest.raises(Web3RPCError):
            result = await async_w3.eth.get_logs(filter_params)

        # Test with `address`

        # filter with other address
        filter_params = {
            "fromBlock": BlockNumber(0),
            "address": UNKNOWN_ADDRESS,
        }
        result = await async_w3.eth.get_logs(filter_params)
        assert len(result) == 0

        # Test with multiple `address`

        # filter with other address
        filter_params = {
            "fromBlock": BlockNumber(0),
            "address": [UNKNOWN_ADDRESS, UNKNOWN_ADDRESS],
        }
        result = await async_w3.eth.get_logs(filter_params)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_async_eth_get_logs_with_logs(
        self,
        async_w3: "AsyncWeb3",
        async_block_with_txn_with_log: BlockData,
        async_emitter_contract_address: ChecksumAddress,
        txn_hash_with_log: HexStr,
    ) -> None:
        # Test with block range

        # the range includes the block where the log resides in
        filter_params: FilterParams = {
            "fromBlock": async_block_with_txn_with_log["number"],
            "toBlock": async_block_with_txn_with_log["number"],
        }
        result = await async_w3.eth.get_logs(filter_params)
        assert_contains_log(
            result,
            async_block_with_txn_with_log,
            async_emitter_contract_address,
            txn_hash_with_log,
        )

        # specify only `from_block`. by default `to_block` should be 'latest'
        filter_params = {
            "fromBlock": BlockNumber(0),
        }
        result = await async_w3.eth.get_logs(filter_params)
        assert_contains_log(
            result,
            async_block_with_txn_with_log,
            async_emitter_contract_address,
            txn_hash_with_log,
        )

        # Test with `address`

        # filter with emitter_contract.address
        filter_params = {
            "fromBlock": BlockNumber(0),
            "address": async_emitter_contract_address,
        }
        result = await async_w3.eth.get_logs(filter_params)
        assert_contains_log(
            result,
            async_block_with_txn_with_log,
            async_emitter_contract_address,
            txn_hash_with_log,
        )

    @pytest.mark.asyncio
    async def test_async_eth_get_logs_with_logs_topic_args(
        self,
        async_w3: "AsyncWeb3",
        async_block_with_txn_with_log: BlockData,
        async_emitter_contract_address: ChecksumAddress,
        txn_hash_with_log: HexStr,
    ) -> None:
        # Test with None event sig

        filter_params: FilterParams = {
            "fromBlock": BlockNumber(0),
            "topics": [
                None,
                HexStr(
                    "0x000000000000000000000000000000000000000000000000000000000000d431"
                ),
            ],
        }

        result = await async_w3.eth.get_logs(filter_params)
        assert_contains_log(
            result,
            async_block_with_txn_with_log,
            async_emitter_contract_address,
            txn_hash_with_log,
        )

        # Test with None indexed arg
        filter_params = {
            "fromBlock": BlockNumber(0),
            "topics": [
                HexStr(
                    "0x057bc32826fbe161da1c110afcdcae7c109a8b69149f727fc37a603c60ef94ca"
                ),
                None,
            ],
        }
        result = await async_w3.eth.get_logs(filter_params)
        assert_contains_log(
            result,
            async_block_with_txn_with_log,
            async_emitter_contract_address,
            txn_hash_with_log,
        )

    @pytest.mark.asyncio
    async def test_async_eth_get_logs_with_logs_none_topic_args(
        self, async_w3: "AsyncWeb3"
    ) -> None:
        # Test with None overflowing
        filter_params: FilterParams = {
            "fromBlock": BlockNumber(0),
            "topics": [None, None, None, None],
        }
        result = await async_w3.eth.get_logs(filter_params)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_async_eth_syncing(self, async_w3: "AsyncWeb3") -> None:
        syncing = await async_w3.eth.syncing

        assert is_boolean(syncing) or is_dict(syncing)

        if is_boolean(syncing):
            assert syncing is False
        elif is_dict(syncing):
            sync_dict = cast(SyncStatus, syncing)
            assert "startingBlock" in sync_dict
            assert "currentBlock" in sync_dict
            assert "highestBlock" in sync_dict

            assert is_integer(sync_dict["startingBlock"])
            assert is_integer(sync_dict["currentBlock"])
            assert is_integer(sync_dict["highestBlock"])

    @pytest.mark.asyncio
    async def test_async_eth_get_storage_at(
        self, async_w3: "AsyncWeb3", async_storage_contract: "AsyncContract"
    ) -> None:
        async_storage_contract_address = async_storage_contract.address

        slot_0 = await async_w3.eth.get_storage_at(async_storage_contract_address, 0)
        assert slot_0 == HexBytes(f"0x{'00' * 32}")

        slot_1 = await async_w3.eth.get_storage_at(async_storage_contract_address, 1)
        assert slot_1 == HexBytes(f"0x{'00' * 31}01")

        slot_2 = await async_w3.eth.get_storage_at(async_storage_contract_address, 2)
        assert slot_2 == HexBytes(f"0x{'00' * 31}02")

        slot_3 = await async_w3.eth.get_storage_at(async_storage_contract_address, 3)
        assert slot_3 == HexBytes(
            "0x746872656500000000000000000000000000000000000000000000000000000a"
        )
        assert bytes(slot_3[:5]) == b"three"

        slot_4 = await async_w3.eth.get_storage_at(async_storage_contract_address, 4)
        assert slot_4 == HexBytes(
            "0x666f757200000000000000000000000000000000000000000000000000000008"
        )
        assert bytes(slot_4[:4]) == b"four"

    @pytest.mark.asyncio
    @pytest.mark.xfail
    async def test_async_eth_get_storage_at_ens_name(
        self, async_w3: "AsyncWeb3", async_storage_contract: "AsyncContract"
    ) -> None:
        with ens_addresses(async_w3, {"storage.eth": async_storage_contract.address}):
            storage = await async_w3.eth.get_storage_at(ENS("storage.eth"), 1)
            assert storage == HexBytes(f"0x{'00' * 31}01")

    @pytest.mark.asyncio
    async def test_async_eth_get_storage_at_invalid_address(
        self, async_w3: "AsyncWeb3"
    ) -> None:
        accounts = await async_w3.eth.accounts
        with pytest.raises(InvalidAddress):
            await async_w3.eth.get_storage_at(
                ChecksumAddress(HexAddress(HexStr(accounts[0].lower()))), 0
            )

    def test_async_provider_default_account(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        current_default_account = async_w3.eth.default_account

        # check setter
        async_w3.eth.default_account = async_keyfile_account_address_dual_type
        default_account = async_w3.eth.default_account
        assert default_account == async_keyfile_account_address_dual_type

        # reset to default
        async_w3.eth.default_account = current_default_account

    def test_async_provider_default_block(
        self,
        async_w3: "AsyncWeb3",
    ) -> None:
        # check defaults to 'latest'
        default_block = async_w3.eth.default_block
        assert default_block == "latest"

        # check setter
        async_w3.eth.default_block = BlockNumber(12345)
        default_block = async_w3.eth.default_block
        assert default_block == BlockNumber(12345)

        # reset to default
        async_w3.eth.default_block = "latest"

    @pytest.mark.asyncio
    async def test_eth_getBlockTransactionCountByHash_async_empty_block(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        transaction_count = await async_w3.eth.get_block_transaction_count(
            async_empty_block["hash"]
        )

        assert is_integer(transaction_count)
        assert transaction_count == 0

    @pytest.mark.asyncio
    async def test_eth_getBlockTransactionCountByNumber_async_empty_block(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        transaction_count = await async_w3.eth.get_block_transaction_count(
            async_empty_block["number"]
        )

        assert is_integer(transaction_count)
        assert transaction_count == 0

    @pytest.mark.asyncio
    async def test_eth_getBlockTransactionCountByHash_block_with_txn(
        self, async_w3: "AsyncWeb3", async_block_with_txn: BlockData
    ) -> None:
        transaction_count = await async_w3.eth.get_block_transaction_count(
            async_block_with_txn["hash"]
        )

        assert is_integer(transaction_count)
        assert transaction_count >= 1

    @pytest.mark.asyncio
    async def test_eth_getUncleCountByBlockHash(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        uncle_count = await async_w3.eth.get_uncle_count(async_empty_block["hash"])

        assert is_integer(uncle_count)
        assert uncle_count == 0

    @pytest.mark.asyncio
    async def test_eth_getUncleCountByBlockNumber(
        self, async_w3: "AsyncWeb3", async_empty_block: BlockData
    ) -> None:
        uncle_count = await async_w3.eth.get_uncle_count(async_empty_block["number"])

        assert is_integer(uncle_count)
        assert uncle_count == 0

    @pytest.mark.asyncio
    async def test_eth_getBlockTransactionCountByNumber_block_with_txn(
        self, async_w3: "AsyncWeb3", async_block_with_txn: BlockData
    ) -> None:
        transaction_count = await async_w3.eth.get_block_transaction_count(
            async_block_with_txn["number"]
        )

        assert is_integer(transaction_count)
        assert transaction_count >= 1

    @pytest.mark.asyncio
    async def test_async_eth_sign(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        signature = await async_w3.eth.sign(
            async_keyfile_account_address_dual_type,
            text="Message tö sign. Longer than hash!",
        )
        assert is_bytes(signature)
        assert len(signature) == 32 + 32 + 1

        # test other formats
        hexsign = await async_w3.eth.sign(
            async_keyfile_account_address_dual_type,
            hexstr=HexStr(
                "0x4d6573736167652074c3b6207369676e2e204c6f6e676572207468616e206861736821"  # noqa: E501
            ),
        )
        assert hexsign == signature

        intsign = await async_w3.eth.sign(
            async_keyfile_account_address_dual_type,
            0x4D6573736167652074C3B6207369676E2E204C6F6E676572207468616E206861736821,
        )
        assert intsign == signature

        bytessign = await async_w3.eth.sign(
            async_keyfile_account_address_dual_type,
            b"Message t\xc3\xb6 sign. Longer than hash!",
        )
        assert bytessign == signature

        new_signature = await async_w3.eth.sign(
            async_keyfile_account_address_dual_type,
            text="different message is different",
        )
        assert new_signature != signature

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Async middleware to convert ENS names to addresses is missing"
    )
    async def test_async_eth_sign_ens_names(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        with ens_addresses(
            async_w3, {"unlocked-acct.eth": async_keyfile_account_address_dual_type}
        ):
            signature = await async_w3.eth.sign(
                ENS("unlocked-acct.eth"), text="Message tö sign. Longer than hash!"
            )
            assert is_bytes(signature)
            assert len(signature) == 32 + 32 + 1

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_replace_transaction_legacy(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": async_w3.to_wei(1, "gwei"),
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)

        txn_params["gasPrice"] = async_w3.to_wei(2, "gwei")
        replace_txn_hash = await async_w3.eth.replace_transaction(txn_hash, txn_params)
        replace_txn = await async_w3.eth.get_transaction(replace_txn_hash)

        assert is_same_address(
            replace_txn["from"], cast(ChecksumAddress, txn_params["from"])
        )
        assert is_same_address(
            replace_txn["to"], cast(ChecksumAddress, txn_params["to"])
        )
        assert replace_txn["value"] == 1
        assert replace_txn["gas"] == 21000
        assert replace_txn["gasPrice"] == txn_params["gasPrice"]

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_replace_transaction(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        two_gwei_in_wei = async_w3.to_wei(2, "gwei")
        three_gwei_in_wei = async_w3.to_wei(3, "gwei")

        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": two_gwei_in_wei,
            "maxPriorityFeePerGas": async_w3.to_wei(1, "gwei"),
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)

        txn_params["maxFeePerGas"] = three_gwei_in_wei
        txn_params["maxPriorityFeePerGas"] = two_gwei_in_wei

        replace_txn_hash = await async_w3.eth.replace_transaction(txn_hash, txn_params)
        replace_txn = await async_w3.eth.get_transaction(replace_txn_hash)

        assert is_same_address(
            replace_txn["from"], cast(ChecksumAddress, txn_params["from"])
        )
        assert is_same_address(
            replace_txn["to"], cast(ChecksumAddress, txn_params["to"])
        )
        assert replace_txn["value"] == 1
        assert replace_txn["gas"] == 21000
        assert replace_txn["maxFeePerGas"] == three_gwei_in_wei
        assert replace_txn["maxPriorityFeePerGas"] == two_gwei_in_wei

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_replace_transaction_underpriced(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        # Note: `underpriced transaction` error is only consistent with
        # ``txpool.nolocals`` flag as of Geth ``v1.15.4``.
        # https://github.com/ethereum/web3.py/pull/3636
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": async_w3.to_wei(3, "gwei"),
            "maxPriorityFeePerGas": async_w3.to_wei(2, "gwei"),
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)

        one_gwei_in_wei = async_w3.to_wei(1, "gwei")
        txn_params["maxFeePerGas"] = one_gwei_in_wei
        txn_params["maxPriorityFeePerGas"] = one_gwei_in_wei

        with pytest.raises(Web3RPCError, match="replacement transaction underpriced"):
            await async_w3.eth.replace_transaction(txn_hash, txn_params)

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_replace_transaction_non_existing_transaction(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": async_w3.to_wei(3, "gwei"),
            "maxPriorityFeePerGas": async_w3.to_wei(1, "gwei"),
        }
        with pytest.raises(TransactionNotFound):
            await async_w3.eth.replace_transaction(
                HexStr(
                    "0x98e8cc09b311583c5079fa600f6c2a3bea8611af168c52e4b60b5b243a441997"
                ),
                txn_params,
            )

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_replace_transaction_already_mined(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": async_w3.to_wei(2, "gwei"),
            "maxPriorityFeePerGas": async_w3.to_wei(1, "gwei"),
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)
        await async_w3.eth.wait_for_transaction_receipt(txn_hash, timeout=10)

        txn_params["maxFeePerGas"] = async_w3.to_wei(3, "gwei")
        txn_params["maxPriorityFeePerGas"] = async_w3.to_wei(2, "gwei")
        with pytest.raises(Web3ValueError, match="Supplied transaction with hash"):
            await async_w3.eth.replace_transaction(txn_hash, txn_params)

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_replace_transaction_incorrect_nonce(
        self, async_w3: "AsyncWeb3", async_keyfile_account_address: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address,
            "to": async_keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": async_w3.to_wei(2, "gwei"),
            "maxPriorityFeePerGas": async_w3.to_wei(1, "gwei"),
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)
        txn = await async_w3.eth.get_transaction(txn_hash)

        txn_params["maxFeePerGas"] = async_w3.to_wei(3, "gwei")
        txn_params["maxPriorityFeePerGas"] = async_w3.to_wei(2, "gwei")
        txn_params["nonce"] = Nonce(txn["nonce"] + 1)
        with pytest.raises(Web3ValueError):
            await async_w3.eth.replace_transaction(txn_hash, txn_params)

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_replace_transaction_gas_price_too_low(
        self,
        async_w3: "AsyncWeb3",
        async_keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address_dual_type,
            "to": async_keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": async_w3.to_wei(2, "gwei"),
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)

        txn_params["gasPrice"] = async_w3.to_wei(1, "gwei")
        with pytest.raises(Web3ValueError):
            await async_w3.eth.replace_transaction(txn_hash, txn_params)

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_replace_transaction_gas_price_defaulting_minimum(
        self, async_w3: "AsyncWeb3", async_keyfile_account_address: ChecksumAddress
    ) -> None:
        gas_price = async_w3.to_wei(1, "gwei")

        txn_params: TxParams = {
            "from": async_keyfile_account_address,
            "to": async_keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": gas_price,
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)

        txn_params.pop("gasPrice")
        replace_txn_hash = await async_w3.eth.replace_transaction(txn_hash, txn_params)
        replace_txn = await async_w3.eth.get_transaction(replace_txn_hash)

        assert replace_txn["gasPrice"] == math.ceil(
            gas_price * 1.125
        )  # minimum gas price

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_replace_transaction_gas_price_defaulting_strategy_higher(
        self, async_w3: "AsyncWeb3", async_keyfile_account_address: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": async_keyfile_account_address,
            "to": async_keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": async_w3.to_wei(1, "gwei"),
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)

        two_gwei_in_wei = async_w3.to_wei(2, "gwei")

        def higher_gas_price_strategy(_async_w3: "AsyncWeb3", _txn: TxParams) -> Wei:
            return two_gwei_in_wei

        async_w3.eth.set_gas_price_strategy(higher_gas_price_strategy)

        txn_params.pop("gasPrice")
        replace_txn_hash = await async_w3.eth.replace_transaction(txn_hash, txn_params)
        replace_txn = await async_w3.eth.get_transaction(replace_txn_hash)
        assert (
            replace_txn["gasPrice"] == two_gwei_in_wei
        )  # Strategy provides higher gas price
        async_w3.eth.set_gas_price_strategy(None)  # reset strategy

    @flaky_geth_dev_mining
    @pytest.mark.asyncio
    async def test_async_eth_replace_transaction_gas_price_defaulting_strategy_lower(
        self, async_w3: "AsyncWeb3", async_keyfile_account_address: ChecksumAddress
    ) -> None:
        gas_price = async_w3.to_wei(2, "gwei")
        txn_params: TxParams = {
            "from": async_keyfile_account_address,
            "to": async_keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": gas_price,
        }
        txn_hash = await async_w3.eth.send_transaction(txn_params)

        def lower_gas_price_strategy(async_w3: "AsyncWeb3", txn: TxParams) -> Wei:
            return async_w3.to_wei(1, "gwei")

        async_w3.eth.set_gas_price_strategy(lower_gas_price_strategy)

        txn_params.pop("gasPrice")
        replace_txn_hash = await async_w3.eth.replace_transaction(txn_hash, txn_params)
        replace_txn = await async_w3.eth.get_transaction(replace_txn_hash)
        # Strategy provides lower gas price - minimum preferred
        assert replace_txn["gasPrice"] == math.ceil(gas_price * 1.125)
        async_w3.eth.set_gas_price_strategy(None)  # reset strategy

    @pytest.mark.asyncio
    async def test_async_eth_new_filter(self, async_w3: "AsyncWeb3") -> None:
        filter = await async_w3.eth.filter({})

        changes = await async_w3.eth.get_filter_changes(filter.filter_id)
        assert is_list_like(changes)
        assert not changes

        logs = await async_w3.eth.get_filter_logs(filter.filter_id)
        assert is_list_like(logs)
        assert not logs

        result = await async_w3.eth.uninstall_filter(filter.filter_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_async_eth_new_block_filter(self, async_w3: "AsyncWeb3") -> None:
        filter = await async_w3.eth.filter("latest")
        assert is_string(filter.filter_id)

        changes = await async_w3.eth.get_filter_changes(filter.filter_id)
        assert is_list_like(changes)

        result = await async_w3.eth.uninstall_filter(filter.filter_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_async_eth_new_pending_transaction_filter(
        self, async_w3: "AsyncWeb3"
    ) -> None:
        filter = await async_w3.eth.filter("pending")
        assert is_string(filter.filter_id)

        changes = await async_w3.eth.get_filter_changes(filter.filter_id)
        assert is_list_like(changes)
        assert not changes

        result = await async_w3.eth.uninstall_filter(filter.filter_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_async_eth_uninstall_filter(self, async_w3: "AsyncWeb3") -> None:
        filter = await async_w3.eth.filter({})
        assert is_string(filter.filter_id)

        success = await async_w3.eth.uninstall_filter(filter.filter_id)
        assert success is True

        failure = await async_w3.eth.uninstall_filter(filter.filter_id)
        assert failure is False


class EthModuleTest:
    def test_eth_syncing(self, w3: "Web3") -> None:
        syncing = w3.eth.syncing

        assert is_boolean(syncing) or is_dict(syncing)

        if is_boolean(syncing):
            assert syncing is False
        elif is_dict(syncing):
            sync_dict = cast(SyncStatus, syncing)
            assert "startingBlock" in sync_dict
            assert "currentBlock" in sync_dict
            assert "highestBlock" in sync_dict

            assert is_integer(sync_dict["startingBlock"])
            assert is_integer(sync_dict["currentBlock"])
            assert is_integer(sync_dict["highestBlock"])

    def test_eth_chain_id(self, w3: "Web3") -> None:
        chain_id = w3.eth.chain_id
        # chain id value from geth fixture genesis file
        assert chain_id == 131277322940537

    def test_eth_fee_history(self, w3: "Web3") -> None:
        fee_history = w3.eth.fee_history(1, "latest", [50])
        assert is_list_like(fee_history["baseFeePerGas"])
        assert is_list_like(fee_history["gasUsedRatio"])
        assert is_integer(fee_history["oldestBlock"])
        assert fee_history["oldestBlock"] >= 0
        assert is_list_like(fee_history["reward"])
        if len(fee_history["reward"]) > 0:
            assert is_list_like(fee_history["reward"][0])

    def test_eth_fee_history_with_integer(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        fee_history = w3.eth.fee_history(1, empty_block["number"], [50])
        assert is_list_like(fee_history["baseFeePerGas"])
        assert is_list_like(fee_history["gasUsedRatio"])
        assert is_integer(fee_history["oldestBlock"])
        assert fee_history["oldestBlock"] >= 0
        assert is_list_like(fee_history["reward"])
        if len(fee_history["reward"]) > 0:
            assert is_list_like(fee_history["reward"][0])

    def test_eth_fee_history_no_reward_percentiles(self, w3: "Web3") -> None:
        fee_history = w3.eth.fee_history(1, "latest")
        assert is_list_like(fee_history["baseFeePerGas"])
        assert is_list_like(fee_history["gasUsedRatio"])
        assert is_integer(fee_history["oldestBlock"])
        assert fee_history["oldestBlock"] >= 0

    def test_eth_gas_price(self, w3: "Web3") -> None:
        gas_price = w3.eth.gas_price
        assert is_integer(gas_price)
        assert gas_price > 0

    def test_eth_max_priority_fee(self, w3: "Web3") -> None:
        max_priority_fee = w3.eth.max_priority_fee
        assert is_integer(max_priority_fee)

    def test_eth_max_priority_fee_with_fee_history_calculation(
        self, w3: "Web3", request_mocker: Type[RequestMocker]
    ) -> None:
        with request_mocker(
            w3,
            mock_errors={RPCEndpoint("eth_maxPriorityFeePerGas"): {}},
            mock_results={RPCEndpoint("eth_feeHistory"): {"reward": [[0]]}},
        ):
            with pytest.warns(
                UserWarning,
                match=(
                    "There was an issue with the method eth_maxPriorityFeePerGas. "
                    "Calculating using eth_feeHistory."
                ),
            ):
                max_priority_fee = w3.eth.max_priority_fee
                assert is_integer(max_priority_fee)
                assert max_priority_fee == PRIORITY_FEE_MIN

    def test_eth_accounts(self, w3: "Web3") -> None:
        accounts = w3.eth.accounts
        assert is_list_like(accounts)
        assert len(accounts) != 0
        assert all(is_checksum_address(account) for account in accounts)

    def test_eth_blob_base_fee(self, w3: "Web3") -> None:
        blob_base_fee = w3.eth.blob_base_fee
        assert is_integer(blob_base_fee)
        assert blob_base_fee >= 0

    def test_eth_block_number(self, w3: "Web3") -> None:
        block_number = w3.eth.block_number
        assert is_integer(block_number)
        assert block_number >= 0

    def test_eth_get_block_number(self, w3: "Web3") -> None:
        block_number = w3.eth.get_block_number()
        assert is_integer(block_number)
        assert block_number >= 0

    def test_eth_get_balance(self, w3: "Web3") -> None:
        account = w3.eth.accounts[0]

        with pytest.raises(InvalidAddress):
            w3.eth.get_balance(ChecksumAddress(HexAddress(HexStr(account.lower()))))

        balance = w3.eth.get_balance(account)

        assert is_integer(balance)
        assert balance >= 0

    def test_eth_get_balance_with_block_identifier(self, w3: "Web3") -> None:
        miner_address = w3.eth.get_block(1)["miner"]
        balance_post_genesis = w3.eth.get_balance(miner_address, 1)
        later_balance = w3.eth.get_balance(miner_address, "latest")

        assert is_integer(balance_post_genesis)
        assert is_integer(later_balance)
        assert later_balance > balance_post_genesis

    @pytest.mark.parametrize(
        "address, expect_success",
        [("test-address.eth", True), ("not-an-address.eth", False)],
    )
    def test_eth_get_balance_with_ens_name(
        self, w3: "Web3", address: ChecksumAddress, expect_success: bool
    ) -> None:
        with ens_addresses(w3, {"test-address.eth": w3.eth.accounts[0]}):
            if expect_success:
                balance = w3.eth.get_balance(address)
                assert is_integer(balance)
                assert balance >= 0
            else:
                with pytest.raises(NameNotFound):
                    w3.eth.get_balance(address)

    def test_eth_get_storage_at(self, w3: "Web3", storage_contract: "Contract") -> None:
        storage_contract_address = storage_contract.address

        slot_0 = w3.eth.get_storage_at(storage_contract_address, 0)
        assert slot_0 == HexBytes(f"0x{'00' * 32}")

        slot_1 = w3.eth.get_storage_at(storage_contract_address, 1)
        assert slot_1 == HexBytes(f"0x{'00' * 31}01")

        slot_2 = w3.eth.get_storage_at(storage_contract_address, 2)
        assert slot_2 == HexBytes(f"0x{'00' * 31}02")

        slot_3 = w3.eth.get_storage_at(storage_contract_address, 3)
        assert slot_3 == HexBytes(
            "0x746872656500000000000000000000000000000000000000000000000000000a"
        )
        assert bytes(slot_3[:5]) == b"three"

        slot_4 = w3.eth.get_storage_at(storage_contract_address, 4)
        assert slot_4 == HexBytes(
            "0x666f757200000000000000000000000000000000000000000000000000000008"
        )
        assert bytes(slot_4[:4]) == b"four"

    def test_eth_get_storage_at_ens_name(
        self, w3: "Web3", storage_contract: "Contract"
    ) -> None:
        with ens_addresses(w3, {"storage.eth": storage_contract.address}):
            storage = w3.eth.get_storage_at(ENS("storage.eth"), 1)
            assert storage == HexBytes(f"0x{'00' * 31}01")

    def test_eth_get_storage_at_invalid_address(self, w3: "Web3") -> None:
        account = w3.eth.accounts[0]
        with pytest.raises(InvalidAddress):
            w3.eth.get_storage_at(
                ChecksumAddress(HexAddress(HexStr(account.lower()))), 0
            )

    def test_eth_get_transaction_count(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        transaction_count = w3.eth.get_transaction_count(
            keyfile_account_address_dual_type
        )
        assert is_integer(transaction_count)
        assert transaction_count >= 0

    def test_eth_get_transaction_count_ens_name(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        with ens_addresses(
            w3, {"unlocked-acct-dual-type.eth": keyfile_account_address_dual_type}
        ):
            transaction_count = w3.eth.get_transaction_count(
                ENS("unlocked-acct-dual-type.eth")
            )
            assert is_integer(transaction_count)
            assert transaction_count >= 0

    def test_eth_get_transaction_count_invalid_address(self, w3: "Web3") -> None:
        account = w3.eth.accounts[0]
        with pytest.raises(InvalidAddress):
            w3.eth.get_transaction_count(
                ChecksumAddress(HexAddress(HexStr(account.lower())))
            )

    def test_eth_getBlockTransactionCountByHash_empty_block(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        transaction_count = w3.eth.get_block_transaction_count(empty_block["hash"])

        assert is_integer(transaction_count)
        assert transaction_count == 0

    def test_eth_getBlockTransactionCountByNumber_empty_block(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        transaction_count = w3.eth.get_block_transaction_count(empty_block["number"])

        assert is_integer(transaction_count)
        assert transaction_count == 0

    def test_eth_getBlockTransactionCountByHash_block_with_txn(
        self, w3: "Web3", block_with_txn: BlockData
    ) -> None:
        transaction_count = w3.eth.get_block_transaction_count(block_with_txn["hash"])

        assert is_integer(transaction_count)
        assert transaction_count >= 1

    def test_eth_getBlockTransactionCountByNumber_block_with_txn(
        self, w3: "Web3", block_with_txn: BlockData
    ) -> None:
        transaction_count = w3.eth.get_block_transaction_count(block_with_txn["number"])

        assert is_integer(transaction_count)
        assert transaction_count >= 1

    def test_eth_getUncleCountByBlockHash(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        uncle_count = w3.eth.get_uncle_count(empty_block["hash"])

        assert is_integer(uncle_count)
        assert uncle_count == 0

    def test_eth_getUncleCountByBlockNumber(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        uncle_count = w3.eth.get_uncle_count(empty_block["number"])

        assert is_integer(uncle_count)
        assert uncle_count == 0

    def test_eth_get_code(
        self, w3: "Web3", math_contract_address: ChecksumAddress
    ) -> None:
        code = w3.eth.get_code(math_contract_address)
        assert isinstance(code, HexBytes)
        assert len(code) > 0

    def test_eth_get_code_ens_address(
        self, w3: "Web3", math_contract_address: ChecksumAddress
    ) -> None:
        with ens_addresses(w3, {"mathcontract.eth": math_contract_address}):
            code = w3.eth.get_code(ENS("mathcontract.eth"))
            assert isinstance(code, HexBytes)
            assert len(code) > 0

    def test_eth_get_code_invalid_address(
        self, w3: "Web3", math_contract: "Contract"
    ) -> None:
        with pytest.raises(InvalidAddress):
            w3.eth.get_code(
                ChecksumAddress(HexAddress(HexStr(math_contract.address.lower())))
            )

    def test_eth_get_code_with_block_identifier(
        self, w3: "Web3", emitter_contract: "Contract"
    ) -> None:
        code = w3.eth.get_code(
            emitter_contract.address, block_identifier=w3.eth.block_number
        )
        assert isinstance(code, HexBytes)
        assert len(code) > 0

    def test_eth_create_access_list(
        self,
        w3: "Web3",
        keyfile_account_address_dual_type: ChecksumAddress,
        math_contract: "Contract",
    ) -> None:
        # build txn
        txn = math_contract.functions.incrementCounter(1).build_transaction(
            {"from": keyfile_account_address_dual_type}
        )

        # create access list
        response = w3.eth.create_access_list(txn)

        assert is_dict(response)
        access_list = response["accessList"]
        assert len(access_list) > 0
        assert access_list[0]["address"] is not None
        assert is_checksum_address(access_list[0]["address"])
        assert len(access_list[0]["storageKeys"][0]) == 66
        assert int(response["gasUsed"]) >= 0

        # assert the result can be used directly in a transaction dict
        txn["accessList"] = response["accessList"]
        txn["gas"] = response["gasUsed"]

        # send txn with access list
        w3.eth.send_transaction(txn)

    def test_eth_sign(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        signature = w3.eth.sign(
            keyfile_account_address_dual_type, text="Message tö sign. Longer than hash!"
        )
        assert is_bytes(signature)
        assert len(signature) == 32 + 32 + 1

        # test other formats
        hexsign = w3.eth.sign(
            keyfile_account_address_dual_type,
            hexstr=HexStr(
                "0x4d6573736167652074c3b6207369676e2e204c6f6e676572207468616e206861736821"  # noqa: E501
            ),
        )
        assert hexsign == signature

        intsign = w3.eth.sign(
            keyfile_account_address_dual_type,
            0x4D6573736167652074C3B6207369676E2E204C6F6E676572207468616E206861736821,
        )
        assert intsign == signature

        bytessign = w3.eth.sign(
            keyfile_account_address_dual_type,
            b"Message t\xc3\xb6 sign. Longer than hash!",
        )
        assert bytessign == signature

        new_signature = w3.eth.sign(
            keyfile_account_address_dual_type, text="different message is different"
        )
        assert new_signature != signature

    def test_eth_sign_ens_names(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        with ens_addresses(
            w3, {"unlocked-acct.eth": keyfile_account_address_dual_type}
        ):
            signature = w3.eth.sign(
                "unlocked-acct.eth", text="Message tö sign. Longer than hash!"
            )
            assert is_bytes(signature)
            assert len(signature) == 32 + 32 + 1

    def test_eth_sign_typed_data(
        self,
        w3: "Web3",
        keyfile_account_address_dual_type: ChecksumAddress,
        skip_if_testrpc: Callable[["Web3"], None],
    ) -> None:
        validJSONMessage = """
            {
                "types": {
                    "EIP712Domain": [
                        {"name": "name", "type": "string"},
                        {"name": "version", "type": "string"},
                        {"name": "chainId", "type": "uint256"},
                        {"name": "verifyingContract", "type": "address"}
                    ],
                    "Person": [
                        {"name": "name", "type": "string"},
                        {"name": "wallet", "type": "address"}
                    ],
                    "Mail": [
                        {"name": "from", "type": "Person"},
                        {"name": "to", "type": "Person"},
                        {"name": "contents", "type": "string"}
                    ]
                },
                "primaryType": "Mail",
                "domain": {
                    "name": "Ether Mail",
                    "version": "1",
                    "chainId": "0x01",
                    "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC"
                },
                "message": {
                    "from": {
                        "name": "Cow",
                        "wallet": "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826"
                    },
                    "to": {
                        "name": "Bob",
                        "wallet": "0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB"
                    },
                    "contents": "Hello, Bob!"
                }
            }
        """
        skip_if_testrpc(w3)
        signature = HexBytes(
            w3.eth.sign_typed_data(
                keyfile_account_address_dual_type, json.loads(validJSONMessage)
            )
        )
        assert len(signature) == 32 + 32 + 1

    def test_invalid_eth_sign_typed_data(
        self,
        w3: "Web3",
        keyfile_account_address_dual_type: ChecksumAddress,
        skip_if_testrpc: Callable[["Web3"], None],
    ) -> None:
        skip_if_testrpc(w3)
        invalid_typed_message = """
            {
                "types": {
                    "EIP712Domain": [
                        {"name": "name", "type": "string"},
                        {"name": "version", "type": "string"},
                        {"name": "chainId", "type": "uint256"},
                        {"name": "verifyingContract", "type": "address"}
                    ],
                    "Person": [
                        {"name": "name", "type": "string"},
                        {"name": "wallet", "type": "address"}
                    ],
                    "Mail": [
                        {"name": "from", "type": "Person"},
                        {"name": "to", "type": "Person[2]"},
                        {"name": "contents", "type": "string"}
                    ]
                },
                "primaryType": "Mail",
                "domain": {
                    "name": "Ether Mail",
                    "version": "1",
                    "chainId": "0x01",
                    "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC"
                },
                "message": {
                    "from": {
                        "name": "Cow",
                        "wallet": "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826"
                    },
                    "to": [{
                        "name": "Bob",
                        "wallet": "0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB"
                    }],
                    "contents": "Hello, Bob!"
                }
            }
        """
        with pytest.raises(
            Web3ValueError,
            match=r".*Expected 2 items for array type Person\[2\], got 1 items.*",
        ):
            w3.eth.sign_typed_data(
                keyfile_account_address_dual_type, json.loads(invalid_typed_message)
            )

    def test_eth_sign_transaction_legacy(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address,
            "to": keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": w3.eth.gas_price,
            "nonce": Nonce(0),
        }
        result = w3.eth.sign_transaction(txn_params)
        signatory_account = w3.eth.account.recover_transaction(result["raw"])
        assert keyfile_account_address == signatory_account
        assert result["tx"]["to"] == txn_params["to"]
        assert result["tx"]["value"] == txn_params["value"]
        assert result["tx"]["gas"] == txn_params["gas"]
        assert result["tx"]["gasPrice"] == txn_params["gasPrice"]
        assert result["tx"]["nonce"] == txn_params["nonce"]

    def test_eth_sign_transaction(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address,
            "to": keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": w3.to_wei(2, "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
            "nonce": Nonce(0),
        }
        result = w3.eth.sign_transaction(txn_params)
        signatory_account = w3.eth.account.recover_transaction(result["raw"])
        assert keyfile_account_address == signatory_account
        assert result["tx"]["to"] == txn_params["to"]
        assert result["tx"]["value"] == txn_params["value"]
        assert result["tx"]["gas"] == txn_params["gas"]
        assert result["tx"]["maxFeePerGas"] == txn_params["maxFeePerGas"]
        assert (
            result["tx"]["maxPriorityFeePerGas"] == txn_params["maxPriorityFeePerGas"]
        )
        assert result["tx"]["nonce"] == txn_params["nonce"]

    def test_eth_sign_transaction_hex_fees(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address,
            "to": keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": hex(w3.to_wei(2, "gwei")),
            "maxPriorityFeePerGas": hex(w3.to_wei(1, "gwei")),
            "nonce": Nonce(0),
        }
        result = w3.eth.sign_transaction(txn_params)
        signatory_account = w3.eth.account.recover_transaction(result["raw"])
        assert keyfile_account_address == signatory_account
        assert result["tx"]["to"] == txn_params["to"]
        assert result["tx"]["value"] == txn_params["value"]
        assert result["tx"]["gas"] == txn_params["gas"]
        assert result["tx"]["maxFeePerGas"] == int(str(txn_params["maxFeePerGas"]), 16)
        assert result["tx"]["maxPriorityFeePerGas"] == int(
            str(txn_params["maxPriorityFeePerGas"]), 16
        )
        assert result["tx"]["nonce"] == txn_params["nonce"]

    def test_eth_sign_transaction_ens_names(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        with ens_addresses(w3, {"unlocked-account.eth": keyfile_account_address}):
            txn_params: TxParams = {
                "from": "unlocked-account.eth",
                "to": "unlocked-account.eth",
                "value": Wei(1),
                "gas": 21000,
                "maxFeePerGas": w3.to_wei(2, "gwei"),
                "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
                "nonce": Nonce(0),
            }
            result = w3.eth.sign_transaction(txn_params)
            signatory_account = w3.eth.account.recover_transaction(result["raw"])
            assert keyfile_account_address == signatory_account
            assert result["tx"]["to"] == keyfile_account_address
            assert result["tx"]["value"] == txn_params["value"]
            assert result["tx"]["gas"] == txn_params["gas"]
            assert result["tx"]["maxFeePerGas"] == txn_params["maxFeePerGas"]
            assert (
                result["tx"]["maxPriorityFeePerGas"]
                == txn_params["maxPriorityFeePerGas"]
            )
            assert result["tx"]["nonce"] == txn_params["nonce"]

    def test_eth_send_transaction_addr_checksum_required(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        non_checksum_addr = keyfile_account_address.lower()
        txn_params: TxParams = {
            "from": keyfile_account_address,
            "to": keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": w3.to_wei(2, "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
        }

        with pytest.raises(InvalidAddress):
            invalid_params = cast(
                TxParams, dict(txn_params, **{"from": non_checksum_addr})
            )
            w3.eth.send_transaction(invalid_params)

        with pytest.raises(InvalidAddress):
            invalid_params = cast(
                TxParams, dict(txn_params, **{"to": non_checksum_addr})
            )
            w3.eth.send_transaction(invalid_params)

    def test_eth_send_transaction_legacy(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": w3.to_wei(
                1, "gwei"
            ),  # post-london needs to be more than the base fee
        }
        txn_hash = w3.eth.send_transaction(txn_params)
        txn = w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 21000
        assert txn["gasPrice"] == txn_params["gasPrice"]

    def test_eth_send_transaction(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": w3.to_wei(3, "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
        }

        txn_hash = w3.eth.send_transaction(txn_params)
        txn = w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 21000
        assert txn["maxFeePerGas"] == txn_params["maxFeePerGas"]
        assert txn["maxPriorityFeePerGas"] == txn_params["maxPriorityFeePerGas"]
        assert txn["gasPrice"] <= txn["maxFeePerGas"]  # effective gas price

    def test_eth_send_transaction_with_nonce(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        max_priority_fee_per_gas = w3.to_wei(1.234, "gwei")
        max_fee_per_gas = Wei(
            w3.eth.get_block("latest")["baseFeePerGas"] + max_priority_fee_per_gas
        )
        txn_params: TxParams = {
            "from": keyfile_account_address,
            "to": keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": max_fee_per_gas,
            "maxPriorityFeePerGas": max_priority_fee_per_gas,
            "nonce": Nonce(
                w3.eth.get_transaction_count(keyfile_account_address, "pending")
            ),
        }
        txn_hash = w3.eth.send_transaction(txn_params)
        txn = w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 21000
        assert txn["maxFeePerGas"] == txn_params["maxFeePerGas"]
        assert txn["maxPriorityFeePerGas"] == txn_params["maxPriorityFeePerGas"]
        assert txn["nonce"] == txn_params["nonce"]
        assert is_integer(txn["gasPrice"])
        assert is_integer(txn_params["maxFeePerGas"])

    def test_eth_send_transaction_default_fees(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
        }
        txn_hash = w3.eth.send_transaction(txn_params)
        txn = w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 21000
        assert is_integer(txn["maxPriorityFeePerGas"])
        assert is_integer(txn["maxFeePerGas"])
        assert txn["gasPrice"] <= txn["maxFeePerGas"]  # effective gas price

    def test_eth_send_transaction_hex_fees(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": hex(250 * 10**9),
            "maxPriorityFeePerGas": hex(2 * 10**9),
        }
        txn_hash = w3.eth.send_transaction(txn_params)
        txn = w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 21000
        assert txn["maxFeePerGas"] == 250 * 10**9
        assert txn["maxPriorityFeePerGas"] == 2 * 10**9

    def test_eth_send_transaction_no_gas(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "maxFeePerGas": Wei(250 * 10**9),
            "maxPriorityFeePerGas": Wei(2 * 10**9),
        }
        txn_hash = w3.eth.send_transaction(txn_params)
        txn = w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 121000  # 21000 + buffer

    def test_eth_send_transaction_with_gas_price(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": Wei(1),
            "maxFeePerGas": Wei(250 * 10**9),
            "maxPriorityFeePerGas": Wei(2 * 10**9),
        }
        with pytest.raises(TransactionTypeMismatch):
            w3.eth.send_transaction(txn_params)

    def test_eth_send_transaction_no_priority_fee(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": Wei(250 * 10**9),
        }
        with pytest.raises(
            InvalidTransaction, match="maxPriorityFeePerGas must be defined"
        ):
            w3.eth.send_transaction(txn_params)

    def test_eth_send_transaction_no_max_fee(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        max_priority_fee_per_gas = w3.to_wei(2, "gwei")
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxPriorityFeePerGas": max_priority_fee_per_gas,
        }
        txn_hash = w3.eth.send_transaction(txn_params)
        txn = w3.eth.get_transaction(txn_hash)

        assert is_same_address(txn["from"], cast(ChecksumAddress, txn_params["from"]))
        assert is_same_address(txn["to"], cast(ChecksumAddress, txn_params["to"]))
        assert txn["value"] == 1
        assert txn["gas"] == 21000
        assert is_integer(txn["maxPriorityFeePerGas"])
        assert txn["maxPriorityFeePerGas"] == max_priority_fee_per_gas
        assert is_integer(txn["maxFeePerGas"])

    def test_eth_send_transaction_max_fee_less_than_tip(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": Wei(1 * 10**9),
            "maxPriorityFeePerGas": Wei(2 * 10**9),
        }
        with pytest.raises(
            InvalidTransaction, match="maxFeePerGas must be >= maxPriorityFeePerGas"
        ):
            w3.eth.send_transaction(txn_params)

    def test_validation_middleware_chain_id_mismatch(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        wrong_chain_id = 1234567890
        actual_chain_id = w3.eth.chain_id

        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": Wei(21000),
            "maxFeePerGas": w3.to_wei(2, "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
            "chainId": wrong_chain_id,
        }
        with pytest.raises(
            Web3ValidationError,
            match=f"The transaction declared chain ID {wrong_chain_id}, "
            f"but the connected node is on {actual_chain_id}",
        ):
            w3.eth.send_transaction(txn_params)

    @pytest.mark.parametrize(
        "max_fee", (1000000000, None), ids=["with_max_fee", "without_max_fee"]
    )
    def test_gas_price_from_strategy_bypassed_for_dynamic_fee_txn(
        self,
        w3: "Web3",
        keyfile_account_address_dual_type: ChecksumAddress,
        max_fee: Wei,
    ) -> None:
        max_priority_fee = w3.to_wei(1, "gwei")
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxPriorityFeePerGas": max_priority_fee,
        }
        if max_fee is not None:
            txn_params = assoc(txn_params, "maxFeePerGas", max_fee)

        def gas_price_strategy(_w3: "Web3", _txn: TxParams) -> Wei:
            return w3.to_wei(2, "gwei")

        w3.eth.set_gas_price_strategy(gas_price_strategy)

        txn_hash = w3.eth.send_transaction(txn_params)
        txn = w3.eth.get_transaction(txn_hash)

        latest_block = w3.eth.get_block("latest")
        assert (
            txn["maxFeePerGas"] == max_fee
            if max_fee is not None
            else 2 * latest_block["baseFeePerGas"] + max_priority_fee
        )
        assert txn["maxPriorityFeePerGas"] == max_priority_fee
        assert txn["gasPrice"] <= txn["maxFeePerGas"]  # effective gas price

        w3.eth.set_gas_price_strategy(None)  # reset strategy

    def test_gas_price_from_strategy_bypassed_for_dynamic_fee_txn_no_tip(
        self,
        w3: "Web3",
        keyfile_account_address_dual_type: ChecksumAddress,
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": Wei(1000000000),
        }

        def gas_price_strategy(_w3: "Web3", _txn: TxParams) -> Wei:
            return w3.to_wei(2, "gwei")

        w3.eth.set_gas_price_strategy(gas_price_strategy)

        with pytest.raises(
            InvalidTransaction, match="maxPriorityFeePerGas must be defined"
        ):
            w3.eth.send_transaction(txn_params)

        w3.eth.set_gas_price_strategy(None)  # reset strategy

    def test_gas_price_strategy_hex_value(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
        }
        two_gwei_in_wei = w3.to_wei(2, "gwei")

        def gas_price_strategy(_w3: "Web3", _txn: TxParams) -> str:
            return hex(two_gwei_in_wei)

        w3.eth.set_gas_price_strategy(gas_price_strategy)  # type: ignore

        txn_hash = w3.eth.send_transaction(txn_params)
        txn = w3.eth.get_transaction(txn_hash)

        assert txn["gasPrice"] == two_gwei_in_wei
        w3.eth.set_gas_price_strategy(None)  # reset strategy

    @flaky_geth_dev_mining
    def test_eth_replace_transaction_legacy(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": w3.to_wei(
                1, "gwei"
            ),  # must be greater than base_fee post London
        }
        txn_hash = w3.eth.send_transaction(txn_params)

        txn_params["gasPrice"] = w3.to_wei(2, "gwei")
        replace_txn_hash = w3.eth.replace_transaction(txn_hash, txn_params)
        replace_txn = w3.eth.get_transaction(replace_txn_hash)

        assert is_same_address(
            replace_txn["from"], cast(ChecksumAddress, txn_params["from"])
        )
        assert is_same_address(
            replace_txn["to"], cast(ChecksumAddress, txn_params["to"])
        )
        assert replace_txn["value"] == 1
        assert replace_txn["gas"] == 21000
        assert replace_txn["gasPrice"] == txn_params["gasPrice"]

    @flaky_geth_dev_mining
    def test_eth_replace_transaction(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        two_gwei_in_wei = w3.to_wei(2, "gwei")
        three_gwei_in_wei = w3.to_wei(3, "gwei")

        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": two_gwei_in_wei,
            "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
        }
        txn_hash = w3.eth.send_transaction(txn_params)

        txn_params["maxFeePerGas"] = three_gwei_in_wei
        txn_params["maxPriorityFeePerGas"] = two_gwei_in_wei

        replace_txn_hash = w3.eth.replace_transaction(txn_hash, txn_params)
        replace_txn = w3.eth.get_transaction(replace_txn_hash)

        assert is_same_address(
            replace_txn["from"], cast(ChecksumAddress, txn_params["from"])
        )
        assert is_same_address(
            replace_txn["to"], cast(ChecksumAddress, txn_params["to"])
        )
        assert replace_txn["value"] == 1
        assert replace_txn["gas"] == 21000
        assert replace_txn["maxFeePerGas"] == three_gwei_in_wei
        assert replace_txn["maxPriorityFeePerGas"] == two_gwei_in_wei

    @flaky_geth_dev_mining
    def test_eth_replace_transaction_underpriced(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        # Note: `underpriced transaction` error is only consistent with
        # ``txpool.nolocals`` flag as of Geth ``v1.15.4``.
        # https://github.com/ethereum/web3.py/pull/3636
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": w3.to_wei(3, "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(2, "gwei"),
        }
        txn_hash = w3.eth.send_transaction(txn_params)

        one_gwei_in_wei = w3.to_wei(1, "gwei")
        txn_params["maxFeePerGas"] = one_gwei_in_wei
        txn_params["maxPriorityFeePerGas"] = one_gwei_in_wei

        with pytest.raises(Web3RPCError, match="replacement transaction underpriced"):
            w3.eth.replace_transaction(txn_hash, txn_params)

    @flaky_geth_dev_mining
    def test_eth_replace_transaction_non_existing_transaction(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": w3.to_wei(3, "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
        }
        with pytest.raises(TransactionNotFound):
            w3.eth.replace_transaction(
                HexStr(
                    "0x98e8cc09b311583c5079fa600f6c2a3bea8611af168c52e4b60b5b243a441997"
                ),
                txn_params,
            )

    @flaky_geth_dev_mining
    def test_eth_replace_transaction_already_mined(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": w3.to_wei(2, "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
        }
        txn_hash = w3.eth.send_transaction(txn_params)
        w3.eth.wait_for_transaction_receipt(txn_hash, timeout=10)

        txn_params["maxFeePerGas"] = w3.to_wei(3, "gwei")
        txn_params["maxPriorityFeePerGas"] = w3.to_wei(2, "gwei")
        with pytest.raises(Web3ValueError, match="Supplied transaction with hash"):
            w3.eth.replace_transaction(txn_hash, txn_params)

    @flaky_geth_dev_mining
    def test_eth_replace_transaction_incorrect_nonce(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address,
            "to": keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "maxFeePerGas": w3.to_wei(2, "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
        }
        txn_hash = w3.eth.send_transaction(txn_params)
        txn = w3.eth.get_transaction(txn_hash)

        txn_params["maxFeePerGas"] = w3.to_wei(3, "gwei")
        txn_params["maxPriorityFeePerGas"] = w3.to_wei(2, "gwei")
        txn_params["nonce"] = Nonce(txn["nonce"] + 1)
        with pytest.raises(Web3ValueError):
            w3.eth.replace_transaction(txn_hash, txn_params)

    @flaky_geth_dev_mining
    def test_eth_replace_transaction_gas_price_too_low(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address_dual_type,
            "to": keyfile_account_address_dual_type,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": w3.to_wei(2, "gwei"),
        }
        txn_hash = w3.eth.send_transaction(txn_params)

        txn_params["gasPrice"] = w3.to_wei(1, "gwei")
        with pytest.raises(Web3ValueError):
            w3.eth.replace_transaction(txn_hash, txn_params)

    @flaky_geth_dev_mining
    def test_eth_replace_transaction_gas_price_defaulting_minimum(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        gas_price = w3.to_wei(1, "gwei")

        txn_params: TxParams = {
            "from": keyfile_account_address,
            "to": keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": gas_price,
        }
        txn_hash = w3.eth.send_transaction(txn_params)

        txn_params.pop("gasPrice")
        replace_txn_hash = w3.eth.replace_transaction(txn_hash, txn_params)
        replace_txn = w3.eth.get_transaction(replace_txn_hash)

        assert replace_txn["gasPrice"] == math.ceil(
            gas_price * 1.125
        )  # minimum gas price

    @flaky_geth_dev_mining
    def test_eth_replace_transaction_gas_price_defaulting_strategy_higher(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address,
            "to": keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": w3.to_wei(1, "gwei"),
        }
        txn_hash = w3.eth.send_transaction(txn_params)

        two_gwei_in_wei = w3.to_wei(2, "gwei")

        def higher_gas_price_strategy(w3: "Web3", txn: TxParams) -> Wei:
            return two_gwei_in_wei

        w3.eth.set_gas_price_strategy(higher_gas_price_strategy)

        txn_params.pop("gasPrice")
        replace_txn_hash = w3.eth.replace_transaction(txn_hash, txn_params)
        replace_txn = w3.eth.get_transaction(replace_txn_hash)
        assert (
            replace_txn["gasPrice"] == two_gwei_in_wei
        )  # Strategy provides higher gas price
        w3.eth.set_gas_price_strategy(None)  # reset strategy

    @flaky_geth_dev_mining
    def test_eth_replace_transaction_gas_price_defaulting_strategy_lower(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        gas_price = w3.to_wei(2, "gwei")
        txn_params: TxParams = {
            "from": keyfile_account_address,
            "to": keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": gas_price,
        }
        txn_hash = w3.eth.send_transaction(txn_params)

        def lower_gas_price_strategy(w3: "Web3", txn: TxParams) -> Wei:
            return w3.to_wei(1, "gwei")

        w3.eth.set_gas_price_strategy(lower_gas_price_strategy)

        txn_params.pop("gasPrice")
        replace_txn_hash = w3.eth.replace_transaction(txn_hash, txn_params)
        replace_txn = w3.eth.get_transaction(replace_txn_hash)
        # Strategy provides lower gas price - minimum preferred
        assert replace_txn["gasPrice"] == math.ceil(gas_price * 1.125)
        w3.eth.set_gas_price_strategy(None)  # reset strategy

    def test_eth_modify_transaction_legacy(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address,
            "to": keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "gasPrice": w3.to_wei(
                1, "gwei"
            ),  # must be greater than base_fee post London
        }
        txn_hash = w3.eth.send_transaction(txn_params)

        modified_txn_hash = w3.eth.modify_transaction(
            txn_hash, gasPrice=(cast(Wei, txn_params["gasPrice"] * 2)), value=Wei(2)
        )
        modified_txn = w3.eth.get_transaction(modified_txn_hash)

        assert is_same_address(
            modified_txn["from"], cast(ChecksumAddress, txn_params["from"])
        )
        assert is_same_address(
            modified_txn["to"], cast(ChecksumAddress, txn_params["to"])
        )
        assert modified_txn["value"] == 2
        assert modified_txn["gas"] == 21000
        assert modified_txn["gasPrice"] == cast(int, txn_params["gasPrice"]) * 2

    def test_eth_modify_transaction(
        self, w3: "Web3", keyfile_account_address: ChecksumAddress
    ) -> None:
        txn_params: TxParams = {
            "from": keyfile_account_address,
            "to": keyfile_account_address,
            "value": Wei(1),
            "gas": 21000,
            "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
            "maxFeePerGas": w3.to_wei(2, "gwei"),
        }
        txn_hash = w3.eth.send_transaction(txn_params)

        modified_txn_hash = w3.eth.modify_transaction(
            txn_hash,
            value=Wei(2),
            maxPriorityFeePerGas=(cast(Wei, txn_params["maxPriorityFeePerGas"] * 2)),
            maxFeePerGas=(cast(Wei, txn_params["maxFeePerGas"] * 2)),
        )
        modified_txn = w3.eth.get_transaction(modified_txn_hash)

        assert is_same_address(
            modified_txn["from"], cast(ChecksumAddress, txn_params["from"])
        )
        assert is_same_address(
            modified_txn["to"], cast(ChecksumAddress, txn_params["to"])
        )
        assert modified_txn["value"] == 2
        assert modified_txn["gas"] == 21000
        assert (
            modified_txn["maxPriorityFeePerGas"]
            == cast(Wei, txn_params["maxPriorityFeePerGas"]) * 2
        )
        assert modified_txn["maxFeePerGas"] == cast(Wei, txn_params["maxFeePerGas"]) * 2

    def test_eth_send_raw_transaction(
        self, w3: "Web3", keyfile_account_pkey: HexStr
    ) -> None:
        keyfile_account = w3.eth.account.from_key(keyfile_account_pkey)
        txn = {
            "chainId": 131277322940537,  # the chainId set for the fixture
            "from": keyfile_account.address,
            "to": keyfile_account.address,
            "value": Wei(0),
            "gas": 21000,
            "nonce": w3.eth.get_transaction_count(keyfile_account.address, "pending"),
            "gasPrice": 10**9,
        }
        signed = keyfile_account.sign_transaction(txn)
        txn_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        assert txn_hash == HexBytes(signed.hash)

    def test_sign_and_send_raw_middleware(
        self, w3: "Web3", keyfile_account_pkey: HexStr
    ) -> None:
        keyfile_account = w3.eth.account.from_key(keyfile_account_pkey)
        txn: TxParams = {
            "from": keyfile_account.address,
            "to": keyfile_account.address,
            "value": Wei(0),
            "gas": 21000,
        }
        w3.middleware_onion.inject(
            SignAndSendRawMiddlewareBuilder.build(keyfile_account), "signing", layer=0
        )
        txn_hash = w3.eth.send_transaction(txn)
        assert isinstance(txn_hash, HexBytes)

        # cleanup
        w3.middleware_onion.remove("signing")

    def test_eth_call(self, w3: "Web3", math_contract: "Contract") -> None:
        txn_params = math_contract._prepare_transaction(
            abi_element_identifier="add",
            fn_args=(7, 11),
            transaction={"from": w3.eth.accounts[0], "to": math_contract.address},
        )
        call_result = w3.eth.call(txn_params)
        assert is_string(call_result)
        (result,) = w3.codec.decode(["uint256"], call_result)
        assert result == 18

    def test_eth_call_with_override_code(
        self, w3: "Web3", revert_contract: "Contract"
    ) -> None:
        txn_params = revert_contract._prepare_transaction(
            abi_element_identifier="normalFunction",
            transaction={"from": w3.eth.accounts[0], "to": revert_contract.address},
        )
        call_result = w3.eth.call(txn_params)
        (result,) = w3.codec.decode(["bool"], call_result)
        assert result is True

        # override runtime bytecode: `normalFunction` returns `false`
        override_code = HexStr(
            "0x6080604052348015600f57600080fd5b5060043610603c5760003560e01c8063185c38a4146041578063c06a97cb146049578063d67e4b84146051575b600080fd5b60476071565b005b604f60df565b005b605760e4565b604051808215151515815260200191505060405180910390f35b6040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601b8152602001807f46756e6374696f6e20686173206265656e2072657665727465642e000000000081525060200191505060405180910390fd5b600080fd5b60008090509056fea2646970667358221220bb71e9e9a2e271cd0fbe833524a3ea67df95f25ea13aef5b0a761fa52b538f1064736f6c63430006010033"  # noqa: E501
        )
        call_result = w3.eth.call(
            txn_params, "latest", {revert_contract.address: {"code": override_code}}
        )
        (result,) = w3.codec.decode(["bool"], call_result)
        assert result is False

        # test bytes

        bytes_call_result = w3.eth.call(
            txn_params,
            "latest",
            {revert_contract.address: {"code": to_bytes(hexstr=override_code)}},
        )
        (bytes_result,) = w3.codec.decode(["bool"], bytes_call_result)
        assert bytes_result is False

    @pytest.mark.parametrize(
        "params",
        (
            {
                "nonce": 1,  # int
                "balance": 1,  # int
                "code": HexStr("0x"),  # HexStr
                # with state
                "state": {HexStr(f"0x{'00' * 32}"): HexStr(f"0x{'00' * 32}")},
            },
            {
                "nonce": HexStr("0x1"),  # HexStr
                "balance": HexStr("0x1"),  # HexStr
                "code": b"\x00",  # bytes
                # with stateDiff
                "stateDiff": {HexStr(f"0x{'00' * 32}"): HexStr(f"0x{'00' * 32}")},
            },
        ),
    )
    def test_eth_call_with_override_param_type_check(
        self,
        w3: "Web3",
        math_contract: "Contract",
        params: StateOverrideParams,
    ) -> None:
        txn_params: TxParams = {"from": w3.eth.accounts[0], "to": math_contract.address}

        # assert does not raise
        w3.eth.call(txn_params, "latest", {math_contract.address: params})

    def test_eth_call_with_0_result(
        self, w3: "Web3", math_contract: "Contract"
    ) -> None:
        txn_params = math_contract._prepare_transaction(
            abi_element_identifier="add",
            fn_args=(0, 0),
            transaction={"from": w3.eth.accounts[0], "to": math_contract.address},
        )
        call_result = w3.eth.call(txn_params)
        assert is_string(call_result)
        (result,) = w3.codec.decode(["uint256"], call_result)
        assert result == 0

    def test_eth_call_revert_with_msg(
        self,
        w3: "Web3",
        revert_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
    ) -> None:
        txn_params = revert_contract._prepare_transaction(
            abi_element_identifier="revertWithMessage",
            transaction={
                "from": keyfile_account_address,
                "to": revert_contract.address,
            },
        )
        data = "0x08c379a00000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000001b46756e6374696f6e20686173206265656e2072657665727465642e0000000000"  # noqa: E501
        with pytest.raises(
            ContractLogicError, match="execution reverted: Function has been reverted"
        ) as excinfo:
            w3.eth.call(txn_params)
        assert excinfo.value.data == data

    def test_eth_call_revert_without_msg(
        self,
        w3: "Web3",
        revert_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
    ) -> None:
        with pytest.raises(ContractLogicError, match="execution reverted"):
            txn_params = revert_contract._prepare_transaction(
                abi_element_identifier="revertWithoutMessage",
                transaction={
                    "from": keyfile_account_address,
                    "to": revert_contract.address,
                },
            )
            w3.eth.call(txn_params)

    def test_eth_call_custom_error_revert_with_msg(
        self,
        w3: "Web3",
        revert_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
    ) -> None:
        data = revert_contract.encode_abi(
            abi_element_identifier="UnauthorizedWithMessage",
            args=["You are not authorized"],
        )
        txn_params = revert_contract._prepare_transaction(
            abi_element_identifier="customErrorWithMessage",
            transaction={
                "from": keyfile_account_address,
                "to": revert_contract.address,
            },
        )
        with pytest.raises(ContractCustomError, match=data) as excinfo:
            w3.eth.call(txn_params)
        assert excinfo.value.data == data

    def test_eth_call_custom_error_revert_without_msg(
        self,
        w3: "Web3",
        revert_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
    ) -> None:
        data = revert_contract.encode_abi(abi_element_identifier="Unauthorized")
        txn_params = revert_contract._prepare_transaction(
            abi_element_identifier="customErrorWithoutMessage",
            transaction={
                "from": keyfile_account_address,
                "to": revert_contract.address,
            },
        )
        with pytest.raises(ContractCustomError, match=data) as excinfo:
            w3.eth.call(txn_params)
        assert excinfo.value.data == data

    def test_eth_simulate_v1(self, w3: "Web3") -> None:
        simulate_result = w3.eth.simulate_v1(
            {
                "blockStateCalls": [
                    {
                        "blockOverrides": {
                            "baseFeePerGas": Wei(10),
                        },
                        "stateOverrides": {
                            "0xc100000000000000000000000000000000000000": {
                                "balance": Wei(500000000),
                            }
                        },
                        "calls": [
                            {
                                "from": "0xc100000000000000000000000000000000000000",
                                "to": "0xc100000000000000000000000000000000000000",
                                "maxFeePerGas": Wei(10),
                                "maxPriorityFeePerGas": Wei(10),
                            }
                        ],
                    }
                ],
                "validation": True,
                "traceTransfers": True,
            },
            "latest",
        )

        assert len(simulate_result) == 1

        result = simulate_result[0]
        assert result.get("baseFeePerGas") == 10

        calls_result = result.get("calls")
        assert calls_result is not None
        assert len(calls_result) == 1
        call_entry = calls_result[0]

        assert all(
            key in call_entry for key in ("returnData", "logs", "gasUsed", "status")
        )
        assert call_entry["status"] == 1
        assert call_entry["gasUsed"] == int("0x5208", 16)

    @pytest.mark.parametrize(
        "panic_error,params",
        (
            ("01", []),
            ("11", []),
            ("12", [0]),
            ("21", [-1]),
            ("22", []),
            ("31", []),
            ("32", []),
            ("41", []),
            ("51", []),
        ),
    )
    def test_contract_panic_errors(
        self,
        w3: "Web3",
        panic_errors_contract: "Contract",
        panic_error: str,
        params: List[Any],
    ) -> None:
        method = getattr(
            panic_errors_contract.functions,
            f"errorCode{panic_error}",
        )
        error_msg = PANIC_ERROR_CODES[panic_error]

        with pytest.raises(ContractPanicError, match=re.escape(error_msg)):
            method(*params).call()

    def test_eth_call_offchain_lookup(
        self,
        w3: "Web3",
        offchain_lookup_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
        monkeypatch: "MonkeyPatch",
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            offchain_lookup_contract.address
        ).lower()
        mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/{OFFCHAIN_LOOKUP_TEST_DATA}.json",  # noqa: E501
            mocked_json_data=WEB3PY_AS_HEXBYTES,
        )
        response = offchain_lookup_contract.functions.testOffchainLookup(
            OFFCHAIN_LOOKUP_TEST_DATA
        ).call()
        assert w3.codec.decode(["string"], response)[0] == "web3py"

    def test_eth_call_offchain_lookup_raises_when_ccip_read_is_disabled(
        self,
        w3: "Web3",
        offchain_lookup_contract: "Contract",
    ) -> None:
        return_data = (
            OFFCHAIN_LOOKUP_4BYTE_DATA
            + abi_encoded_offchain_lookup_contract_address(w3, offchain_lookup_contract)
            + OFFCHAIN_LOOKUP_RETURN_DATA
        )
        # test ContractFunction call
        with pytest.raises(OffchainLookup) as e:
            offchain_lookup_contract.functions.testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            ).call(ccip_read_enabled=False)
        assert e.value.data == return_data

        # test ContractCaller call
        with pytest.raises(OffchainLookup) as excinfo:
            offchain_lookup_contract.caller(ccip_read_enabled=False).testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            )
        assert excinfo.value.data == return_data

        # test global flag on the provider
        w3.provider.global_ccip_read_enabled = False

        with pytest.raises(OffchainLookup) as exc_info:
            offchain_lookup_contract.functions.testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            ).call()
        assert exc_info.value.data == return_data

        w3.provider.global_ccip_read_enabled = True  # cleanup

    def test_eth_call_offchain_lookup_call_flag_overrides_provider_flag(
        self,
        w3: "Web3",
        offchain_lookup_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
        monkeypatch: "MonkeyPatch",
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            offchain_lookup_contract.address
        ).lower()
        mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/{OFFCHAIN_LOOKUP_TEST_DATA}.json",  # noqa: E501
            mocked_json_data=WEB3PY_AS_HEXBYTES,
        )

        w3.provider.global_ccip_read_enabled = False

        response = offchain_lookup_contract.functions.testOffchainLookup(
            OFFCHAIN_LOOKUP_TEST_DATA
        ).call(ccip_read_enabled=True)
        assert w3.codec.decode(["string"], response)[0] == "web3py"

        w3.provider.global_ccip_read_enabled = True  # cleanup

    @pytest.mark.parametrize("max_redirects", range(-1, 4))
    def test_eth_call_offchain_lookup_raises_if_max_redirects_is_less_than_4(
        self,
        w3: "Web3",
        offchain_lookup_contract: "Contract",
        max_redirects: int,
    ) -> None:
        default_max_redirects = w3.provider.ccip_read_max_redirects

        w3.provider.ccip_read_max_redirects = max_redirects
        with pytest.raises(Web3ValueError, match="at least 4"):
            offchain_lookup_contract.functions.testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            ).call()

        w3.provider.ccip_read_max_redirects = default_max_redirects  # cleanup

    def test_eth_call_offchain_lookup_raises_for_improperly_formatted_rest_request_response(  # noqa: E501
        self,
        w3: "Web3",
        offchain_lookup_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
        monkeypatch: "MonkeyPatch",
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            offchain_lookup_contract.address
        ).lower()
        mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/{OFFCHAIN_LOOKUP_TEST_DATA}.json",  # noqa: E501
            mocked_json_data=WEB3PY_AS_HEXBYTES,
            json_data_field="not_data",
        )
        with pytest.raises(Web3ValidationError, match="missing 'data' field"):
            offchain_lookup_contract.functions.testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            ).call()

    @pytest.mark.parametrize("status_code_non_4xx_error", [100, 300, 500, 600])
    def test_eth_call_offchain_lookup_tries_next_url_for_non_4xx_error_status_and_tests_POST(  # noqa: E501
        self,
        w3: "Web3",
        offchain_lookup_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
        monkeypatch: "MonkeyPatch",
        status_code_non_4xx_error: int,
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            offchain_lookup_contract.address
        ).lower()

        # The next url in our test contract doesn't contain '{data}', triggering
        # the POST request logic. The idea here is to return a bad status for
        # the first url (GET) and a success status from the second call (POST)
        # to test both that we move on to the next url with non 4xx status and
        # that the POST logic is also working as expected.
        mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/{OFFCHAIN_LOOKUP_TEST_DATA}.json",  # noqa: E501
            mocked_status_code=status_code_non_4xx_error,
            mocked_json_data=WEB3PY_AS_HEXBYTES,
        )
        mock_offchain_lookup_request_response(
            monkeypatch,
            http_method="POST",
            mocked_request_url="https://web3.py/gateway",
            mocked_status_code=200,
            mocked_json_data=WEB3PY_AS_HEXBYTES,
            sender=normalized_contract_address,
            calldata=OFFCHAIN_LOOKUP_TEST_DATA,
        )
        response = offchain_lookup_contract.functions.testOffchainLookup(
            OFFCHAIN_LOOKUP_TEST_DATA
        ).call()
        assert w3.codec.decode(["string"], response)[0] == "web3py"

    def test_eth_call_offchain_lookup_calls_raise_for_status_for_4xx_status_code(
        self,
        w3: "Web3",
        offchain_lookup_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
        monkeypatch: "MonkeyPatch",
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            offchain_lookup_contract.address
        ).lower()
        mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/{OFFCHAIN_LOOKUP_TEST_DATA}.json",  # noqa: E501
            mocked_status_code=randint(400, 499),
            mocked_json_data=WEB3PY_AS_HEXBYTES,
        )
        with pytest.raises(Exception, match="called raise_for_status\\(\\)"):
            offchain_lookup_contract.functions.testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            ).call()

    def test_eth_call_offchain_lookup_raises_when_all_supplied_urls_fail(
        self,
        offchain_lookup_contract: "Contract",
    ) -> None:
        # GET and POST requests should fail since responses are not mocked
        with pytest.raises(
            MultipleFailedRequests, match="Offchain lookup failed for supplied urls"
        ):
            offchain_lookup_contract.functions.testOffchainLookup(
                OFFCHAIN_LOOKUP_TEST_DATA
            ).call()

    def test_eth_call_continuous_offchain_lookup_raises_with_too_many_requests(
        self,
        offchain_lookup_contract: "Contract",
        monkeypatch: "MonkeyPatch",
    ) -> None:
        normalized_contract_address = to_hex_if_bytes(
            offchain_lookup_contract.address
        ).lower()
        mock_offchain_lookup_request_response(
            monkeypatch,
            mocked_request_url=f"https://web3.py/gateway/{normalized_contract_address}/0x.json",  # noqa: E501
        )
        with pytest.raises(TooManyRequests, match="Too many CCIP read redirects"):
            offchain_lookup_contract.caller().continuousOffchainLookup()

    def test_eth_estimate_gas_revert_with_msg(
        self,
        w3: "Web3",
        revert_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
    ) -> None:
        with pytest.raises(
            ContractLogicError, match="execution reverted: Function has been reverted"
        ):
            txn_params = revert_contract._prepare_transaction(
                abi_element_identifier="revertWithMessage",
                transaction={
                    "from": keyfile_account_address,
                    "to": revert_contract.address,
                },
            )
            w3.eth.estimate_gas(txn_params)

    def test_eth_estimate_gas_revert_without_msg(
        self,
        w3: "Web3",
        revert_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
    ) -> None:
        with pytest.raises(ContractLogicError, match="execution reverted"):
            txn_params = revert_contract._prepare_transaction(
                abi_element_identifier="revertWithoutMessage",
                transaction={
                    "from": keyfile_account_address,
                    "to": revert_contract.address,
                },
            )
            w3.eth.estimate_gas(txn_params)

    def test_eth_estimate_gas_custom_error_revert_with_msg(
        self,
        w3: "Web3",
        revert_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
    ) -> None:
        data = revert_contract.encode_abi(
            abi_element_identifier="UnauthorizedWithMessage",
            args=["You are not authorized"],
        )
        txn_params = revert_contract._prepare_transaction(
            abi_element_identifier="customErrorWithMessage",
            transaction={
                "from": keyfile_account_address,
                "to": revert_contract.address,
            },
        )
        with pytest.raises(ContractCustomError, match=data) as excinfo:
            w3.eth.estimate_gas(txn_params)
        assert excinfo.value.data == data

    def test_eth_estimate_gas_custom_error_revert_without_msg(
        self,
        w3: "Web3",
        revert_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
    ) -> None:
        data = revert_contract.encode_abi(abi_element_identifier="Unauthorized")
        txn_params = revert_contract._prepare_transaction(
            abi_element_identifier="customErrorWithoutMessage",
            transaction={
                "from": keyfile_account_address,
                "to": revert_contract.address,
            },
        )
        with pytest.raises(ContractCustomError, match=data) as excinfo:
            w3.eth.estimate_gas(txn_params)
        assert excinfo.value.data == data

    def test_eth_estimate_gas(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        gas_estimate = w3.eth.estimate_gas(
            {
                "from": keyfile_account_address_dual_type,
                "to": keyfile_account_address_dual_type,
                "value": Wei(1),
            }
        )
        assert is_integer(gas_estimate)
        assert gas_estimate > 0

    def test_eth_estimate_gas_with_block(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        gas_estimate = w3.eth.estimate_gas(
            {
                "from": keyfile_account_address_dual_type,
                "to": keyfile_account_address_dual_type,
                "value": Wei(1),
            },
            "latest",
        )
        assert is_integer(gas_estimate)
        assert gas_estimate > 0

    @pytest.mark.parametrize(
        "params",
        (
            {
                "nonce": 1,  # int
                "balance": 1,  # int
                "code": HexStr("0x"),  # HexStr
                # with state
                "state": {HexStr(f"0x{'00' * 32}"): HexStr(f"0x{'00' * 32}")},
            },
            {
                "nonce": HexStr("0x1"),  # HexStr
                "balance": HexStr("0x1"),  # HexStr
                "code": b"\x00",  # bytes
                # with stateDiff
                "stateDiff": {HexStr(f"0x{'00' * 32}"): HexStr(f"0x{'00' * 32}")},
            },
        ),
    )
    def test_eth_estimate_gas_with_override_param_type_check(
        self,
        w3: "Web3",
        math_contract: "Contract",
        params: StateOverrideParams,
    ) -> None:
        txn_params: TxParams = {"from": w3.eth.accounts[0]}

        # assert does not raise
        w3.eth.estimate_gas(txn_params, None, {math_contract.address: params})

    def test_eth_getBlockByHash(self, w3: "Web3", empty_block: BlockData) -> None:
        block = w3.eth.get_block(empty_block["hash"])
        assert block["hash"] == empty_block["hash"]
        assert block["receiptsRoot"] == empty_block["receiptsRoot"]
        assert block["logsBloom"] == empty_block["logsBloom"]

    def test_eth_getBlockByHash_not_found(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        with pytest.raises(BlockNotFound):
            w3.eth.get_block(UNKNOWN_HASH)

    def test_eth_getBlockByHash_pending(self, w3: "Web3") -> None:
        block = w3.eth.get_block("pending")
        assert block["hash"] is None

    def test_eth_getBlockByNumber_with_integer(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        block = w3.eth.get_block(empty_block["number"])
        assert block["number"] == empty_block["number"]

    def test_eth_getBlockByNumber_latest(self, w3: "Web3") -> None:
        block = w3.eth.get_block("latest")
        assert block["hash"] is not None

    def test_eth_getBlockByNumber_not_found(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        with pytest.raises(BlockNotFound):
            w3.eth.get_block(BlockNumber(12345))

    def test_eth_getBlockByNumber_pending(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        current_block_number = w3.eth.block_number
        block = w3.eth.get_block("pending")
        assert block["number"] == current_block_number + 1

    def test_eth_getBlockByNumber_earliest(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        genesis_block = w3.eth.get_block(BlockNumber(0))
        block = w3.eth.get_block("earliest")
        assert block["number"] == 0
        assert block["hash"] == genesis_block["hash"]

    def test_eth_getBlockByNumber_safe(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        block = w3.eth.get_block("safe")
        assert block is not None
        assert isinstance(block["number"], int)

    def test_eth_getBlockByNumber_finalized(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        block = w3.eth.get_block("finalized")
        assert block is not None
        assert isinstance(block["number"], int)

    def test_eth_getBlockByNumber_full_transactions(
        self, w3: "Web3", block_with_txn: BlockData
    ) -> None:
        block = w3.eth.get_block(block_with_txn["number"], True)
        transaction = cast(TxData, block["transactions"][0])
        assert transaction["hash"] == block_with_txn["transactions"][0]

    def test_eth_getBlockReceipts_hash(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        receipts = w3.eth.get_block_receipts(empty_block["hash"])
        assert isinstance(receipts, list)

    def test_eth_getBlockReceipts_not_found(self, w3: "Web3") -> None:
        with pytest.raises(BlockNotFound):
            w3.eth.get_block_receipts(UNKNOWN_HASH)

    def test_eth_getBlockReceipts_with_integer(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        receipts = w3.eth.get_block_receipts(empty_block["number"])
        assert isinstance(receipts, list)

    def test_eth_getBlockReceipts_safe(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        receipts = w3.eth.get_block_receipts("safe")
        assert isinstance(receipts, list)

    def test_eth_getBlockReceipts_finalized(
        self, w3: "Web3", empty_block: BlockData
    ) -> None:
        receipts = w3.eth.get_block_receipts("finalized")
        assert isinstance(receipts, list)

    def test_eth_getTransactionByHash(self, w3: "Web3", mined_txn_hash: HexStr) -> None:
        transaction = w3.eth.get_transaction(mined_txn_hash)
        assert is_dict(transaction)
        assert transaction["hash"] == HexBytes(mined_txn_hash)

    def test_eth_getTransactionByHash_contract_creation(
        self, w3: "Web3", math_contract_deploy_txn_hash: HexStr
    ) -> None:
        transaction = w3.eth.get_transaction(math_contract_deploy_txn_hash)
        assert is_dict(transaction)
        assert transaction["to"] is None, f"to field is {transaction['to']!r}"

    def test_eth_getTransactionByBlockHashAndIndex(
        self, w3: "Web3", block_with_txn: BlockData, mined_txn_hash: HexStr
    ) -> None:
        transaction = w3.eth.get_transaction_by_block(block_with_txn["hash"], 0)
        assert is_dict(transaction)
        assert transaction["hash"] == HexBytes(mined_txn_hash)

    def test_eth_getTransactionByBlockNumberAndIndex(
        self, w3: "Web3", block_with_txn: BlockData, mined_txn_hash: HexStr
    ) -> None:
        transaction = w3.eth.get_transaction_by_block(block_with_txn["number"], 0)
        assert is_dict(transaction)
        assert transaction["hash"] == HexBytes(mined_txn_hash)

    def test_eth_get_transaction_receipt_mined(
        self, w3: "Web3", block_with_txn: BlockData, mined_txn_hash: HexStr
    ) -> None:
        receipt = w3.eth.get_transaction_receipt(mined_txn_hash)
        assert is_dict(receipt)
        assert receipt["blockNumber"] == block_with_txn["number"]
        assert receipt["blockHash"] == block_with_txn["hash"]
        assert receipt["transactionIndex"] == 0
        assert receipt["transactionHash"] == HexBytes(mined_txn_hash)
        assert is_checksum_address(receipt["to"])
        assert receipt["from"] is not None
        assert is_checksum_address(receipt["from"])

        effective_gas_price = receipt["effectiveGasPrice"]
        assert isinstance(effective_gas_price, int)
        assert effective_gas_price > 0

    @flaky_geth_dev_mining
    def test_eth_get_transaction_receipt_unmined(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_hash = w3.eth.send_transaction(
            {
                "from": keyfile_account_address_dual_type,
                "to": keyfile_account_address_dual_type,
                "value": Wei(1),
                "gas": 21000,
                "maxFeePerGas": w3.to_wei(3, "gwei"),
                "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
            }
        )
        with pytest.raises(TransactionNotFound):
            w3.eth.get_transaction_receipt(txn_hash)

    def test_eth_get_transaction_receipt_with_log_entry(
        self,
        w3: "Web3",
        block_with_txn_with_log: BlockData,
        emitter_contract: "Contract",
        txn_hash_with_log: HexStr,
    ) -> None:
        receipt = w3.eth.get_transaction_receipt(txn_hash_with_log)
        assert is_dict(receipt)
        assert receipt["blockNumber"] == block_with_txn_with_log["number"]
        assert receipt["blockHash"] == block_with_txn_with_log["hash"]
        assert receipt["transactionIndex"] == 0
        assert receipt["transactionHash"] == HexBytes(txn_hash_with_log)

        assert len(receipt["logs"]) == 1
        log_entry = receipt["logs"][0]

        assert log_entry["blockNumber"] == block_with_txn_with_log["number"]
        assert log_entry["blockHash"] == block_with_txn_with_log["hash"]
        assert log_entry["logIndex"] == 0
        assert is_same_address(log_entry["address"], emitter_contract.address)
        assert log_entry["transactionIndex"] == 0
        assert log_entry["transactionHash"] == HexBytes(txn_hash_with_log)

    def test_eth_wait_for_transaction_receipt_mined(
        self, w3: "Web3", block_with_txn: BlockData, mined_txn_hash: HexStr
    ) -> None:
        receipt = w3.eth.wait_for_transaction_receipt(mined_txn_hash)
        assert is_dict(receipt)
        assert receipt["blockNumber"] == block_with_txn["number"]
        assert receipt["blockHash"] == block_with_txn["hash"]
        assert receipt["transactionIndex"] == 0
        assert receipt["transactionHash"] == HexBytes(mined_txn_hash)
        assert is_checksum_address(receipt["to"])
        assert receipt["from"] is not None
        assert is_checksum_address(receipt["from"])

        effective_gas_price = receipt["effectiveGasPrice"]
        assert isinstance(effective_gas_price, int)
        assert effective_gas_price > 0

    @flaky_geth_dev_mining
    def test_eth_wait_for_transaction_receipt_unmined(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        txn_hash = w3.eth.send_transaction(
            {
                "from": keyfile_account_address_dual_type,
                "to": keyfile_account_address_dual_type,
                "value": Wei(1),
                "gas": 21000,
                "maxFeePerGas": w3.to_wei(3, "gwei"),
                "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
            }
        )

        timeout = 0.01
        with pytest.raises(TimeExhausted) as exc_info:
            w3.eth.wait_for_transaction_receipt(txn_hash, timeout=timeout)

        assert (_ in str(exc_info) for _ in [repr(txn_hash), timeout])

    def test_eth_wait_for_transaction_receipt_with_log_entry(
        self,
        w3: "Web3",
        block_with_txn_with_log: BlockData,
        emitter_contract: "Contract",
        txn_hash_with_log: HexStr,
    ) -> None:
        receipt = w3.eth.wait_for_transaction_receipt(txn_hash_with_log)
        assert is_dict(receipt)
        assert receipt["blockNumber"] == block_with_txn_with_log["number"]
        assert receipt["blockHash"] == block_with_txn_with_log["hash"]
        assert receipt["transactionIndex"] == 0
        assert receipt["transactionHash"] == HexBytes(txn_hash_with_log)

        assert len(receipt["logs"]) == 1
        log_entry = receipt["logs"][0]

        assert log_entry["blockNumber"] == block_with_txn_with_log["number"]
        assert log_entry["blockHash"] == block_with_txn_with_log["hash"]
        assert log_entry["logIndex"] == 0
        assert is_same_address(log_entry["address"], emitter_contract.address)
        assert log_entry["transactionIndex"] == 0
        assert log_entry["transactionHash"] == HexBytes(txn_hash_with_log)

    def test_eth_getUncleByBlockHashAndIndex(self, w3: "Web3") -> None:
        # TODO: how do we make uncles....
        pass

    def test_eth_getUncleByBlockNumberAndIndex(self, w3: "Web3") -> None:
        # TODO: how do we make uncles....
        pass

    def test_eth_new_filter(self, w3: "Web3") -> None:
        filter = w3.eth.filter({})

        changes = w3.eth.get_filter_changes(filter.filter_id)
        assert is_list_like(changes)
        assert not changes

        logs = w3.eth.get_filter_logs(filter.filter_id)
        assert is_list_like(logs)
        assert not logs

        result = w3.eth.uninstall_filter(filter.filter_id)
        assert result is True

    def test_eth_new_block_filter(self, w3: "Web3") -> None:
        filter = w3.eth.filter("latest")
        assert is_string(filter.filter_id)

        changes = w3.eth.get_filter_changes(filter.filter_id)
        assert is_list_like(changes)

        result = w3.eth.uninstall_filter(filter.filter_id)
        assert result is True

    def test_eth_new_pending_transaction_filter(self, w3: "Web3") -> None:
        filter = w3.eth.filter("pending")
        assert is_string(filter.filter_id)

        changes = w3.eth.get_filter_changes(filter.filter_id)
        assert is_list_like(changes)
        assert not changes

        result = w3.eth.uninstall_filter(filter.filter_id)
        assert result is True

    def test_eth_get_logs_without_logs(
        self, w3: "Web3", block_with_txn_with_log: BlockData
    ) -> None:
        # Test with block range

        filter_params: FilterParams = {
            "fromBlock": BlockNumber(0),
            "toBlock": BlockNumber(block_with_txn_with_log["number"] - 1),
        }
        result = w3.eth.get_logs(filter_params)
        assert len(result) == 0

        # the range is wrong
        filter_params = {
            "fromBlock": block_with_txn_with_log["number"],
            "toBlock": BlockNumber(block_with_txn_with_log["number"] - 1),
        }
        with pytest.raises(Web3RPCError):
            w3.eth.get_logs(filter_params)

        # Test with `address`

        # filter with other address
        filter_params = {
            "fromBlock": BlockNumber(0),
            "address": UNKNOWN_ADDRESS,
        }
        result = w3.eth.get_logs(filter_params)
        assert len(result) == 0

        # Test with multiple `address`

        # filter with other address
        filter_params = {
            "fromBlock": BlockNumber(0),
            "address": [UNKNOWN_ADDRESS, UNKNOWN_ADDRESS],
        }
        result = w3.eth.get_logs(filter_params)
        assert len(result) == 0

    def test_eth_get_logs_with_logs(
        self,
        w3: "Web3",
        block_with_txn_with_log: BlockData,
        emitter_contract_address: ChecksumAddress,
        txn_hash_with_log: HexStr,
    ) -> None:
        # Test with block range

        # the range includes the block where the log resides in
        filter_params: FilterParams = {
            "fromBlock": block_with_txn_with_log["number"],
            "toBlock": block_with_txn_with_log["number"],
        }
        result = w3.eth.get_logs(filter_params)
        assert_contains_log(
            result, block_with_txn_with_log, emitter_contract_address, txn_hash_with_log
        )

        # specify only `from_block`. by default `to_block` should be 'latest'
        filter_params = {
            "fromBlock": BlockNumber(0),
        }
        result = w3.eth.get_logs(filter_params)
        assert_contains_log(
            result, block_with_txn_with_log, emitter_contract_address, txn_hash_with_log
        )

        # Test with `address`

        # filter with emitter_contract.address
        filter_params = {
            "fromBlock": BlockNumber(0),
            "address": emitter_contract_address,
        }

    def test_eth_get_logs_with_logs_topic_args(
        self,
        w3: "Web3",
        block_with_txn_with_log: BlockData,
        emitter_contract_address: ChecksumAddress,
        txn_hash_with_log: HexStr,
    ) -> None:
        # Test with None event sig

        filter_params: FilterParams = {
            "fromBlock": BlockNumber(0),
            "topics": [
                None,
                HexStr(
                    "0x000000000000000000000000000000000000000000000000000000000000d431"
                ),
            ],
        }

        result = w3.eth.get_logs(filter_params)
        assert_contains_log(
            result, block_with_txn_with_log, emitter_contract_address, txn_hash_with_log
        )

        # Test with None indexed arg
        filter_params = {
            "fromBlock": BlockNumber(0),
            "topics": [
                HexStr(
                    "0x057bc32826fbe161da1c110afcdcae7c109a8b69149f727fc37a603c60ef94ca"
                ),
                None,
            ],
        }
        result = w3.eth.get_logs(filter_params)
        assert_contains_log(
            result, block_with_txn_with_log, emitter_contract_address, txn_hash_with_log
        )

    def test_eth_get_logs_with_logs_none_topic_args(self, w3: "Web3") -> None:
        # Test with None overflowing
        filter_params: FilterParams = {
            "fromBlock": BlockNumber(0),
            "topics": [None, None, None],
        }

        result = w3.eth.get_logs(filter_params)
        assert len(result) == 0

    def test_eth_call_old_contract_state(
        self,
        w3: "Web3",
        math_contract: "Contract",
        keyfile_account_address: ChecksumAddress,
    ) -> None:
        current_block = w3.eth.get_block("latest")
        block_num = current_block["number"]
        block_hash = current_block["hash"]

        default_call_result = math_contract.functions.counter().call()
        latest_call_result = math_contract.functions.counter().call(
            block_identifier="latest"
        )

        # increment counter and get tx receipt
        tx_hash = math_contract.functions.incrementCounter().transact(
            {"from": keyfile_account_address}
        )
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # get new state value
        post_state_block_num_call_result = math_contract.functions.counter().call(
            block_identifier=tx_receipt["blockNumber"]
        )

        # call old state values with different block identifiers
        block_hash_call_result = math_contract.functions.counter().call(
            block_identifier=block_hash
        )
        pre_state_block_num_call_result = math_contract.functions.counter().call(
            block_identifier=block_num
        )

        # assert old state values before incrementing counter
        assert pre_state_block_num_call_result == post_state_block_num_call_result - 1
        assert (
            pre_state_block_num_call_result
            == block_hash_call_result
            == default_call_result
            == latest_call_result
        )

    def test_eth_uninstall_filter(self, w3: "Web3") -> None:
        filter = w3.eth.filter({})
        assert is_string(filter.filter_id)

        success = w3.eth.uninstall_filter(filter.filter_id)
        assert success is True

        failure = w3.eth.uninstall_filter(filter.filter_id)
        assert failure is False

    def test_eth_get_raw_transaction(self, w3: "Web3", mined_txn_hash: HexStr) -> None:
        raw_transaction = w3.eth.get_raw_transaction(mined_txn_hash)
        assert is_bytes(raw_transaction)

    def test_eth_get_raw_transaction_raises_error(self, w3: "Web3") -> None:
        with pytest.raises(
            TransactionNotFound, match=f"Transaction with hash: '{UNKNOWN_HASH}'"
        ):
            w3.eth.get_raw_transaction(UNKNOWN_HASH)

    def test_eth_get_raw_transaction_by_block(
        self,
        w3: "Web3",
        keyfile_account_address_dual_type: ChecksumAddress,
        block_with_txn: BlockData,
    ) -> None:
        # eth_getRawTransactionByBlockNumberAndIndex: block identifier
        w3.eth.send_transaction(
            {
                "from": keyfile_account_address_dual_type,
                "to": keyfile_account_address_dual_type,
                "value": Wei(1),
            }
        )
        raw_transaction = None
        while not raw_transaction:
            try:
                raw_transaction = w3.eth.get_raw_transaction_by_block("latest", 0)
            except TransactionNotFound:
                continue

        assert is_bytes(raw_transaction)

        # eth_getRawTransactionByBlockNumberAndIndex: block number
        block_with_txn_number = block_with_txn["number"]
        assert is_integer(block_with_txn_number)
        raw_transaction = w3.eth.get_raw_transaction_by_block(block_with_txn_number, 0)
        assert is_bytes(raw_transaction)

        # eth_getRawTransactionByBlockHashAndIndex: block hash
        block_with_txn_hash = block_with_txn["hash"]
        assert is_bytes(block_with_txn_hash)
        raw_transaction = w3.eth.get_raw_transaction_by_block(block_with_txn_hash, 0)
        assert is_bytes(raw_transaction)

    @pytest.mark.parametrize("unknown_block_num_or_hash", (1234567899999, UNKNOWN_HASH))
    def test_eth_get_raw_transaction_by_block_raises_error(
        self, w3: "Web3", unknown_block_num_or_hash: Union[int, HexBytes]
    ) -> None:
        with pytest.raises(
            TransactionNotFound,
            match=(
                f"Transaction index: 0 on block id: "
                f"{to_hex_if_integer(unknown_block_num_or_hash)!r} not found."
            ),
        ):
            w3.eth.get_raw_transaction_by_block(unknown_block_num_or_hash, 0)

    def test_eth_get_raw_transaction_by_block_raises_error_block_identifier(
        self, w3: "Web3"
    ) -> None:
        unknown_identifier = "unknown"
        with pytest.raises(
            Web3ValueError,
            match=(
                "Value did not match any of the recognized block identifiers: "
                f"{unknown_identifier}"
            ),
        ):
            # type ignored because we are testing an invalid input
            w3.eth.get_raw_transaction_by_block(unknown_identifier, 0)  # type: ignore

    def test_default_account(
        self, w3: "Web3", keyfile_account_address_dual_type: ChecksumAddress
    ) -> None:
        current_default = w3.eth.default_account

        # check setter
        w3.eth.default_account = keyfile_account_address_dual_type
        default_account = w3.eth.default_account
        assert default_account == keyfile_account_address_dual_type

        # reset to default
        w3.eth.default_account = current_default

    def test_default_block(
        self,
        w3: "Web3",
    ) -> None:
        # check defaults to 'latest'
        default_block = w3.eth.default_block
        assert default_block == "latest"

        # check setter
        w3.eth.default_block = BlockNumber(12345)
        default_block = w3.eth.default_block
        assert default_block == BlockNumber(12345)

        # reset to default
        w3.eth.default_block = "latest"
