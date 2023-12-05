import base64
import time
from decimal import Decimal
from typing import Any, Dict, List

from vega.auth import Signer
from vega.client import Client

from hummingbot.connector.derivative.vega_perpetual import (
    vega_perpetual_constants as CONSTANTS,
    vega_perpetual_web_utils as web_utils,
)
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class VegaPerpetualAuth(AuthBase):
    """
    Auth class required by Vega Perpetual API
    """

    def __init__(self, public_key: str, mnemonic: str, domain: str = CONSTANTS.DOMAIN):
        self._public_key = public_key
        self._mnemonic = mnemonic
        self.domain = domain
        self.is_valid = self.confirm_pub_key_matches_generated()
        self._best_grpc_url = ""

    async def grpc_base(self) -> None:
        endpoints = CONSTANTS.PERPETUAL_GRPC_ENDPOINTS
        if self.domain == CONSTANTS.TESTNET_DOMAIN:
            endpoints = CONSTANTS.TESTNET_GRPC_ENDPOINTS
        results: List[Dict[str, str]] = []
        for url in endpoints:
            try:
                _start_time = time.time_ns()
                mnemonic_length = len(self._mnemonic.split())
                if self._mnemonic is not None and mnemonic_length > 0:
                    # NOTE: This trys to connect, if not it cycles through the endpoints
                    self._client: Client = Client(
                        mnemonic=self._mnemonic,
                        grpc_url=web_utils.grpc_url(self.domain),
                        # NOTE: This is for vega vs metamask snap
                        derivations=(0 if mnemonic_length == 12 else 1)
                    )
                _end_time = time.time_ns()
                _request_latency = _end_time - _start_time
                # Check to ensure we have a match
                _time_ms = Decimal(_request_latency)
                results.append({"connection": url, "latency": _time_ms})
            except Exception:
                pass

        if len(results) > 0:
            # Sort the results
            sorted_result = sorted(results, key=lambda x: x['latency'])
            # Return the connection endpoint with the best response time
            self._best_grpc_url = sorted_result[0]["connection"]

    def confirm_pub_key_matches_generated(self) -> bool:
        mnemonic_length = len(self._mnemonic.split())
        if self._mnemonic is not None and mnemonic_length > 0:
            derivations = (0 if mnemonic_length == 12 else 1)
            try:
                signer = Signer.from_mnemonic(mnemonic=self._mnemonic, derivations=derivations)
                if signer._pub_key == self._public_key:
                    return True
            except Exception:
                return False
        return False

    async def sign_payload(self, payload: Dict[str, Any], method: str) -> str:
        if self._best_grpc_url == "":
            await self.grpc_base()
        mnemonic_length = len(self._mnemonic.split())
        if self._mnemonic is not None and mnemonic_length > 0:
            # NOTE: This trys to connect, if not it cycles through the endpoints
            self._client: Client = Client(
                mnemonic=self._mnemonic,
                grpc_url=self._best_grpc_url,
                # NOTE: This is for vega vs metamask snap
                derivations=(0 if mnemonic_length == 12 else 1)
            )
        # NOTE: https://docs.vega.xyz/mainnet/api/grpc/vega/commands/v1/transaction.proto
        signed_transaction = self._client.sign_transaction(payload, method)

        serialized = signed_transaction.SerializeToString()
        encoded = base64.b64encode(serialized)

        return encoded

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        return request  # pass-through

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through
