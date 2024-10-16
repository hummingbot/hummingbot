from eth_account import Account
from eth_account.messages import encode_defunct

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class DexalotAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider
        self.wallet = Account.from_key(secret_key)

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """

        message = encode_defunct(text="dexalot")
        signed_message = self.wallet.sign_message(signable_message=message)
        headers = {"x-signature": f"{self.wallet.address}:{signed_message.signature.hex()}"}
        if request.headers is not None:
            headers.update(request.headers)
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Dexalot does not use this
        functionality
        """
        message = encode_defunct(text="dexalot")
        signed_message = self.wallet.sign_message(signable_message=message)
        request.payload["signature"] = f"{self.wallet.address}:{signed_message.signature.hex()}"
        return request
