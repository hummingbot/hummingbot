# XRPL Import
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from xrpl.constants import CryptoAlgorithm
from xrpl.wallet import Wallet

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class XRPLAuth(AuthBase):
    def __init__(self, xrpl_secret_key: str):
        try:
            if len(xrpl_secret_key) == 0:
                self._wallet = Wallet.create()
            else:
                # Check if it's a raw private key (hex format)
                if xrpl_secret_key.startswith(("ED", "00")):
                    # Raw private key
                    private_key = xrpl_secret_key
                    # Convert private key to bytes
                    private_key_bytes = bytes.fromhex(private_key[2:])  # Remove ED/00 prefix
                    # Derive public key using Ed25519
                    private_key_obj = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
                    public_key_bytes = private_key_obj.public_key().public_bytes_raw()
                    public_key = "ED" + public_key_bytes.hex()
                    # Create wallet with derived keys
                    self._wallet = Wallet(public_key=public_key, private_key=private_key)
                elif xrpl_secret_key.startswith("s"):
                    # Seed format
                    self._wallet = Wallet.from_seed(xrpl_secret_key, algorithm=self.get_algorithm(key=xrpl_secret_key))
                else:
                    raise ValueError("Invalid XRPL secret key format. Must be either a seed (starting with 's'), or a raw private key (starting with 'ED' or '00')")
        except Exception as e:
            raise ValueError(f"Invalid XRPL secret key: {e}")

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    def get_wallet(self) -> Wallet:
        return self._wallet

    def get_account(self) -> str:
        return self._wallet.classic_address

    def get_algorithm(self, key: str) -> CryptoAlgorithm:
        if key.startswith("sEd"):
            return CryptoAlgorithm.ED25519
        elif key.startswith("s"):
            return CryptoAlgorithm.SECP256K1
        else:
            raise ValueError("Invalid key format")
