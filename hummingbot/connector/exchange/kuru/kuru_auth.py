from eth_account import Account

from kuru_sdk_py.configs import WalletConfig


class KuruAuth:
    """
    Wallet-based authentication for Kuru DEX.

    Wraps a private key, derives the wallet address, and provides
    a WalletConfig for the Kuru SDK. Unlike CEX connectors, there
    are no API keys - all auth is done via transaction signing.
    """

    def __init__(self, private_key: str):
        self._private_key = private_key
        self._account = Account.from_key(private_key)
        self._address: str = self._account.address

    @property
    def address(self) -> str:
        return self._address

    @property
    def private_key(self) -> str:
        return self._private_key

    def get_wallet_config(self) -> WalletConfig:
        return WalletConfig(private_key=self._private_key)
