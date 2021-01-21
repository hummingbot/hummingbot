#!/usr/vin/env python
import rsa
import time

from typing import Dict, Any


class K2Auth():
    """
    Auth class required by K2 API
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        # TODO: Determine if there is a way to include both PKCS1 and PKCS8 keys
        self.secret_key = rsa.PrivateKey.load_pkcs1(secret_key)

    def generate_auth_dict(
        self,
        path_url: str,
    ):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """

        nonce = int(time.time() * 1e3)
        auth_payload = path_url + str(nonce)
        signature = rsa.sign(auth_payload.encode(), self.secret_key, "SHA-256").hex()

        headers = self.get_headers()
        headers["APIKey"] = self.api_key
        headers["APINonce"] = nonce
        headers["APISignature"] = signature
        headers["APIAuthPayload"] = auth_payload

        return headers

    def get_headers(self) -> Dict[str, Any]:
        """
        Generates authentication headers required by K2
        :return: a dictionary of auth headers
        """

        return {
            "Content-Type": 'application/x-www-form-urlencoded',
        }
