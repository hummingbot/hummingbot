import base64
from typing import Any, Dict

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

    def sign_payload(self, payload: Dict[str, Any], method: str) -> str:
        mnemonic_length = len(self._mnemonic.split())
        if self._mnemonic is not None and mnemonic_length > 0:
            self._client: Client = Client(
                mnemonic=self._mnemonic,
                grpc_url=web_utils.grpc_url(self.domain),
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
