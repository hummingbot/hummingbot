import json
import hmac
import string
import uuid
import hashlib

from typing import Dict, Union, Tuple, Any
from urllib.parse import urlencode

from eth_account import Account
from eth_account.messages import encode_defunct, SignableMessage
from eth_account.signers.local import LocalAccount
from eth_typing import HexStr
from web3 import Web3


class IdexAuth:

    HEX_DIGITS_SET = set(string.hexdigits)

    def __init__(self, api_key: str, secret_key: str, wallet_private_key: str = None):
        self._api_key = api_key
        self._secret_key = secret_key
        self._wallet_private_key = wallet_private_key

        self._nonce: Union[uuid.UUID, None] = uuid.uuid1()
        self._wallet: Union[LocalAccount, None] = None

        self.init_wallet(wallet_private_key)

    @staticmethod
    def encode(s: str) -> bytes:
        return s.encode('latin-1')

    @staticmethod
    def decode(b: bytes) -> str:
        return b.decode('latin-1')

    def hmac_sign(self, data: Union[str, bytes]) -> str:
        """generate hmac signature"""
        return hmac.new(
            self._secret_key.encode("utf-8") if isinstance(self._secret_key, str) else self._secret_key,
            data.encode("utf-8") if isinstance(data, str) else data,  # todo alf: check this is correct. Field Order ?
            hashlib.sha256
        ).hexdigest()

    def generate_nonce(self) -> str:
        """re-create uuid1 and return it as a string. Example return: cf7989e0-2030-11eb-8473-f1ca5eaaaff1"""
        self._nonce = uuid.uuid1()
        return str(self._nonce)

    def get_nonce_int(self) -> int:
        """return currently stored uuid1 as an integer"""
        return self._nonce.int

    def get_nonce_str(self) -> str:
        """return currently stored uuid1 as a string. Example return: cf7989e0-2030-11eb-8473-f1ca5eaaaff1"""
        return str(self._nonce)

    def init_wallet(self, private_key: str = None):
        if private_key:
            self._wallet_private_key = private_key
        if self._wallet_private_key:
            self._wallet = Account.from_key(private_key)

    def wallet_sign(self, signature_parameters: Tuple[Tuple[str, Any], ...]) -> str:
        """
        Returns the solidityKeccak signature (ETH Wallet) for the given signature_parameters.

        Example usage:
            idex_auth = IdexAuth(f'{api_key}', f'{api_secret}', f'{wallet_private_key}')
            idex_auth.generate_nonce()
            signature_parameters = (
                ("uint128", idex_auth.get_nonce_as_int()),
                ("address", idex_auth.get_wallet_address()),
            )
            wallet_signature = idex_auth.wallet_sign(signature_parameters)
        """
        fields, values = zip(*signature_parameters)
        signature_parameters_hash: bytes = Web3.solidityKeccak(fields, values)
        signable_message: SignableMessage = encode_defunct(hexstr=signature_parameters_hash.hex())
        signed_message = self._wallet.sign_message(signable_message)  # what type ?
        wallet_signature: str = signed_message.signature.hex()
        return wallet_signature

    @property
    def wallet(self):
        return self._wallet

    def get_wallet_object(self) -> LocalAccount:
        return self._wallet

    def get_wallet_address(self) -> HexStr:
        """public address of the wallet"""
        return self._wallet.address

    def new_wallet_object(self, private_key: str = None) -> LocalAccount:
        private_key = private_key or self._wallet_private_key
        return Account.from_key(private_key)

    def get_wallet_bytes(self, private_key: str = None) -> str:
        raise PendingDeprecationWarning
        # private_key = private_key or self.wallet_private_key
        # return IdexAuth.remove0x_prefix(Account.from_key(private_key).address)

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
                "nonce": self.get_nonce_str()
            })

        params = urlencode(params)  # todo alf: order of param fields for signature ?
        url = f"{url}?{params}"
        return {
            "headers": {
                "IDEX-API-Key": self._api_key,
                "IDEX-HMAC-Signature": self.hmac_sign(params)
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
                "nonce": self.get_nonce_str()
            })

        if wallet_signature:
            body["signature"] = wallet_signature

        body = json.dumps(body, separators=(',', ':'))  # todo alf: 1. sort_keys=True ?   2. why explicit separators ?

        return {
            "headers": {
                "IDEX-API-Key": self._api_key,
                "IDEX-HMAC-Signature": self.hmac_sign(body)
            },
            "body": body,
            "url": url
        }

    generate_auth_dict_for_delete = generate_auth_dict_for_post

    # ----------------------------- Deprecated methods -----------------------------

    @classmethod
    def wallet_signature(cls, *parameters: Tuple[str, Any], private_key: str = None):
        raise PendingDeprecationWarning
        # fields = [item[0] for item in parameters]
        # values = [item[1] for item in parameters]
        # signature_parameters_hash = Web3.solidityKeccak(fields, values)
        # signed_message = cls.new_wallet_object(private_key=private_key).sign_message(
        #     signable_message=encode_defunct(hexstr=signature_parameters_hash.hex())
        # )
        # return signed_message.signature.hex()

    @staticmethod
    def remove0x_prefix(value):
        raise PendingDeprecationWarning
        # if value[:2] == '0x':
        #     return value[2:]
        # return value

    @staticmethod
    def decimal_to_bytes(n, endian='big'):
        """int.from_bytes and int.to_bytes don't work in python2"""
        raise PendingDeprecationWarning
        # if n > 0:
        #     next_byte = IdexAuth.decimal_to_bytes(n // 0x100, endian)
        #     remainder = bytes([n % 0x100])
        #     return next_byte + remainder if endian == 'big' else remainder + next_byte
        # else:
        #     return b''

    @staticmethod
    def base16_to_binary(s):
        raise PendingDeprecationWarning
        # return base64.b16decode(s, True)

    @staticmethod
    def number_to_be(n, size):
        raise PendingDeprecationWarning
        # return IdexAuth.decimal_to_bytes(int(n), 'big').rjust(size, b'\x00')

    @staticmethod
    def binary_concat(*args):
        raise PendingDeprecationWarning
        # result = bytes()
        # for arg in args:
        #     result = result + arg
        # return result

    @staticmethod
    def binary_to_base64(s):
        raise PendingDeprecationWarning
        # return IdexAuth.decode(base64.standard_b64encode(s))

    @staticmethod
    def binary_to_base16(s):
        raise PendingDeprecationWarning
        # return IdexAuth.decode(base64.b16encode(s)).lower()

    @staticmethod
    def hash(request, algorithm='md5', digest='hex'):
        raise PendingDeprecationWarning
        # if algorithm == 'keccak':
        #     binary = bytes(Web3.sha3(request))
        # else:
        #     h = hashlib.new(algorithm, request)
        #     binary = h.digest()
        # if digest == 'base64':
        #     return IdexAuth.binary_to_base64(binary)
        # elif digest == 'hex':
        #     return IdexAuth.binary_to_base16(binary)
        # return binary

    @staticmethod
    def binary_concat_array(array):
        raise PendingDeprecationWarning
        # result = bytes()
        # for element in array:
        #     result = result + element
        # return result

    @staticmethod
    def number_to_le(n, size):
        raise PendingDeprecationWarning
        # return IdexAuth.decimal_to_bytes(int(n), 'little').ljust(size, b'\x00')

    def hash_message(self, message):
        raise PendingDeprecationWarning
        # message_bytes = base64.b16decode(IdexAuth.encode(IdexAuth.remove0x_prefix(message)), True)
        # hash_bytes = Web3.sha3(
        #     b"\x19Ethereum Signed Message:\n" + IdexAuth.encode(str(len(message_bytes))) + message_bytes
        # )
        # return '0x' + IdexAuth.decode(base64.b16encode(hash_bytes)).lower()

    def sign_message_string(self, message, privateKey):
        raise PendingDeprecationWarning
        # signed_message = Account.sign_message(encode_defunct(hexstr=message), private_key=privateKey)
        # return signed_message.signature.hex()

    @classmethod
    def hex_to_uint128(cls, value):
        raise PendingDeprecationWarning
        # # Deal with leading 0x
        # value = value.split("x", 1)[-1]
        # # Filter none hexl
        # value = f"0x{''.join([c for c in value if c in cls.HEX_DIGITS_SET])}"
        # return int(value, 16)
