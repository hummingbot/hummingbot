#!/usr/bin/env python3
"""(Optional) Approve a Hyperliquid builder fee for a builder address.

Most `hbot` users do NOT need this: open-source Hummingbot attaches the Foundation builder code at
0 bps, so there is nothing to approve. Use this only if you intentionally want to authorize a
non-zero builder fee (e.g. to support a builder, or to match a Condor-hosted setup). Approving a fee
authorizes the builder to charge up to `max_fee_rate` on your fills.

Secrets: the main wallet key is read from $HL_MAIN_KEY or stdin — NEVER pass it on argv.

Usage:
    python approve_builder_fee.py --builder 0xABC... --max-fee 0.001%            # DRY RUN
    python approve_builder_fee.py --builder 0xABC... --max-fee 0.001% --submit   # submit
    python approve_builder_fee.py --builder 0xABC... --max-fee 0.001% --submit --testnet

Requires eth_account (a Hummingbot dependency). Mainnet by default.
"""
import argparse
import json
import os
import sys
import time

from _hl_sign import post_exchange, sign_user_action
from eth_account import Account

APPROVE_BUILDER_FEE_TYPES = [
    {"name": "hyperliquidChain", "type": "string"},
    {"name": "maxFeeRate", "type": "string"},
    {"name": "builder", "type": "address"},
    {"name": "nonce", "type": "uint64"},
]


def _read_main_key() -> str:
    key = os.environ.get("HL_MAIN_KEY")
    if not key:
        key = sys.stdin.readline().strip()
    if not key:
        raise SystemExit("No main wallet key provided (set $HL_MAIN_KEY or pipe via stdin).")
    return key if key.startswith("0x") else "0x" + key


def main() -> int:
    ap = argparse.ArgumentParser(description="Approve a Hyperliquid builder fee (optional).")
    ap.add_argument("--builder", required=True, help="builder address to authorize (0x...)")
    ap.add_argument("--max-fee", required=True, dest="max_fee",
                    help="max fee rate as a percent string, e.g. '0.001%%'")
    ap.add_argument("--submit", action="store_true",
                    help="actually POST (default is a dry run that prints the signed payload)")
    ap.add_argument("--testnet", action="store_true")
    args = ap.parse_args()
    is_mainnet = not args.testnet

    if not args.max_fee.strip().endswith("%"):
        raise SystemExit("--max-fee must be a percent string ending in '%', e.g. '0.001%'")

    main_key = _read_main_key()
    nonce = int(time.time() * 1000)
    fields = {"maxFeeRate": args.max_fee, "builder": args.builder.lower(), "nonce": nonce}
    action, signature, signer = sign_user_action(
        main_key, "approveBuilderFee", "HyperliquidTransaction:ApproveBuilderFee",
        APPROVE_BUILDER_FEE_TYPES, fields, is_mainnet)
    main_address = Account.from_key(main_key).address

    print("=== approveBuilderFee action (signed) ===")
    print(json.dumps({"action": action, "nonce": nonce, "signature": signature}, indent=2))
    print(f"\n  recovered signer : {signer}")
    print(f"  main wallet      : {main_address}  ({'OK' if signer.lower() == main_address.lower() else 'MISMATCH'})")

    if not args.submit:
        print("\nDRY RUN — not submitted. Re-run with --submit to approve on-chain.")
        return 0

    print("\nSubmitting to Hyperliquid /exchange ...")
    resp = post_exchange(action, signature, nonce, is_mainnet)
    print(json.dumps(resp, indent=2))
    ok = isinstance(resp, dict) and resp.get("status") == "ok"
    print(f"\n{'Approved.' if ok else 'Approval may have failed — check the response above.'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
