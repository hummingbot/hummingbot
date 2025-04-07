import hashlib
import hmac
from typing import Dict, Any

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce_low_res


class NdaxAuth():
    """
    Auth class required by NDAX API
    """

    def __init__(self, uid: str, api_key: str, secret_key: str, account_name: str):
        self._uid: str = uid
        self._api_key: str = api_key
        self._secret_key: str = secret_key
        self._account_name: str = account_name

    @property
    def uid(self) -> int:
        return int(self._uid)

    @property
    def account_name(self) -> str:
        return self._account_name

    def generate_nonce(self):
        return str(get_tracking_nonce_low_res())

    def generate_auth_dict(self) -> Dict[str, Any]:
        """
        Generates a dictionary with all required information for the authentication process
        :return: a dictionary of authentication info including the request signature
        """
        nonce = self.generate_nonce()
        raw_signature = nonce + self._uid + self._api_key

        auth_info = {'Nonce': nonce,
                     'APIKey': self._api_key,
                     'Signature': hmac.new(self._secret_key.encode('utf-8'),
                                           raw_signature.encode('utf-8'),
                                           hashlib.sha256).hexdigest(),
                     'UserId': self._uid}

        return auth_info

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        """
        Generates and returns a dictionary with the structure of the payload required for authentication
        :return: a dictionary with the required parameters for authentication
        """
        return self.generate_auth_dict()

    def get_headers(self) -> Dict[str, Any]:
        """
        Generates authentication headers required by ProBit
        :return: a dictionary of auth headers
        """

        return {
            "Content-Type": 'application/json',
        }

    def get_auth_headers(self):
        headers = self.get_headers()
        headers.update(self.generate_auth_dict())
        return headers
