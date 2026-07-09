from typing import Optional

from aptos_sdk.account import Account


class DecibelPerpetualAuth:
    """
    Authentication class for Decibel Perpetual connector.

    Decibel uses delegation pattern:
    - API wallet signs all transactions
    - Main wallet delegates trading permissions to API wallet
    - Main wallet private key is NEVER exposed to the bot

    This class manages the API wallet account for signing and derives
    the subaccount address from the main wallet public key.
    """

    def __init__(self, api_wallet_private_key: str, main_wallet_public_key: str, api_key: str):
        """
        Initialize authentication with API wallet keypair and main wallet public key.

        :param api_wallet_private_key: API wallet private key (hex format, with or without 0x/ed25519-priv- prefix)
        :param main_wallet_public_key: Main wallet public key (for subaccount derivation)
        :param api_key: API key for REST API Bearer token authentication
        """
        self._api_wallet_private_key = api_wallet_private_key
        self._main_wallet_public_key = main_wallet_public_key.replace("0x", "").replace("0X", "")
        self._api_key = api_key
        self._api_wallet_account: Optional[Account] = None
        self._subaccount_addr: Optional[str] = None

    @property
    def account(self) -> Account:
        """
        Get the API wallet account instance (used for signing transactions).
        Lazy initialization to avoid creating account on import.
        Uses Account.load_key() which handles ed25519-priv- prefix automatically.
        """
        if self._api_wallet_account is None:
            # Account.load_key() handles ed25519-priv-0x... format natively
            self._api_wallet_account = Account.load_key(self._api_wallet_private_key)
        return self._api_wallet_account

    @property
    def address(self) -> str:
        """
        Get the API wallet address (0x... format).
        This is the wallet that signs transactions.
        """
        return str(self.account.address())

    @property
    def main_wallet_address(self) -> str:
        """
        Get the main wallet address from public key.
        This is used for subaccount derivation.
        """
        # Main wallet address is the public key with 0x prefix
        return f"0x{self._main_wallet_public_key}"

    def get_subaccount_address(self, package_address: str) -> str:
        """
        Get the subaccount address.
        Decibel supports using the main account address as a subaccount.
        """
        return self.main_wallet_address

    def sign_transaction(self, transaction) -> any:
        """
        Sign a transaction with the API wallet's private key.

        The API wallet has been delegated permission to trade on behalf
        of the main wallet's subaccount.

        :param transaction: The transaction to sign
        :return: The signed transaction authenticator
        """
        return transaction.sign(self.account.private_key)

    async def rest_authenticate(self, request):
        """
        Add Bearer token authentication to REST requests.

        :param request: The request to authenticate
        :return: The request with Authorization header added
        """
        if self._api_key:
            request.headers = request.headers or {}
            request.headers["Authorization"] = f"Bearer {self._api_key}"
        return request
