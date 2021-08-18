import hashlib
import hmac
import time
from typing import Dict, Any


class BybitPerpetualAuth():
    """
    Auth class required by Bybit API
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

    def generate_auth_dict(self) -> Dict[str, Any]:
        """
        Generates a dictionary with all required information for the authentication process
        :return: a dictionary of authentication info including the request signature
        """
        expires = str(int(round(time.time()) + 1)) + "000"
        raw_signature = 'GET/realtime' + expires
        signature = str(hmac.new(self._secret_key.encode('utf-8'), raw_signature.encode('utf-8'), hashlib.sha256).hexdigest())

        auth_info = {'op': 'auth',
                     'args': [self.api_key, expires, signature]}

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
