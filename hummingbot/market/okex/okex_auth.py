import base64
from datetime import datetime
import hashlib
import hmac
import json
import time
from typing import (
    Any,
    Dict
)
from urllib.parse import urlencode
from collections import OrderedDict


"spot/v3/accounts"


class OKExAuth:
    def __init__(self, api_key: str, secret_key: str, passphrase: str):
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self.passphrase : str = passphrase

    @staticmethod
    def keysort(dictionary: Dict[str, str]) -> Dict[str, str]:
        return OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))

    @staticmethod
    def json(data):
        return json.dumps(data, separators=(',', ':'))

    @staticmethod
    def get_timestamp() -> str:
        miliseconds = int(time.time() * 1000)
        utc = datetime.utcfromtimestamp(miliseconds // 1000)
        return utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-6] + "{:03d}".format(int(miliseconds) % 1000) + 'Z' 

    def get_signature(self, timestamp, method, path_url, body) -> str:
        auth = timestamp + method + path_url
        if body:
            auth += self.json(body)
        signature =  base64.b64encode(hmac.new(self.secret_key.encode(), auth.encode(), hashlib.sha256).digest())
        return signature.decode()

    def add_auth_to_params(self,
                           method: str,
                           path_url: str,
                           args: Dict[str, Any]=None) -> Dict[str, Any]:

        uppercase_method = method.upper()

        timestamp = self.get_timestamp()

        request = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": self.get_signature(timestamp, uppercase_method, path_url, args),
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
        }

        # TODO check if this goes
        # if args is not None:
        #     request.update(args)

        sorted_request = self.keysort(request)
        
        return sorted_request
