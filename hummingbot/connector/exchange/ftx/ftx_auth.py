import time
import hmac
from typing import Dict, Any
from requests import Request


class FtxAuth:
    def __init__(self, api_key: str, secret_key: str, subaccount_name: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.subaccount_name = subaccount_name

    def generate_auth_dict(
        self,
        http_method: str,
        url: str,
        params: Dict[str, Any] = None,
        body: Dict[str, Any] = None
    ) -> Dict[str, any]:

        if http_method == "POST":
            request = Request(http_method, url, json=body)
            prepared = request.prepare()
            ts = int(time.time() * 1000)
            content_to_sign = f'{ts}{prepared.method}{prepared.path_url}'.encode()
            content_to_sign += prepared.body
        else:
            request = Request(http_method, url)
            prepared = request.prepare()
            ts = int(time.time() * 1000)
            content_to_sign = f'{ts}{prepared.method}{prepared.path_url}'.encode()

        signature = hmac.new(self.secret_key.encode(), content_to_sign, 'sha256').hexdigest()

        # V3 Authentication headers
        headers = {
            "FTX-KEY": self.api_key,
            "FTX-SIGN": signature,
            "FTX-TS": str(ts)
        }
        if self.subaccount_name is not None and self.subaccount_name != "":
            headers["FTX-SUBACCOUNT"] = self.subaccount_name

        return headers

    def generate_websocket_subscription(self):
        ts = int(1000 * time.time())
        presign = f"{ts}websocket_login"
        sign = hmac.new(self.secret_key.encode(), presign.encode(), 'sha256').hexdigest()
        subscribe = {
            "args": {
                "key": self.api_key,
                "sign": sign,
                "time": ts,
            },
            "op": "login"
        }
        if self.subaccount_name is not None and self.subaccount_name != "":
            subscribe["args"]["subaccount"] = self.subaccount_name

        return subscribe
