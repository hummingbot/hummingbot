import asyncio
import json
import logging
from http.cookies import SimpleCookie
from typing import Any, Dict, Mapping, Optional

import aiohttp

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest

logger = logging.getLogger(__name__)


class GrvtPerpetualAuth(AuthBase):
    """
    Auth class required by GRVT Perpetual API.

    GRVT uses API key authentication via session cookies.
    Authentication flow:
    1. POST to /auth/api_key/login with {"api_key": "<your_key>"}
    2. Receive a session cookie (gravity=<token>) and X-Grvt-Account-Id header
    3. Use cookie and header in all authenticated requests

    Order signing uses EIP-712 typed-data with an Ethereum private key via
    grvt_perpetual_order_sign_utils.build_order_signature.
    Login is performed lazily on the first authenticated request.
    """

    def __init__(
        self,
        api_key: str,
        sub_account_id: str,
        time_provider: TimeSynchronizer,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key: str = api_key
        self._sub_account_id: str = sub_account_id
        self._time_provider: TimeSynchronizer = time_provider
        self._domain: str = domain
        self._session_cookie: Optional[str] = None
        self._account_id: Optional[str] = None
        self._login_lock: asyncio.Lock = asyncio.Lock()
        self._authenticated: bool = False

    @property
    def sub_account_id(self) -> str:
        return self._sub_account_id

    @property
    def session_cookie(self) -> Optional[str]:
        return self._session_cookie

    @property
    def account_id(self) -> Optional[str]:
        return self._account_id

    def set_session_cookie(self, cookie: str):
        self._session_cookie = cookie

    def set_account_id(self, account_id: str):
        self._account_id = account_id

    async def ensure_authenticated(self):
        if self._authenticated:
            return
        if self._session_cookie is not None:
            # Support pre-seeded session in tests or restored sessions.
            self._authenticated = True
            return
        await self._login()

    async def _login(self):
        """
        Performs the API key login to obtain session cookie and account ID.
        Called lazily on the first authenticated request.
        """
        if self._authenticated:
            return

        async with self._login_lock:
            if self._authenticated:
                return
            try:
                auth_url = web_utils.auth_url(self._domain)
                payload = json.dumps({
                    "api_key": self._api_key,
                })
                headers = {
                    "Content-Type": "application/json",
                    "accept": "application/json",
                    "Cookie": "rm=true;",
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(auth_url, data=payload, headers=headers) as response:
                        if response.status >= 400:
                            response_text = await response.text()
                            raise IOError(
                                f"Failed to authenticate with GRVT API ({response.status}): {response_text}"
                            )

                        try:
                            response_json = await response.json()
                        except Exception:
                            response_json = {}

                        self._session_cookie = self._extract_session_cookie(
                            set_cookie_header=response.headers.get("Set-Cookie", ""),
                            response_json=response_json,
                        )

                        # Extract account id from response headers or body
                        account_id = response.headers.get("X-Grvt-Account-Id", "")
                        if not account_id:
                            account_id = response_json.get(
                                "account_id", response_json.get("x_grvt_account_id", "")
                            )
                        if account_id:
                            self._account_id = account_id

                        if self._session_cookie is None:
                            raise IOError(
                                "GRVT authentication succeeded but no session cookie was returned."
                            )

                        self._authenticated = True
                        logger.info("Successfully authenticated with GRVT API")
            except Exception as e:
                logger.error(f"Error authenticating with GRVT: {e}")
                raise

    @staticmethod
    def _extract_session_cookie(
        set_cookie_header: str, response_json: Mapping[str, Any]
    ) -> Optional[str]:
        if set_cookie_header:
            parsed_cookie = SimpleCookie()
            parsed_cookie.load(set_cookie_header)
            if "gravity" in parsed_cookie:
                return f"gravity={parsed_cookie['gravity'].value}"
            return set_cookie_header.split(";", maxsplit=1)[0]

        cookie_from_json = response_json.get("cookie")
        if isinstance(cookie_from_json, str) and cookie_from_json:
            return cookie_from_json.split(";", maxsplit=1)[0]

        return None

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds authentication headers and cookies to REST requests.
        Performs login on first call if not yet authenticated.
        """
        await self.ensure_authenticated()

        headers = dict(request.headers) if request.headers else {}
        headers["Content-Type"] = "application/json"

        if self._session_cookie:
            headers["Cookie"] = self._session_cookie
        if self._account_id:
            headers["X-Grvt-Account-Id"] = self._account_id
        headers["X-Grvt-Subaccount-Id"] = self._sub_account_id

        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Adds authentication to WebSocket requests via headers.
        """
        await self.ensure_authenticated()
        return request

    def header_for_authentication(self) -> Dict[str, str]:
        """
        Returns headers needed for authenticated requests.
        """
        headers = {
            "Content-Type": "application/json",
        }
        if self._session_cookie:
            headers["Cookie"] = self._session_cookie
        if self._account_id:
            headers["X-Grvt-Account-Id"] = self._account_id
        headers["X-Grvt-Subaccount-Id"] = self._sub_account_id
        return headers

    def ws_headers_for_authentication(self) -> Dict[str, str]:
        """
        Returns headers needed for authenticated WebSocket connections.
        """
        headers = {}
        if self._session_cookie:
            headers["Cookie"] = self._session_cookie
        if self._account_id:
            headers["X-Grvt-Account-Id"] = self._account_id
        headers["X-Grvt-Subaccount-Id"] = self._sub_account_id
        return headers

    def get_auth_login_body(self) -> str:
        """
        Returns the JSON body for the authentication login request.
        """
        return json.dumps({"api_key": self._api_key})
