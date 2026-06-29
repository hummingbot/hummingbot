"""Shared Hyperliquid user-signed-action signing (EIP-712), used by the agent-wallet and
builder-fee scripts.

Hyperliquid "user-signed actions" (approveAgent, approveBuilderFee, withdraw, …) are signed with
EIP-712 typed data — distinct from L1 order signing. The schema mirrors the official
hyperliquid-python-sdk: a fixed `HyperliquidSignTransaction` domain on chainId 421614
(signatureChainId 0x66eee) for both mainnet and testnet, with `hyperliquidChain` ("Mainnet"/"Testnet")
distinguishing the network inside the signed message.

No third-party deps beyond eth_account (already a Hummingbot dependency).
"""
import json
import urllib.request
from typing import Any, Dict, List, Tuple

from eth_account import Account
from eth_account.messages import encode_typed_data

SIGNATURE_CHAIN_ID = "0x66eee"   # fixed for HL user-signed actions (== 421614)
DOMAIN_CHAIN_ID = 421614
MAINNET_EXCHANGE = "https://api.hyperliquid.xyz/exchange"
TESTNET_EXCHANGE = "https://api.hyperliquid-testnet.xyz/exchange"


def sign_user_action(
    private_key: str,
    action_type: str,
    primary_type: str,
    payload_types: List[Dict[str, str]],
    fields: Dict[str, Any],
    is_mainnet: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Sign a Hyperliquid user-signed action.

    `fields` are exactly the hashed payload fields (matching payload_types, minus the auto-added
    hyperliquidChain). Returns (full_action, signature, signer_address): `full_action` is the dict to
    POST (with `type`, `signatureChainId`, `hyperliquidChain` filled in); `signature` is {r, s, v};
    `signer_address` is recovered from the signature so the caller can assert it matches the main
    wallet.
    """
    acct = Account.from_key(private_key)

    # Only the typed payload fields are hashed (must match payload_types names exactly).
    message = dict(fields)
    message["hyperliquidChain"] = "Mainnet" if is_mainnet else "Testnet"

    typed = {
        "domain": {
            "name": "HyperliquidSignTransaction",
            "version": "1",
            "chainId": DOMAIN_CHAIN_ID,
            "verifyingContract": "0x0000000000000000000000000000000000000000",
        },
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            primary_type: payload_types,
        },
        "primaryType": primary_type,
        "message": message,
    }
    signable = encode_typed_data(full_message=typed)
    signed = Account.sign_message(signable, private_key)

    # Self-verify: recover the signer and confirm it's the key we signed with.
    recovered = Account.recover_message(signable, signature=signed.signature)
    if recovered.lower() != acct.address.lower():
        raise RuntimeError(
            f"Signature self-check failed: recovered {recovered} != signer {acct.address}")

    full_action = {"type": action_type, **fields,
                   "signatureChainId": SIGNATURE_CHAIN_ID,
                   "hyperliquidChain": message["hyperliquidChain"]}
    signature = {"r": f"0x{signed.r:064x}", "s": f"0x{signed.s:064x}", "v": signed.v}
    return full_action, signature, recovered


def post_exchange(action: Dict[str, Any], signature: Dict[str, Any], nonce: int,
                  is_mainnet: bool) -> Dict[str, Any]:
    """POST a signed action to the Hyperliquid /exchange endpoint."""
    url = MAINNET_EXCHANGE if is_mainnet else TESTNET_EXCHANGE
    body = {"action": action, "nonce": nonce, "signature": signature}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())
