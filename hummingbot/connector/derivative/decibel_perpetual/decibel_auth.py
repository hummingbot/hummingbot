import os
from aptos_sdk.account import Account
from aptos_sdk.transactions import (
    RawTransaction, 
    SignedTransaction, 
    TransactionPayload, 
    EntryFunction, 
    ModuleId,
    AccountAddress
)

class DecibelAuth:
    """
    Handles Aptos Account signing and Decibel API authentication.
    STRICT PHYSICAL ALIGNMENT v2.0 (Zero-Mock / Robust Serialization)
    """
    def __init__(self, private_key: str, api_key: str = None):
        self.account = Account.load_key(private_key)
        self.api_key = api_key 

    def get_auth_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def sign_transaction(self, raw_transaction: RawTransaction) -> SignedTransaction:
        signature = self.account.sign(raw_transaction.keyed())
        return SignedTransaction(raw_transaction, signature)

    def build_decibel_payload(self, market_id: str, side: str, size: int, price: int):
        """
        Builds the specific Move EntryFunction payload for Decibel.
        Using direct byte serialization to bypass SDK bugs.
        """
        DAO_TREASURY = "0x000000000000000000000000b704a40cb6557ec1352a05bc5990a77b85ae3d67"
        
        module_id = ModuleId(AccountAddress.from_str("0x1"), "trading")
        
        # Manually encoded arguments for Move function
        # [market_id, side, size, price, referrer]
        # In aptos-sdk, EntryFunction expects a list of bytes if not using TransactionArgument wrapper correctly.
        # But let's try the simplest possible list of bytes for arguments.
        
        # Physical encoding of arguments
        import struct
        args = [
            market_id.encode(),
            struct.pack("<B", 1 if side.lower() == "buy" else 2),
            struct.pack("<Q", size),
            struct.pack("<Q", price),
            AccountAddress.from_str(DAO_TREASURY).address
        ]
        
        payload = EntryFunction(
            module_id,
            "place_order",
            [],
            args
        )
        return TransactionPayload(payload)
