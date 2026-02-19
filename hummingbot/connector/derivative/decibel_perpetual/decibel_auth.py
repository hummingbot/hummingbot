import os
from aptos_sdk.account import Account
from aptos_sdk.client import RestClient
from hummingbot.connector.derivative.decibel_perpetual.decibel_utils import TRADING_HTTP_URL

class DecibelAuth:
    """
    Handles Aptos Account signing and Decibel API authentication.
    """
    def __init__(self, private_key: str, api_key: str = None):
        self.account = Account.load_key(private_key)
        self.api_key = api_key # The Bearer key requested from maintainers

    def get_auth_headers(self) -> dict:
        """
        Returns headers for REST API calls.
        """
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Some exchanges require a signature in headers for private endpoints
        # Decibel SDK seems to focus on on-chain transactions for 'write' ops.
        return headers

    def sign_transaction(self, payload: dict):
        """
        Signs a Move transaction payload for Decibel.
        """
        # This will interface with aptos-sdk to build and sign
        pass

if __name__ == "__main__":
    # Test loading (fake key for structure check)
    # 32 bytes hex
    fake_key = "0x" + "1" * 64
    auth = DecibelAuth(fake_key, "test_api_key")
    print(f"✅ Auth initialized for address: {auth.account.address()}")
    print(f"📡 Headers: {auth.get_auth_headers()}")
