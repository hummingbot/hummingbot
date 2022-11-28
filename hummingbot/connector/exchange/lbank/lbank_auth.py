import hashlib
import hmac
import json
import random
import string
import time
from base64 import b64encode
from dataclasses import replace
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class LbankAuth(AuthBase):

    RSA_KEY_TEXT = "-----{} RSA PRIVATE KEY-----"
    RSA_HEADER = RSA_KEY_TEXT.format("BEGIN")
    RSA_FOOTER = RSA_KEY_TEXT.format("END")
    RSA_KEY_FORMAT = RSA_HEADER + "\n{}\n" + RSA_FOOTER

    def __init__(self, api_key: str, secret_key: str, auth_method: Optional[str] = "RSA") -> None:
        self.api_key: str = api_key
        self.secret_key: str = self.RSA_KEY_FORMAT.format(secret_key) if auth_method == "RSA" else secret_key
        self.auth_method: str = auth_method

    def _time(self) -> int:
        return int(round(time.time() * 1e3))

    def _generate_rand_str(self) -> str:
        return "".join(random.sample(string.ascii_letters + string.digits, 35))

    def _generate_auth_signature(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Helper function that includes the timestamp and generates the appropriate authentication signature for the
        request.
        """

        payload: str = hashlib.md5(urlencode(dict(sorted(data.items()))).encode("utf-8")).hexdigest().upper()
        if self.auth_method == "RSA":
            key = RSA.importKey(self.secret_key)
            signer = PKCS1_v1_5.new(key)
            digest = SHA256.new()
            digest.update(payload.encode("utf-8"))
            return b64encode(signer.sign(digest)).decode("utf-8")
        elif self.auth_method == "HmacSHA256":
            secret_bytes = bytes(self.secret_key, encoding="utf-8")
            payload_bytes = bytes(payload, encoding="utf-8")
            return hmac.new(secret_bytes, payload_bytes, digestmod=hashlib.sha256).hexdigest().lower()

        return None

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameters into the request header.

        :param request: the request to be configured for authenticated interaction
        """
        additional_params = {
            "api_key": self.api_key,
            "echostr": self._generate_rand_str(),
            "signature_method": self.auth_method,
            "timestamp": str(self._time())
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        headers.update(
            {
                "echostr": additional_params["echostr"],
                "signature_method": additional_params["signature_method"],
                "timestamp": additional_params["timestamp"],
            }
        )

        data = {}
        if request.data is not None:
            data.update(json.loads(request.data))
        data.update(additional_params)

        signature: Optional[str] = self._generate_auth_signature(data)

        if signature is None:
            raise ValueError("Error occurred generating signature. "
                             f"Request: {request} "
                             f"API Key: {self.api_key} ")

        data.update({"sign": signature})

        del data["signature_method"]
        del data["timestamp"]
        del data["echostr"]

        request = replace(request, data=data)
        request = replace(request, headers=headers)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to generate the appropriate websocket auth payload.
        """
        return request  # pass-through
