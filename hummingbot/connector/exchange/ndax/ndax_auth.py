import hashlib
import hmac
import threading
import time
from typing import Dict, Optional

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce_low_res
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.connections_factory import ConnectionsFactory
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest

ONE_HOUR = 3600


class NdaxAuth(AuthBase):
    """
    Auth class required by NDAX API
    """

    _instance = None
    _lock = threading.Lock()  # To ensure thread safety during instance creation

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:  # Double-checked locking
                    cls._instance = super(NdaxAuth, cls).__new__(cls)
        return cls._instance

    def __init__(self, uid: str, api_key: str, secret_key: str, account_name: str):
        if not hasattr(self, "_initialized"):  # Prevent reinitialization
            if len(uid) > 0:
                self._uid: str = uid
                self._account_id = 0
                self._api_key: str = api_key
                self._secret_key: str = secret_key
                self._account_name: str = account_name
                self._token: Optional[str] = None
                self._token_expiration: int = 0
                self._initialized = True

    @property
    def token(self) -> str:
        return self._token

    @token.setter
    def token(self, token: str):
        self._token = token

    @property
    def uid(self) -> int:
        return int(self._uid)

    @uid.setter
    def uid(self, uid: str):
        self._uid = uid

    @property
    def account_id(self) -> int:
        return int(self._account_id)

    @property
    def account_name(self) -> str:
        return self._account_name

    def generate_nonce(self):
        return str(get_tracking_nonce_low_res())

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """
        headers = {}
        if self._token is None or time.time() > self._token_expiration:
            rest_connection = await ConnectionsFactory().get_rest_connection()
            request = RESTRequest(
                method=RESTMethod.POST,
                url="https://api.ndax.io:8443/AP/Authenticate",
                endpoint_url="",
                params={},
                data={},
                headers=self.header_for_authentication(),
            )
            authentication_req = await rest_connection.call(request)
            authentication = await authentication_req.json()
            if authentication.get("Authenticated", False) is True:
                self._token = authentication["SessionToken"]
                self._token_expiration = time.time() + ONE_HOUR - 10
                self._uid = authentication["User"]["UserId"]
                self._account_id = int(authentication["User"]["AccountId"])
            else:
                raise Exception("Could not authenticate REST connection with NDAX")

        headers.update({"APToken": self._token, "Content-Type": "application/json"})
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated.
        """
        return request

    def header_for_authentication(self) -> Dict[str, str]:
        """
        Generates authentication headers
        :return: a dictionary of auth headers
        """

        nonce = self.generate_nonce()
        raw_signature = nonce + str(self._uid) + self._api_key

        auth_info = {
            "Nonce": nonce,
            "APIKey": self._api_key,
            "Signature": hmac.new(
                self._secret_key.encode("utf-8"), raw_signature.encode("utf-8"), hashlib.sha256
            ).hexdigest(),
            "UserId": str(self._uid),
        }
        return auth_info
