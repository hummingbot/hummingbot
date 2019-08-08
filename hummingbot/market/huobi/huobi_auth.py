import time
import hmac
import hashlib
import base64
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urlencode


class HuobiAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_dict(self, method: str, main_url: str, path_url: str, args: Optional[Dict[str, any]]) -> Dict[str, any]:
        date_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        request = {
            "AccessId": self.api_key,
            "SignatureMethod": "HmacSHA256",
            "SignatureVersion": 2,
            "Timestamp": date_time
        }
        if args is not None:
            request.update(args)
        message = method.upper() + "\n" + main_url + "\n" + path_url + "\n" + \
            urlencode(request)
        hmac_key = base64.urlsafe_b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode('utf8'), hashlib.sha256)
        signature_b64 = base64.b64encode(bytes(signature.digest())).decode('utf8')
        request.update({"Signature": signature_b64})
        print(request)
        return request
