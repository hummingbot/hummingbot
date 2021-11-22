import asyncio
import hmac
import hashlib
import json
from typing import Dict, Any
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce


class SouthXchangeAuth():
    """
    Auth class required by SouthXchange API
    Learn more at https://main.southxchange.com/Content/swagger/ui/?urls.primaryName=API%20v4#/
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self._shared_client = None
        self._lock = asyncio.Lock()

    def get_auth_headers(self,
                         path_url: str = "",
                         data: Dict[str, Any] = {}):
        """
        Modify - SouthXchange
        """
        data['nonce'] = get_tracking_nonce()
        data['key'] = self.api_key
        userSignature = hmac.new(
            self.secret_key.encode('utf-8'),
            json.dumps(data).encode('utf8'),
            hashlib.sha512
        ).hexdigest()
        header = {'Hash': userSignature, 'Content-Type': 'application/json'}
        return {
            "header": header,
            "data": data,
        }

    def get_api_key(self) -> str:
        return self.api_key

    def get_headers(self) -> Dict[str, Any]:
        """
        Generates generic headers required by SouthXchange
        :return: a dictionary of headers
        """
        return {
            'Content-Type': 'application/json',
        }
