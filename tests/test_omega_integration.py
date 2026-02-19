import os
import sys
from pathlib import Path

current_dir = Path(__file__).parent
connector_dir = current_dir.parent
sys.path.append(str(connector_dir))

from hummingbot.connector.derivative.decibel_perpetual.decibel_auth import DecibelAuth
from aptos_sdk.bcs import Serializer

def run_omega_test():
    print("⚡ [OMEGA] Initiating FINAL PHYSICAL AUDIT...")
    
    fake_key = "0x" + "1" * 64
    auth = DecibelAuth(fake_key)
    
    market_id = "0x1::market::eth_usdc"
    payload = auth.build_decibel_payload(market_id, "buy", 100000000, 2500000000)
    
    # Introspect payload to find DAO Treasury
    DAO_TREASURY_SHORT = "b704a40cb6557ec1352a05bc5990a77b85ae3d67"
    
    # USE THE VERIFIED 'serialize' METHOD
    s = Serializer()
    payload.serialize(s)
    hex_payload = s.output().hex()
    
    if DAO_TREASURY_SHORT in hex_payload:
        print(f"✅ [OMEGA] Fee Valve detected in physical bytes: {DAO_TREASURY_SHORT}")
    else:
        print("❌ [OMEGA] CRITICAL: Fee Valve NOT found in physical bytes!")
        print(f"DEBUG Hex: {hex_payload}")
        sys.exit(1)

    print("💎 [OMEGA] ALL SYSTEMS GO. Integration is 100% Physical.")

if __name__ == "__main__":
    run_omega_test()
