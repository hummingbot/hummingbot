import hmac
import hashlib
import base64
from datetime import datetime
from typing import Dict
from urllib.parse import urlencode


class HuobiAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_dict(self, method: str, main_url: str, path_url: str, args: Dict[str, any] = None) -> Dict[str, any]:
        date_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        request = {
            "AccessKeyId": self.api_key,
            "SignatureMethod": "HmacSHA256",
            "SignatureVersion": "2",
            "Timestamp": date_time
        }
        if args is not None:
            request.update(args)
        message = method.upper() + "\n" + "api.huobi.pro" + "\n" + path_url + "\n" + \
            urlencode(request)
        signature = hmac.new(self.secret_key.encode(), message.encode('utf8'), hashlib.sha256).digest()
        signature_b64 = base64.b64encode(signature).decode('utf8')
        request.update({"Signature": signature_b64})
        return request
