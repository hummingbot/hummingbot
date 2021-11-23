import hashlib
import hmac
import json
import time

from decimal import Decimal
from typing import Dict, Any, Optional

from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS


class BybitPerpetualAuth():
    """
    Auth class required by Bybit Perpetual API
    """

    def __init__(self, api_key: str, secret_key: str):
        self._api_key: str = api_key
        self._secret_key: str = secret_key

    def get_timestamp(self):
        return str(int(time.time() * 1e3))

    def get_expiration_timestamp(self):
        return str(int((round(time.time()) + 5) * 1e3))

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        """
        Generates a dictionary with all required information for the authentication process
        :return: a dictionary of authentication info including the request signature
        """
        expires = self.get_expiration_timestamp()
        raw_signature = 'GET/realtime' + expires
        signature = hmac.new(self._secret_key.encode('utf-8'), raw_signature.encode('utf-8'), hashlib.sha256).hexdigest()
        auth_info = [self._api_key, expires, signature]

        return auth_info

    def get_headers(self, referer_header_required: Optional[bool] = False) -> Dict[str, Any]:
        """
        Generates authentication headers required by ProBit
        :return: a dictionary of auth headers
        """
        result = {
            "Content-Type": "application/json"
        }
        if referer_header_required:
            result.update({
                "Referer": CONSTANTS.HBOT_BROKER_ID
            })
        return result

    def extend_params_with_authentication_info(self, params: Dict[str, Any]):
        params["timestamp"] = self.get_timestamp()
        params["api_key"] = self._api_key
        key_value_elements = []
        for key, value in sorted(params.items()):
            converted_value = float(value) if type(value) is Decimal else value
            converted_value = converted_value if type(value) is str else json.dumps(converted_value)
            key_value_elements.append(str(key) + "=" + converted_value)
        raw_signature = '&'.join(key_value_elements)
        signature = hmac.new(self._secret_key.encode('utf-8'), raw_signature.encode('utf-8'), hashlib.sha256).hexdigest()
        params["sign"] = signature
        return params
