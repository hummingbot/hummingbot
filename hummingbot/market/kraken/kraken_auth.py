import base64
from datetime import datetime
import hashlib
import hmac
import time
from typing import (
    Any,
    Dict
)
from urllib.parse import urlencode
from collections import OrderedDict
import urllib

from future.moves import collections

KRAKEN_HOST_NAME = "https://api.kraken.com/0/private/"


class KrakenAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key: str = api_key
        self.secret_key: str = secret_key

    @staticmethod
    def keysort(dictionary: Dict[str, str]) -> Dict[str, str]:
        return OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))

    def binary_concat(self,*args):
        result = bytes()
        for arg in args:
            result = result + arg
        return result

    def extend(self,*args):

        if args is not None:
            result = None
            if type(args[0]) is collections.OrderedDict:

                result = collections.OrderedDict()
            else:
                result = {}
            for arg in args:
                result.update(arg)
            return result
        return {}

    def add_auth_to_params(self, path_url: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
        url = KRAKEN_HOST_NAME
        timestamp = str(int(time.time() * 1000))
        if args:
            args.update({'nonce': timestamp})
        else:
            args = {'nonce': timestamp}

        path_url ='/0/' + path_url
        post_data = urllib.parse.urlencode(args)
        
        # Unicode-objects must be encoded before hashing
        encoded = (str(args['nonce']) + post_data).encode()
        message = path_url.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(
            base64.b64decode(self.secret_key),
            message,
            hashlib.sha512
        )
        sig_digest = base64.b64encode(signature.digest())

        headers = {
                'API-KEY': self.api_key,
                'API-Sign': sig_digest.decode(),
            }

        return headers, args