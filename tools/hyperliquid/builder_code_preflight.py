#!/usr/bin/env python
"""
Hyperliquid builder-code pre-flight check (HGP-87).

A zero-risk smoke test to run BEFORE pointing the builder-code feature at a funded
wallet. It exercises the real connector auth classes - no order is ever placed.

Two checks:

  1. Offline sign-and-recover (default, no network, no funds, throwaway key):
     builds an order action with the builder field exactly as the connector does on
     mainnet, signs it with the real ``HyperliquidAuth`` / ``HyperliquidPerpetualAuth``,
     and independently recovers the signer from the signature. This proves the
     signature is valid AND that it covers the builder field (tampering the fee after
     signing must break recovery). This is the same check Hyperliquid's backend runs.

  2. Live read-only approval query (``--live``, requires ``--user``):
     POSTs ``maxBuilderFee`` to the public ``/info`` endpoint (no auth, no order, no
     funds) and applies the ``get_builder_info`` approval logic. At a 0 bps fee the
     pair is approved trivially (``approved_max >= 0``), which is why the Foundation
     default needs no ``ApproveBuilderFee`` action.

NOTE: testnet does NOT exercise the builder path - the connector omits the builder
field on testnet by design - so these checks are the meaningful pre-flight validation.

Usage (run from the repo root):

    python tools/hyperliquid/builder_code_preflight.py
    python tools/hyperliquid/builder_code_preflight.py --builder 0xYourBuilderAddress --fee-bps 0
    python tools/hyperliquid/builder_code_preflight.py --live --user 0xYourWalletAddress \
        --builder 0xYourBuilderAddress
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

import aiohttp
import eth_account
from eth_account import Account
from eth_account.messages import encode_typed_data

# Allow running standalone from a source checkout without installing the package.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Fixed EIP-712 envelope for Hyperliquid L1 actions (mirrors auth.sign_l1_action).
_DOMAIN = {
    "chainId": 1337,
    "name": "Exchange",
    "verifyingContract": "0x0000000000000000000000000000000000000000",
    "version": "1",
}
_TYPES = {
    "Agent": [
        {"name": "source", "type": "string"},
        {"name": "connectionId", "type": "bytes32"},
    ],
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
}

_SAMPLE_BUILDER = "0xAbC0000000000000000000000000000000000001"
_SAMPLE_CLOID = "0x000000000000000000000000000ee056"


def _recover_signer(auth, signed_action: dict, nonce: int, sig: dict, is_mainnet: bool) -> str:
    """Recompute the phantom-agent hash from the EXACT signed action and recover the signer address."""
    action_hash = auth.action_hash(signed_action, auth._vault_address, nonce)
    phantom_agent = auth.construct_phantom_agent(action_hash, is_mainnet)
    data = {"domain": _DOMAIN, "types": _TYPES, "primaryType": "Agent", "message": phantom_agent}
    encoded = encode_typed_data(full_message=data)
    return Account.recover_message(encoded, vrs=(sig["v"], int(sig["r"], 16), int(sig["s"], 16)))


def _build_cases(secret: str, builder_address: str, fee_tenths_bps: int):
    """One signing case per connector, using the real auth classes."""
    from hummingbot.connector.derivative.hyperliquid_perpetual import hyperliquid_perpetual_constants as perp_const
    from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_auth import (
        HyperliquidPerpetualAuth,
    )
    from hummingbot.connector.exchange.hyperliquid import hyperliquid_constants as spot_const
    from hummingbot.connector.exchange.hyperliquid.hyperliquid_auth import HyperliquidAuth

    address = eth_account.Account.from_key(secret).address
    builder_field = {"b": builder_address.lower(), "f": fee_tenths_bps}
    return {
        "perp": {
            "auth": HyperliquidPerpetualAuth(address, secret, use_vault=False),
            "url": perp_const.PERPETUAL_BASE_URL + "/exchange",
            "info_url": perp_const.PERPETUAL_BASE_URL + "/info",
            "asset": 4,
            "builder_field": builder_field,
        },
        "spot": {
            "auth": HyperliquidAuth(address, secret, use_vault=False),
            "url": spot_const.BASE_URL + "/exchange",
            "info_url": spot_const.BASE_URL + "/info",
            "asset": 10004,
            "builder_field": builder_field,
        },
    }


def run_sign_and_recover(connectors, secret: str, builder_address: str, fee_tenths_bps: int) -> bool:
    signer = eth_account.Account.from_key(secret).address
    print(f"Throwaway signer wallet : {signer}")
    print(f"Builder address         : {builder_address.lower()}")
    print(f"Builder fee (f / bps)   : {fee_tenths_bps} tenths-bps = {fee_tenths_bps / 10} bps")

    cases = _build_cases(secret, builder_address, fee_tenths_bps)
    all_ok = True
    for label in connectors:
        case = cases[label]
        auth = case["auth"]
        params = {
            "type": "order",
            "grouping": "na",
            "orders": {
                "asset": case["asset"],
                "isBuy": True,
                "limitPx": 1200,
                "sz": 0.01,
                "reduceOnly": False,
                "orderType": {"limit": {"tif": "Gtc"}},
                "cloid": _SAMPLE_CLOID,
            },
            "builder": case["builder_field"],
        }
        payload = json.loads(auth.add_auth_to_params_post(json.dumps(params), case["url"]))
        action, sig, nonce = payload["action"], payload["signature"], payload["nonce"]

        has_builder = action.get("builder") == case["builder_field"]
        recovered = _recover_signer(auth, action, nonce, sig, is_mainnet=True)
        signer_match = recovered.lower() == signer.lower()

        # Tamper test: bump the fee in the signed action; recovery must no longer match.
        tampered = json.loads(json.dumps(action))
        tampered["builder"]["f"] = fee_tenths_bps + 100
        tamper_recovered = _recover_signer(auth, tampered, nonce, sig, is_mainnet=True)
        tamper_detected = tamper_recovered.lower() != signer.lower()

        ok = has_builder and signer_match and tamper_detected
        all_ok = all_ok and ok
        print(f"\n[{label.upper()}]")
        print(f"  signed action contains builder field : {has_builder}")
        print(f"  signature recovers to signer wallet  : {signer_match}")
        print(f"  fee tamper breaks the signature      : {tamper_detected}")
        print(f"  builder in signed action             : {json.dumps(action.get('builder'))}")
        print(f"  => {'PASS' if ok else 'FAIL'}")
    return all_ok


async def run_live_builder_info(connectors, user_address: str, builder_address: str) -> bool:
    cases = _build_cases(eth_account.Account.create().key.hex(), builder_address, 0)
    timeout = aiohttp.ClientTimeout(total=15)
    all_ok = True
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for label in connectors:
            info_url = cases[label]["info_url"]
            body = {"type": "maxBuilderFee", "user": user_address, "builder": builder_address.lower()}
            try:
                async with session.post(info_url, json=body, headers={"Content-Type": "application/json"}) as resp:
                    text = await resp.text()
                    approved_max = int(json.loads(text))
                    # get_builder_info approval logic at the (default 0 bps) Foundation fee:
                    approved = approved_max >= 0
                    ok = resp.status == 200 and approved
                    all_ok = all_ok and ok
                    print(f"\n[{label.upper()}] live maxBuilderFee @ {info_url}")
                    print(f"  user                     : {user_address}")
                    print(f"  approved_max (tenths-bps): {approved_max}")
                    print(f"  approved at 0 bps        : {approved}")
                    print(f"  => {'PASS' if ok else 'FAIL'}")
            except Exception as exc:  # network may be restricted in some environments
                all_ok = False
                print(f"\n[{label.upper()}] live query FAILED: {type(exc).__name__}: {exc}")
    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Hyperliquid builder-code pre-flight check (HGP-87).")
    parser.add_argument("--connector", choices=["perp", "spot", "both"], default="both",
                        help="Which connector(s) to check (default: both).")
    parser.add_argument("--builder", default=_SAMPLE_BUILDER,
                        help="Builder address to attribute orders to (default: a sample address).")
    parser.add_argument("--fee-bps", type=int, default=0,
                        help="Builder fee in basis points (default: 0 = attribution only).")
    parser.add_argument("--live", action="store_true",
                        help="Also run the read-only mainnet maxBuilderFee query (requires --user).")
    parser.add_argument("--user", default=None,
                        help="Your wallet address, required with --live for the maxBuilderFee query.")
    args = parser.parse_args()

    connectors = ["perp", "spot"] if args.connector == "both" else [args.connector]
    secret = eth_account.Account.create().key.hex()  # throwaway key; never a real wallet
    fee_tenths_bps = args.fee_bps * 10

    print("=" * 60)
    print("Hyperliquid builder-code pre-flight (offline sign-and-recover)")
    print("=" * 60)
    offline_ok = run_sign_and_recover(connectors, secret, args.builder, fee_tenths_bps)

    live_ok = True
    if args.live:
        if not args.user:
            parser.error("--live requires --user <your wallet address>")
        print("\n" + "=" * 60)
        print("Live read-only maxBuilderFee query (no auth, no order, no funds)")
        print("=" * 60)
        live_ok = asyncio.run(run_live_builder_info(connectors, args.user, args.builder))

    overall = offline_ok and live_ok
    print(f"\n{'=' * 60}\nOVERALL: {'ALL CHECKS PASS' if overall else 'FAILURE - DO NOT GO LIVE'}")
    print("Reminder: testnet omits the builder field by design; these checks are the")
    print("meaningful pre-flight validation before using a funded mainnet wallet.")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
