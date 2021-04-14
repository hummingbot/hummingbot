import base64
import json
import time
import hashlib
import hmac
from typing import (
    Any,
    Dict
)
from collections import OrderedDict


class KucoinAuth:
    def __init__(self, api_key: str, passphrase: str, secret_key: str):
        self.api_key: str = api_key
        self.passphrase: str = passphrase
        self.secret_key: str = secret_key
        self.partner_id: str = "Hummingbot"
        self.partner_key: str = "8fb50686-81a8-408a-901c-07c5ac5bd758"

    @staticmethod
    def keysort(dictionary: Dict[str, str]) -> Dict[str, str]:
        return OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))

    def third_party_header(self, timestamp: str):
        partner_payload = timestamp + self.partner_id + self.api_key
        partner_signature = base64.b64encode(hmac.new(self.partner_key.encode("utf-8"), partner_payload.encode("utf-8"), hashlib.sha256).digest())
        third_party = {
            "KC-API-PARTNER": self.partner_id,
            "KC-API-PARTNER-SIGN": str(partner_signature, "utf-8")
        }
        return third_party

    def add_auth_to_params(self,
                           method: str,
                           path_url: str,
                           args: Dict[str, Any] = None,
                           partner_header: bool = False) -> Dict[str, Any]:
        timestamp = int(time.time() * 1000)
        request = {
            "KC-API-KEY": self.api_key,
            "KC-API-TIMESTAMP": str(timestamp),
            "Content-Type": "application/json",
            "KC-API-KEY-VERSION": "2"
        }
        if args is not None:
            query_string = json.dumps(args)
            payload = str(timestamp) + method.upper() + path_url + query_string
        else:
            payload = str(timestamp) + method.upper() + path_url
        signature = base64.b64encode(
            hmac.new(self.secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest())
        passphrase = base64.b64encode(
            hmac.new(self.secret_key.encode('utf-8'), self.passphrase.encode('utf-8'), hashlib.sha256).digest())
        request["KC-API-SIGN"] = str(signature, "utf-8")
        request["KC-API-PASSPHRASE"] = str(passphrase, "utf-8")
        if partner_header:
            headers = self.third_party_header(str(timestamp))
            request.update(headers)
        return request
