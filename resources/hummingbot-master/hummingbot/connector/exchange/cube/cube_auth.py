import base64
import hashlib
import hmac
import struct
import time
from typing import Dict, Tuple

from hummingbot.connector.exchange.cube.cube_ws_protobufs import trade_pb2
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class CubeAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request header.
        :param request: the request to be configured for authenticated interaction
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication())
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated.
        functionality
        """

        return request  # pass-through

    def header_for_authentication(self) -> Dict[str, str]:
        # Generate signature
        signature, timestamp = self._generate_signature()

        # Headers for the API request
        headers = {
            'x-api-key': self.api_key,
            'x-api-signature': signature,
            'x-api-timestamp': str(timestamp)
        }

        return headers

    def credential_message_for_authentication(self) -> bytes:
        # Generate signature
        signature, timestamp = self._generate_signature()

        # Credentials for the API request
        message = trade_pb2.Credentials()
        message.access_key_id = self.api_key
        message.signature = signature
        message.timestamp = timestamp

        serialized_message = message.SerializeToString()

        return serialized_message

    def verify_signature(self, signature: str, timestamp: int) -> bool:
        """
        Verifies the signature generation.
        :param signature: the signature to be verified
        :param timestamp: the timestamp of the request
        :return: True if the signature is valid, False otherwise
        """

        # Generate the signature
        generated_signature, _ = self._generate_signature(timestamp)

        # Generate signature with different timestamp
        generated_signature_diff_timestamp, _ = self._generate_signature(timestamp + 1)

        # Compare the generated signatures with the provided signature
        return signature == generated_signature and signature != generated_signature_diff_timestamp

    def _generate_signature(self, timestamp: int = None) -> Tuple[str, int]:
        # Get timestamp
        if timestamp is None:
            input_timestamp = int(time.time())
        else:
            input_timestamp = timestamp

        # Convert the timestamp to an 8-byte little-endian array
        timestamp_bytes = struct.pack('<Q', input_timestamp)

        # The fixed byte string
        fixed_string = b'cube.xyz'

        # Concatenate the fixed string with the timestamp
        payload = fixed_string + timestamp_bytes

        # Build the secret key bytes
        secret_key_bytes = bytes.fromhex(self.secret_key)

        # Create the HMAC-SHA256 signature
        signature = hmac.new(secret_key_bytes, payload, hashlib.sha256).digest()

        # Encode the signature in base64
        signature_b64 = base64.b64encode(signature)

        return signature_b64.decode(), input_timestamp
