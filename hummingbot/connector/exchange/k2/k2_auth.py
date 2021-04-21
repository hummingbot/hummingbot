#!/usr/vin/env python
import rsa
import time

import hummingbot.connector.exchange.k2.k2_constants as CONSTANTS

from typing import Dict, Any

SECRET_BEGIN_SUBSTRING = '-----BEGIN RSA PRIVATE KEY-----\n'
SECRET_KEY_END_SUBSTRING = '\n-----END RSA PRIVATE KEY-----'


class K2Auth():
    """
    Auth class required by K2 API
    """

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        # TODO: Determine if there is a way to include both PKCS1 and PKCS8 keys
        self.secret_key = rsa.PrivateKey.load_pkcs1(f"{SECRET_BEGIN_SUBSTRING+secret_key+SECRET_KEY_END_SUBSTRING}")

    def generate_auth_dict(
        self,
        path_url: str,
    ):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """

        nonce = str(int(time.time() * 1e3))
        auth_payload = path_url + nonce
        signature = rsa.sign(auth_payload.encode(), self.secret_key, "SHA-256").hex()

        headers = self.get_headers()
        headers["APIKey"] = self.api_key
        headers["APINonce"] = nonce
        headers["APISignature"] = signature
        headers["APIAuthPayload"] = auth_payload

        return headers

    async def get_ws_auth_payload(self) -> Dict[str, Any]:
        auth_dict = self.generate_auth_dict(path_url=CONSTANTS.WSS_LOGIN)
        payload: Dict[str, Any] = {
            "name": CONSTANTS.WSS_LOGIN,
            "data": {
                "apikey": auth_dict["APIKey"],
                "apisignature": auth_dict["APISignature"],
                "apiauthpayload": auth_dict["APIAuthPayload"]
            },
            "apinonce": auth_dict["APINonce"]
        }
        return payload

    def get_headers(self) -> Dict[str, Any]:
        """
        Generates authentication headers required by K2
        :return: a dictionary of auth headers
        """

        return {
            "Content-Type": 'application/x-www-form-urlencoded',
        }
