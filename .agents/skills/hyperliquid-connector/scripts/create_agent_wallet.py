#!/usr/bin/env python3
"""Create (and optionally authorize) a Hyperliquid API/agent wallet for use with `hbot connect`.

An agent wallet (a.k.a. API wallet) is a separate key authorized to **trade** on your account but
**not** to withdraw — the safe way to run a bot. This script generates the keypair locally, then
(with --authorize) signs an `approveAgent` action with your MAIN wallet key and submits it so
Hyperliquid recognizes the agent.

Then in Hummingbot connect with mode `api_wallet`:
    address    = your MAIN account address (holds the funds)
    secret_key = the AGENT private key this script prints

Secrets: the main wallet key is read from $HL_MAIN_KEY or stdin — NEVER pass it on argv. The
generated agent key is printed once; store it securely.

Usage:
    python create_agent_wallet.py                         # just generate a keypair (you authorize later)
    python create_agent_wallet.py --authorize             # generate + sign approveAgent (DRY RUN: prints payload)
    python create_agent_wallet.py --authorize --submit    # generate + actually submit the authorization
    python create_agent_wallet.py --authorize --submit --testnet --name hbot

Requires eth_account (a Hummingbot dependency). Mainnet by default.
"""
import argparse
import json
import os
import sys
import time

from _hl_sign import post_exchange, sign_user_action
from eth_account import Account

APPROVE_AGENT_TYPES = [
    {"name": "hyperliquidChain", "type": "string"},
    {"name": "agentAddress", "type": "address"},
    {"name": "agentName", "type": "string"},
    {"name": "nonce", "type": "uint64"},
]


def _read_main_key() -> str:
    key = os.environ.get("HL_MAIN_KEY")
    if not key:
        if sys.stdin.isatty():
            sys.stderr.write("Enter MAIN wallet private key (input hidden via stdin pipe preferred): ")
            sys.stderr.flush()
        key = sys.stdin.readline().strip()
    if not key:
        raise SystemExit("No main wallet key provided (set $HL_MAIN_KEY or pipe via stdin).")
    return key if key.startswith("0x") else "0x" + key


def main() -> int:
    ap = argparse.ArgumentParser(description="Create/authorize a Hyperliquid agent (API) wallet.")
    ap.add_argument("--authorize", action="store_true",
                    help="sign an approveAgent action with the main wallet key (else just generate)")
    ap.add_argument("--submit", action="store_true",
                    help="actually POST the authorization (default is a dry run that prints it)")
    ap.add_argument("--name", default="hbot", help="agent name (default: hbot)")
    ap.add_argument("--testnet", action="store_true")
    args = ap.parse_args()
    is_mainnet = not args.testnet

    # 1. Generate the agent keypair locally.
    agent = Account.create()
    agent_address, agent_key = agent.address, agent.key.hex()
    agent_key = agent_key if agent_key.startswith("0x") else "0x" + agent_key

    print("=== Agent (API) wallet generated ===")
    print(f"  agent address     : {agent_address}")
    print(f"  agent private key : {agent_key}")
    print("  ^ store this key securely; it is shown only once.\n")

    if not args.authorize:
        print("Not authorized yet. Either:")
        print("  - re-run with --authorize --submit (needs your MAIN wallet key via $HL_MAIN_KEY), or")
        print("  - authorize this agent in the UI at https://app.hyperliquid.xyz/API\n")
        print("Then `hbot connect hyperliquid_perpetual` with mode=api_wallet,")
        print("  address=<your MAIN account address>, secret_key=<the agent key above>.")
        return 0

    # 2. Build + sign the approveAgent action with the MAIN wallet key.
    main_key = _read_main_key()
    nonce = int(time.time() * 1000)
    fields = {"agentAddress": agent_address, "agentName": args.name, "nonce": nonce}
    action, signature, signer = sign_user_action(
        main_key, "approveAgent", "HyperliquidTransaction:ApproveAgent",
        APPROVE_AGENT_TYPES, fields, is_mainnet)
    main_address = Account.from_key(main_key).address

    print("=== approveAgent action (signed) ===")
    print(json.dumps({"action": action, "nonce": nonce, "signature": signature}, indent=2))
    print(f"\n  recovered signer  : {signer}")
    print(f"  main wallet       : {main_address}  ({'OK' if signer.lower() == main_address.lower() else 'MISMATCH'})")

    if not args.submit:
        print("\nDRY RUN — not submitted. Re-run with --submit to authorize on-chain.")
        return 0

    print("\nSubmitting to Hyperliquid /exchange ...")
    resp = post_exchange(action, signature, nonce, is_mainnet)
    print(json.dumps(resp, indent=2))
    ok = isinstance(resp, dict) and resp.get("status") == "ok"
    print(f"\n{'Authorized.' if ok else 'Authorization may have failed — check the response above.'}")
    if ok:
        print(f"Now `hbot connect hyperliquid_perpetual`: mode=api_wallet, "
              f"address={main_address}, secret_key=<the agent key above>.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
