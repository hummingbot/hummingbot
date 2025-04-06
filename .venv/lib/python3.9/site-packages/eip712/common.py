# flake8: noqa F821
# Collection of commonly-used EIP712 message type definitions
from typing import Optional, Type, Union

from .messages import EIP712Message


class EIP2612(EIP712Message):
    # NOTE: Subclass this w/ at least one header field

    owner: "address"  # type: ignore
    spender: "address"  # type: ignore
    value: "uint256"  # type: ignore
    nonce: "uint256"  # type: ignore
    deadline: "uint256"  # type: ignore


class EIP4494(EIP712Message):
    # NOTE: Subclass this w/ at least one header field

    spender: "address"  # type: ignore
    tokenId: "uint256"  # type: ignore
    nonce: "uint256"  # type: ignore
    deadline: "uint256"  # type: ignore


def create_permit_def(eip=2612, **header_fields):
    if eip == 2612:

        class Permit(EIP2612):
            _name_ = header_fields.get("name", None)
            _version_ = header_fields.get("version", None)
            _chainId_ = header_fields.get("chainId", None)
            _verifyingContract_ = header_fields.get("verifyingContract", None)
            _salt_ = header_fields.get("salt", None)

    elif eip == 4494:

        class Permit(EIP4494):
            _name_ = header_fields.get("name", None)
            _version_ = header_fields.get("version", None)
            _chainId_ = header_fields.get("chainId", None)
            _verifyingContract_ = header_fields.get("verifyingContract", None)
            _salt_ = header_fields.get("salt", None)

    else:
        raise ValueError(f"Invalid eip {eip}, must use one of: {EIP2612}, {EIP4494}")

    return Permit


class SafeTxV1(EIP712Message):
    # NOTE: Subclass this as `SafeTx` w/ at least one header field
    to: "address"  # type: ignore
    value: "uint256" = 0  # type: ignore
    data: "bytes" = b""
    operation: "uint8" = 0  # type: ignore
    safeTxGas: "uint256" = 0  # type: ignore
    dataGas: "uint256" = 0  # type: ignore
    gasPrice: "uint256" = 0  # type: ignore
    gasToken: "address" = "0x0000000000000000000000000000000000000000"  # type: ignore
    refundReceiver: "address" = "0x0000000000000000000000000000000000000000"  # type: ignore
    nonce: "uint256"  # type: ignore


class SafeTxV2(EIP712Message):
    # NOTE: Subclass this as `SafeTx` w/ at least one header field
    to: "address"  # type: ignore
    value: "uint256" = 0  # type: ignore
    data: "bytes" = b""
    operation: "uint8" = 0  # type: ignore
    safeTxGas: "uint256" = 0  # type: ignore
    baseGas: "uint256" = 0  # type: ignore
    gasPrice: "uint256" = 0  # type: ignore
    gasToken: "address" = "0x0000000000000000000000000000000000000000"  # type: ignore
    refundReceiver: "address" = "0x0000000000000000000000000000000000000000"  # type: ignore
    nonce: "uint256"  # type: ignore


SafeTx = Union[SafeTxV1, SafeTxV2]
SAFE_VERSIONS = {"1.0.0", "1.1.0", "1.1.1", "1.2.0", "1.3.0", "1.4.1"}


def create_safe_tx_def(
    version: str = "1.3.0",
    contract_address: Optional[str] = None,
    chain_id: Optional[int] = None,
) -> type[SafeTx]:
    if not contract_address:
        raise ValueError("Must define 'contract_address'")

    if version not in SAFE_VERSIONS:
        raise ValueError(f"Unknown version {version}")

    major, minor, patch = map(int, version.split("."))

    if minor < 3:

        class SafeTx(SafeTxV1):
            _verifyingContract_ = contract_address

    elif not chain_id:
        raise ValueError("Must supply 'chain_id=' for Safe versions 1.3.0 or later")

    else:

        class SafeTx(SafeTxV2):  # type: ignore[no-redef]
            _chainId_ = chain_id
            _verifyingContract_ = contract_address

    return SafeTx
