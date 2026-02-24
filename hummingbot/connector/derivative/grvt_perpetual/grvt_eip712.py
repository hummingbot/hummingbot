from typing import Any, Dict

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak, to_hex


def build_action_typed_data(
    account_address: str,
    action_payload: Dict[str, Any],
    nonce: int,
    chain_id: int = 1,
    verifying_contract: str = "0x0000000000000000000000000000000000000000",
) -> Dict[str, Any]:
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Action": [
                {"name": "account", "type": "address"},
                {"name": "nonce", "type": "uint256"},
                {"name": "payloadHash", "type": "bytes32"},
            ],
        },
        "primaryType": "Action",
        "domain": {
            "name": "GRVT",
            "version": "1",
            "chainId": chain_id,
            "verifyingContract": verifying_contract,
        },
        "message": {
            "account": account_address,
            "nonce": nonce,
            "payloadHash": _payload_hash_hex(action_payload),
        },
    }


def sign_typed_action(private_key: str, typed_data: Dict[str, Any]) -> Dict[str, Any]:
    wallet = Account.from_key(private_key)
    signed = wallet.sign_message(encode_typed_data(full_message=typed_data))
    return {
        "r": to_hex(signed.r),
        "s": to_hex(signed.s),
        "v": int(signed.v),
        "signature": signed.signature.hex(),
        "messageHash": signed.message_hash.hex(),
    }


def _payload_hash_hex(action_payload: Dict[str, Any]) -> str:
    import json

    payload_bytes = json.dumps(action_payload, sort_keys=True, separators=(",", ":")).encode()
    digest = keccak(payload_bytes)
    return f"0x{digest.hex()}"
