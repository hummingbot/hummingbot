import json
import hmac
import string
import uuid
import hashlib

from typing import Dict, Union, Tuple, Any
from urllib.parse import urlencode

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_account.signers.local import LocalAccount
from web3 import Web3

from hummingbot.connector.exchange.idex.conf import settings


class IdexAuth:

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def sign(self, data: Union[str, bytes]) -> str:
        return hmac.new(
            self.secret_key.encode("utf-8") if isinstance(self.secret_key, str) else self.secret_key,
            data.encode("utf-8") if isinstance(data, str) else data,
            hashlib.sha256
        ).hexdigest()

    HEX_DIGITS_SET = set(string.hexdigits)

    @classmethod
    def hex_to_uint128(cls, value):
        # Deal with leading 0x
        value = value.split("x", 1)[-1]
        # Filter none hex
        value = f"0x{''.join([c for c in value if c in cls.HEX_DIGITS_SET])}"
        return int(value, 16)

    @classmethod
    def get_wallet(cls, private_key: str = None) -> LocalAccount:
        private_key = private_key or settings.eth_account_private_key
        return Account.from_key(private_key)

    @classmethod
    def wallet_signature(cls, *parameters: Tuple[str, Any], private_key: str = None):
        fields = [item[0] for item in parameters]
        values = [item[1] for item in parameters]

        signature_parameters_hash = Web3.solidityKeccak(fields, values)
        signed_message = cls.get_wallet(private_key=private_key).sign_message(
            signable_message=encode_defunct(hexstr=signature_parameters_hash.hex())
        )

        return signed_message.signature.hex()

    @staticmethod
    def generate_nonce():
        return str(uuid.uuid1())

    def generate_auth_dict(
            self,
            http_method: str,
            url: str,
            params: Dict[str, any] = None,
            body: Dict[str, any] = None,
            wallet_signature: str = None) -> Dict[str, any]:
        http_method = http_method.strip().lower()
        params = params or {}
        body = body or {}
        return getattr(self, f"generate_auth_dict_for_{http_method}")(url, params, body, wallet_signature)

    def generate_auth_dict_for_get(
            self,
            url: str,
            params: Dict[str, any],
            body: Dict[str, any] = None,
            wallet_signature: str = None) -> Dict[str, any]:

        if "nonce" not in params:
            params.update({
                "nonce": self.generate_nonce()
            })

        params = urlencode(params)
        url = f"{url}?{params}"
        return {
            "headers": {
                "IDEX-API-Key": self.api_key,
                "IDEX-HMAC-Signature": self.sign(params)
            },
            "url": url
        }

    def generate_auth_dict_for_post(
            self,
            url: str,
            params: Dict[str, any],
            body: Dict[str, any],
            wallet_signature: str = None) -> Dict[str, any]:
        body = body or {}
        parameters = body.get("parameters")
        if isinstance(parameters, dict) and "nonce" not in parameters:
            body["parameters"].update({
                "nonce": self.generate_nonce()
            })

        if wallet_signature:
            body["signature"] = wallet_signature

        body = json.dumps(body, separators=(',', ':'))

        return {
            "headers": {
                "IDEX-API-Key": self.api_key,
                "IDEX-HMAC-Signature": self.sign(body)
            },
            "body": body,
            "url": url
        }

    generate_auth_dict_for_delete = generate_auth_dict_for_post
