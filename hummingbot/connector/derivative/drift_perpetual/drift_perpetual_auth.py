from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class DriftPerpetualAuth(AuthBase):
    """
    Drift's signing keypair lives in the self-hosted Drift Gateway
    (DRIFT_GATEWAY_KEY env, configured by the operator at gateway launch).
    Clients do NOT authenticate to the local gateway — it is the signer.

    This authenticator is therefore an intentional no-op: it satisfies the
    WebAssistantsFactory `AuthBase` contract while adding no headers or
    signatures. The sub-account is selected per-request in the data layer,
    not via auth. (Same delegation-to-gateway model as the dydx_v4 /
    injective_v2 on-chain connectors, which likewise sign outside the
    HTTP auth layer.)
    """

    def __init__(self, sub_account_id: int = 0):
        self._sub_account_id = sub_account_id

    @property
    def sub_account_id(self) -> int:
        return self._sub_account_id

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request
