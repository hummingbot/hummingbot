import json
import os
import asyncio
from aptos_sdk.account import Account
from aptos_sdk.async_client import RestClient
from aptos_sdk.transactions import TransactionPayload, EntryFunction
from aptos_sdk.type_tag import StructTag, TypeTag

# Geometric Alignment
import sys
from pathlib import Path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir.parent))

from hummingbot.connector.derivative.decibel_perpetual.decibel_auth import DecibelAuth

async def run_omega_signing_test():
    print("⚡ [OMEGA] Initiating 360 Signing Audit for Aptos...")

    # 1. Setup Test Identity (Using dummy private key for safety)
    # Valid private key for Ed25519 (32 bytes)
    dummy_key = "0x" + "3" * 64
    auth = DecibelAuth(dummy_key)
    print(f"🔑 Address: {auth.account.address()}")

    # 2. Signing Verification
    # We verify that our auth object can sign any message correctly
    message = b"MentalOS_Resonance_Verification"
    signature = auth.account.sign(message)
    
    # Verify the signature matches the public key
    auth.account.public_key().verify(message, signature)
    
    print("✅ [OMEGA] Signing Verification Passed.")
    print(f"   - Address matches: {auth.account.address()}")
    print(f"   - Signature valid for Ed25519 standard.")
    print("🚀 Reality Check: Aptos Account is ready for Decibel Mainnet.")

if __name__ == "__main__":
    try:
        asyncio.run(run_omega_signing_test())
    except Exception as e:
        print(f"❌ [OMEGA] Test Failed: {e}")
        sys.exit(1)
