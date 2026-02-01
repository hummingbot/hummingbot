import json
from typing import Any, Dict

from eth_account import Account
from eth_account.messages import encode_typed_data
from hummingbot.connector.exchange.evedex import evedex_constants as CONSTANTS


class EvedexAuth:
    def __init__(self, private_key: str):
        self._account = Account.from_key(private_key)

    def sign_request(self, method: str, endpoint: str, params: Dict[str, Any]) -> str:
        """
        Signs a request using EIP-712 structured data.
        """
        typed_data = self._construct_eip712_message(method, endpoint, params)
        encoded = encode_typed_data(full_message=typed_data)
        signature = self._account.sign_message(encoded)
        return signature.signature.hex()

    def _construct_eip712_message(self, method: str, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Constructs the EIP-712 message for EVEDEX authentication.
        """
        # Ensure params are sorted keys for consistent stringification if needed,
        # but EVEDEX might treat 'params' as a JSON string field in the struct.
        params_str = json.dumps(params, sort_keys=True)

        return {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "Request": [
                    {"name": "method", "type": "string"},
                    {"name": "endpoint", "type": "string"},
                    {"name": "params", "type": "string"},
                ],
            },
            "primaryType": "Request",
            "domain": {
                "name": "Evedex Exchange",
                "version": "1",
                "chainId": CONSTANTS.CHAIN_ID,
                "verifyingContract": "0x0000000000000000000000000000000000000000",
            },
            "message": {
                "method": method,
                "endpoint": endpoint,
                "params": params_str,
            },
        }

    def get_public_key(self) -> str:
        return self._account.address

    def get_headers(self) -> Dict[str, str]:
        # Typically headers might include the address, but signature is often passed in payload or specific header.
        # This will depend on implementation details, usually it's used to sign the payload.
        # For HTTP calls, we might need to return a signed payload or headers.
        # Assuming for now we just need the address accessible.
        return {}
