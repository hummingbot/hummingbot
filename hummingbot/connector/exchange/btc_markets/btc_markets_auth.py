import base64
import hmac
import hashlib
import json
from typing import Dict, Any
# from hummingbot.connector.exchange.btc_markets.btc_markets_utils import get_ms_timestamp


class BtcMarketsAuth:
    """
    Auth class required by btc_markets API
    Learn more at https://api.btcmarkets.net/doc/v3#section/Authentication/Authentication-process
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_dict(
        self,
        method: str,
        path_url: str,
        # body: str,
        nonce: int,
        data: Dict[str, Any] = None
    ):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """

        data = data or {}
        data['method'] = method
        data.update({'method': method.upper(), 'nonce': nonce, 'api_key': self.api_key})
        # commented 02/08
        # data_params = data.get('params', {})
        # if not data_params:
        #   data['params'] = {}
        # comment to here

        # params = ''.join(
        #    f'{key}{data_params[key]}'
        #    for key in sorted(data_params)
        # )
        if "body" in data:
            if len(data['body']) == 0:
                payload = f"{data['method']}/{path_url}{data['nonce']}{''}"
            else:
                bjson = json.dumps(data['body'])
                payload = f"{data['method']}/{path_url}{data['nonce']}{bjson}"
        else:
            payload = f"{data['method']}/{path_url}{data['nonce']}{''}"

        presignature = base64.b64encode(hmac.new(
            base64.b64decode(self.secret_key), payload.encode('utf-8'), digestmod=hashlib.sha512).digest())
        signature = presignature.decode('utf8')

        data['sig'] = signature

        return data

    def generate_auth_dict_ws(self, nonce: int):
        """
        Generates an authentication params for websockets login
        :return: a signature of auth params
        """

        payload = "/users/self/subscribe" + "\n" + str(nonce)
        presignature = base64.b64encode(hmac.new(
            base64.b64decode(self.secret_key), payload.encode('utf-8'), digestmod=hashlib.sha512).digest())
        signature = presignature.decode('utf8')
        return signature

    def generate_auth_headers(self, data: Dict[str, Any] = None):
        """
        Generates HTTP headers
        """
        # nonce = get_ms_timestamp()
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "UTF-8",
            "Content-Type": "application/json",
            "BM-AUTH-APIKEY": self.api_key,
            "BM-AUTH-TIMESTAMP": str(data['nonce']),
            "BM-AUTH-SIGNATURE": data['sig']
            # "BM-AUTH-SIGNATURE": self.secret_key
        }

        return headers
