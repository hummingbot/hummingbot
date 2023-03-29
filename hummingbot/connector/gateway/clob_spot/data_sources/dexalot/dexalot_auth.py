from abc import ABC, abstractmethod
from typing import Optional

from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class SignerBase(ABC):
    @abstractmethod
    async def sign_message(self, message: str) -> str:
        ...


class WalletSigner(SignerBase):
    def __init__(
        self,
        chain: str,
        network: str,
        address: str,
        gateway_instance: GatewayHttpClient,
    ):
        self._chain = chain
        self._network = network
        self._address = address
        self._gateway_instance = gateway_instance

    async def sign_message(self, message: str) -> str:
        resp = await self._gateway_instance.wallet_sign(
            chain=self._chain,
            network=self._network,
            address=self._address,
            message=message,
        )
        return resp["signature"]


class DexalotAuth(AuthBase):
    def __init__(self, signer: SignerBase, address: str):
        self._signer = signer
        self._signature: Optional[str] = None
        self._address = address

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        signature = await self._get_signature()
        request.headers = request.headers or {}
        request.headers["x-signature"] = f"{self._address}:{signature}"
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        raise NotImplementedError  # currently unused

    async def _get_signature(self) -> str:
        if self._signature is None:
            self._signature = await self._signer.sign_message("dexalot")
        return self._signature
