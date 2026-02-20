from typing import Dict, Optional

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants import (
    EXCHANGE_NAME,
)


class DecibelPerpetualAuth:
    """
    Auth class for Decibel Perpetual API
    Decibel uses Bearer token authentication.
    """

    def __init__(self, bearer_token: str, origin: str = "https://app.decibel.trade"):
        self._bearer_token = bearer_token
        self._origin = origin

    @property
    def auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._bearer_token}",
            "Origin": self._origin,
        }

    @property
    def api_key(self) -> str:
        return self._bearer_token

    def get_headers(self) -> Dict[str, str]:
        """
        Returns the common headers for authenticated requests
        """
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._bearer_token}",
            "Origin": self._origin,
        }

    def get_account_id(self) -> str:
        """
        Returns the account ID from the bearer token
        Note: This is a placeholder - actual implementation may need to decode/extract from token
        """
        return "main"

    def get_subaccount_id(self) -> Optional[str]:
        """
        Returns the subaccount ID if configured
        """
        return None
