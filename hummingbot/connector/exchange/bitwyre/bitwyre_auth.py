import hashlib
import hmac

from typing import Dict

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.utils.tracking_nonce import NonceCreator

class BitwyreAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = {}

        if request.headers is not None:
            headers.update(request.headers)

        headers.update(self._get_rest_headers(request))
        request.headers = headers

        return request

    def _get_rest_headers(self, request: RESTRequest) -> Dict[str, str]:
        sign = self._generate_sign(request)
        api_key = self.api_key

        headers = {
            "API-Key": api_key,
            "API-Sign": sign,
            "Content-type": "application/json",
        }

        return headers
    
    def _generate_sign(api_secret: str, uri_path: str, checksum: str) -> str:
        nonce = NonceCreator.for_microseconds()

        nonce_checksum = nonce + checksum
        sha256_hash = hashlib.sha256(nonce_checksum.encode('utf-8')).hexdigest()
        message = uri_path + sha256_hash
        api_sign = hmac.new(
            api_secret.encode('utf-8'), 
            message.encode('utf-8'), 
            hashlib.sha512
        ).hexdigest()

        return api_sign
