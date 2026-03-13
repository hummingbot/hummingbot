import json
import time

import base58
from solders.keypair import Keypair

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class PacificaPerpetualAuth(AuthBase):
    def __init__(self, agent_wallet_public_key: str, agent_wallet_private_key: str, user_wallet_public_key: str):
        # aka "agent_wallet"; we pass it in POST requests
        self.agent_wallet_public_key = agent_wallet_public_key
        # used to generate signature for POST requests
        self.agent_wallet_private_key = agent_wallet_private_key

        # aka "account"; we pass it to some GET requests and to all POST requests
        self.user_wallet_public_key = user_wallet_public_key

        self._keypair = None

    @property
    def keypair(self):
        if self._keypair is None:
            self._keypair = Keypair.from_bytes(base58.b58decode(self.agent_wallet_private_key))
        return self._keypair

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.method == RESTMethod.POST:
            request_data = json.loads(request.data)

            operation_type: str = request_data.pop("type")

            signature_header = {
                "timestamp": int(time.time() * 1000),
                "expiry_window": 5000,
                "type": operation_type,
            }

            _, signature_b58 = sign_message(signature_header, request_data, self.keypair)

            final_body = {
                "account": self.user_wallet_public_key,
                "agent_wallet": self.agent_wallet_public_key,
                "signature": signature_b58,
                "timestamp": signature_header["timestamp"],
                "expiry_window": signature_header["expiry_window"],
                **request_data
            }

            request.data = json.dumps(final_body)
            request.headers = {"Content-Type": "application/json"}

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        params = request.payload.get("params", {})

        if params is None:
            return request

        operation_type: str = params.pop("type")

        signature_header = {
            "timestamp": int(time.time() * 1000),
            "expiry_window": 5000,
            "type": operation_type,
        }

        _, signature_b58 = sign_message(signature_header, params, self.keypair)

        final_body = {
            "account": self.agent_wallet_public_key,
            "agent_wallet": self.agent_wallet_public_key,
            "signature": signature_b58,
            "timestamp": signature_header["timestamp"],
            "expiry_window": signature_header["expiry_window"],
            **params
        }

        request.payload["params"] = final_body

        return request

# the following 3 functions have been extracted from the official SDK
# https://github.com/pacifica-fi/python-sdk


def sign_message(header, payload, keypair):
    message = prepare_message(header, payload)
    message_bytes = message.encode("utf-8")
    signature = keypair.sign_message(message_bytes)
    return (message, base58.b58encode(bytes(signature)).decode("ascii"))


def sort_json_keys(value):
    if isinstance(value, dict):
        sorted_dict = {}
        for key in sorted(value.keys()):
            sorted_dict[key] = sort_json_keys(value[key])
        return sorted_dict
    elif isinstance(value, list):
        return [sort_json_keys(item) for item in value]
    else:
        return value


def prepare_message(header, payload):
    if (
        "type" not in header
        or "timestamp" not in header
        or "expiry_window" not in header
    ):
        raise ValueError("Header must have type, timestamp, and expiry_window")

    data = {
        **header,
        "data": payload,
    }

    message = sort_json_keys(data)

    # Specifying the separaters is important because the JSON message is expected to be compact.
    message = json.dumps(message, separators=(",", ":"))

    return message
