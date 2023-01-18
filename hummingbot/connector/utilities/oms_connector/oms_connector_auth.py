import hashlib
import hmac
import json
from typing import Dict

from hummingbot.connector.utilities.oms_connector import oms_connector_constants as CONSTANTS
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSJSONRequest


class OMSConnectorAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, user_id: int):
        self.api_key = api_key
        self.secret_key = secret_key
        self.user_id = user_id
        self.user_name = None
        self.account_id = None
        self._auth_dict = None
        self._initialized = False
        self._build_auth_dict()

    @property
    def initialized(self) -> bool:
        return self._initialized

    def get_rest_auth_headers(self) -> Dict[str, str]:
        return self._auth_dict

    def validate_rest_auth(self, auth_resp_data: Dict[str, str]) -> bool:
        return self._validate_auth(auth_resp_data)

    def update_with_rest_response(self, auth_resp_data: Dict[str, str]):
        self._update_with_auth_response(auth_resp_data)

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = request.headers or {}
        headers.update(self._auth_dict)
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSJSONRequest) -> WSJSONRequest:
        data = request.payload[CONSTANTS.MSG_DATA_FIELD]
        data_dict = json.loads(data)
        data_dict.update(self._auth_dict)
        request.payload[CONSTANTS.MSG_DATA_FIELD] = json.dumps(data_dict)
        return request

    def _build_auth_dict(self):
        nonce_creator = NonceCreator.for_milliseconds()
        nonce = str(nonce_creator.get_tracking_nonce())
        signature = self._generate_signature(nonce)
        self._auth_dict = {
            CONSTANTS.API_KEY_FIELD: self.api_key,
            CONSTANTS.SIGNATURE_FIELD: signature,
            CONSTANTS.USER_ID_FIELD: str(self.user_id),
            CONSTANTS.NONCE_FIELD: nonce,
        }

    def _generate_signature(self, nonce: str) -> str:
        auth_concat = f"{nonce}{self.user_id}{self.api_key}"
        signature = hmac.new(
            key=self.secret_key.encode("utf-8"),
            msg=auth_concat.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return signature

    @staticmethod
    def _validate_auth(data: Dict[str, str]) -> bool:
        return data.get(CONSTANTS.AUTHENTICATED_FIELD) or False

    def _update_with_auth_response(self, data: Dict[str, str]):
        user_data = data[CONSTANTS.USER_FIELD]
        self.user_name = user_data[CONSTANTS.USER_NAME_FIELD]
        self.account_id = user_data[CONSTANTS.ACCOUNT_ID_FIELD]
        self._initialized = True
