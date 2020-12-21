import base64
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


class IdexAuth:

    HEX_DIGITS_SET = set(string.hexdigits)

    def __init__(self, api_key: str, secret_key: str, wallet_private_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.wallet_private_key = wallet_private_key

    @staticmethod
    def remove0x_prefix(value):
        if value[:2] == '0x':
            return value[2:]
        return value

    @staticmethod
    def decimal_to_bytes(n, endian='big'):
        """int.from_bytes and int.to_bytes don't work in python2"""
        if n > 0:
            next_byte = IdexAuth.decimal_to_bytes(n // 0x100, endian)
            remainder = bytes([n % 0x100])
            return next_byte + remainder if endian == 'big' else remainder + next_byte
        else:
            return b''

    @staticmethod
    def encode(string):
        return string.encode('latin-1')

    @staticmethod
    def decode(string):
        return string.decode('latin-1')

    @staticmethod
    def base16_to_binary(s):
        return base64.b16decode(s, True)

    @staticmethod
    def number_to_be(n, size):
        return IdexAuth.decimal_to_bytes(int(n), 'big').rjust(size, b'\x00')

    @staticmethod
    def binary_concat(*args):
        result = bytes()
        for arg in args:
            result = result + arg
        return result

    @staticmethod
    def binary_to_base64(s):
        return IdexAuth.decode(base64.standard_b64encode(s))

    @staticmethod
    def binary_to_base16(s):
        return IdexAuth.decode(base64.b16encode(s)).lower()

    @staticmethod
    def hash(request, algorithm='md5', digest='hex'):
        if algorithm == 'keccak':
            binary = bytes(Web3.sha3(request))
        else:
            h = hashlib.new(algorithm, request)
            binary = h.digest()
        if digest == 'base64':
            return IdexAuth.binary_to_base64(binary)
        elif digest == 'hex':
            return IdexAuth.binary_to_base16(binary)
        return binary

    @staticmethod
    def binary_concat_array(array):
        result = bytes()
        for element in array:
            result = result + element
        return result

    @staticmethod
    def number_to_le(n, size):
        return IdexAuth.decimal_to_bytes(int(n), 'little').ljust(size, b'\x00')

    def hashMessage(self, message):
        message_bytes = base64.b16decode(IdexAuth.encode(IdexAuth.remove0x_prefix(message)), True)
        hash_bytes = Web3.sha3(b"\x19Ethereum Signed Message:\n" + IdexAuth.encode(str(len(message_bytes))) + message_bytes)
        return '0x' + IdexAuth.decode(base64.b16encode(hash_bytes)).lower()

    def sign_message_string(self, message, privateKey):
        signed_message = Account.sign_message(encode_defunct(hexstr=message), private_key=privateKey)
        return signed_message.signature.hex()

    def sign(self, data: Union[str, bytes]) -> str:
        return hmac.new(
            self.secret_key.encode("utf-8") if isinstance(self.secret_key, str) else self.secret_key,
            data.encode("utf-8") if isinstance(data, str) else data,
            hashlib.sha256
        ).hexdigest()

    @classmethod
    def hex_to_uint128(cls, value):
        # Deal with leading 0x
        value = value.split("x", 1)[-1]
        value = f"0x{''.join([c for c in value if c in cls.HEX_DIGITS_SET])}"
        return int(value, 16)

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

    def get_wallet(self, private_key: str = None) -> LocalAccount:
        private_key = private_key or self.wallet_private_key
        return Account.from_key(private_key)

    def get_wallet_bytes(self, private_key: str = None) -> str:
        private_key = private_key or self.wallet_private_key
        return IdexAuth.remove0x_prefix(Account.from_key(private_key).address)

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
