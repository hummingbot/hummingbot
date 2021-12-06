import hmac
import hashlib
from typing import Dict, Any
from hummingbot.connector.exchange.wazirx import wazirx_utils


class WazirxAuth():

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def get_auth(self, params):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """
        query_string = ""
        for key in params:
            query_string = query_string + f"{key}={params[key]}&"

        params['recvWindow'] = 50000
        params['timestamp'] = wazirx_utils.get_ms_timestamp()

        query_string = query_string + f"recvWindow={params['recvWindow']}&timestamp={params['timestamp']}"

        signature = hmac.new(
            self.secret_key.encode('ascii'),
            query_string.encode('ascii'),
            hashlib.sha256
        ).hexdigest()

        params['signature'] = signature
        return params

    def get_headers(self) -> Dict[str, Any]:
        """
        Generates authentication headers required by wazirx.com
        :return: a dictionary of auth headers
        """

        return {
            "Content-Type": 'application/x-www-form-urlencoded',
            "X-Api-Key": self.api_key,
        }
