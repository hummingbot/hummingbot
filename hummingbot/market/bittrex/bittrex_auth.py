import time
import hmac
import hashlib
import urllib
from typing import Dict, Any, Tuple

import ujson


class BittrexAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_dict(
        self,
        http_method: str,
        url: str,
        params: Dict[str, Any] = None,
        body: Dict[str, Any] = None,
        subaccount_id: str = "",
    ) -> Dict[str, any]:
        """
        Generates the url and the valid signature to authenticate with the API endpoint.
        :param http_method: String representing the HTTP method in use ['GET', 'POST', 'DELETE'].
        :param url: String representing the API endpoint.
        :param params: Dictionary of url parameters to be included in the api request. USED ONLY IN SOME CASES
        :param body: Dictionary representing the values in a request body.
        :param subaccount_id: String value of subaccount id.
        :return: Dictionary containing the final 'params' and its corresponding 'signature'.
        """

        # Appends params the url
        def append_params_to_url(url: str, params: Dict[str, any] = {}) -> str:
            if params:
                param_str = urllib.parse.urlencode(params)
                return f"{url}?{param_str}"
            return url

        def construct_content_hash(body: Dict[str, any] = {}) -> Tuple[str, bytes]:
            json_byte: bytes = "".encode()
            if body:
                json_byte = ujson.dumps(body).encode()
                return hashlib.sha512(json_byte).hexdigest(), json_byte
            return hashlib.sha512(json_byte).hexdigest(), json_byte

        timestamp = str(int(time.time() * 1000))
        url = append_params_to_url(url, params)
        content_hash, content_bytes = construct_content_hash(body)
        content_to_sign = "".join([timestamp, url, http_method, content_hash, subaccount_id])
        signature = hmac.new(self.secret_key.encode(), content_to_sign.encode(), hashlib.sha512).hexdigest()

        # V3 Authentication headers
        headers = {
            "Api-Key": self.api_key,
            "Api-Timestamp": timestamp,
            "Api-Content-Hash": content_hash,
            "Api-Signature": signature,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if subaccount_id:
            headers.update({"Api-Subaccount-Id": subaccount_id})

        return {"headers": headers, "body": content_bytes, "url": url}
