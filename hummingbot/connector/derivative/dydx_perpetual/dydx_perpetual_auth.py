import json

from dydx3 import Client
from dydx3.helpers.db import get_account_id as dydx3_get_acount_id
from dydx3.helpers.request_helpers import generate_now_iso, generate_query_path, remove_nones
from dydx3.starkex.order import SignableOrder

import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class DydxPerpetualAuth(AuthBase):
    def __init__(
        self,
        dydx_perpetual_api_key: str,
        dydx_perpetual_api_secret: str,
        dydx_perpetual_passphrase: str,
        dydx_perpetual_ethereum_address: str,
        dydx_perpetual_stark_private_key: str,
    ):
        self._dydx_perpetual_api_key = dydx_perpetual_api_key
        self._dydx_perpetual_api_secret = dydx_perpetual_api_secret
        self._dydx_perpetual_passphrase = dydx_perpetual_passphrase
        self._dydx_perpetual_ethereum_address = dydx_perpetual_ethereum_address
        self._dydx_perpetual_stark_private_key = dydx_perpetual_stark_private_key
        self._dydx_stark_private_key = (
            None if dydx_perpetual_stark_private_key == "" else dydx_perpetual_stark_private_key
        )

        self._dydx_client = None

    @property
    def dydx_client(self):
        if self._dydx_client is None:
            api_credentials = {
                "key": self._dydx_perpetual_api_key,
                "secret": self._dydx_perpetual_api_secret,
                "passphrase": self._dydx_perpetual_passphrase,
            }

            self._dydx_client = Client(
                host=CONSTANTS.DYDX_REST_BASE_URL,
                api_key_credentials=api_credentials,
                stark_private_key=self._dydx_stark_private_key,
            )
        return self._dydx_client

    def get_account_id(self):
        return dydx3_get_acount_id(self._dydx_perpetual_ethereum_address)

    def _get_iso_timestamp(self):
        return generate_now_iso()

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        ts = self._get_iso_timestamp()

        endpoint_url = request.url.replace(CONSTANTS.DYDX_REST_BASE_URL, "")
        if request.params is not None:
            request_path = generate_query_path(endpoint_url, request.params)
        else:
            request_path = endpoint_url

        data = request.data if request.data is not None else "{}"

        signature = self.dydx_client.private.sign(
            request_path=request_path,
            method=str(request.method),
            iso_timestamp=ts,
            data=remove_nones(json.loads(data)),
        )

        headers = {
            "DYDX-SIGNATURE": signature,
            "DYDX-API-KEY": self._dydx_perpetual_api_key,
            "DYDX-TIMESTAMP": ts,
            "DYDX-PASSPHRASE": self._dydx_perpetual_passphrase,
        }

        if request.headers is not None:
            headers.update(request.headers)

        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        ts = self._get_iso_timestamp()

        channel = request.payload["channel"]
        request_path = CONSTANTS.WS_CHANNEL_TO_PATH[channel]

        signature = self.dydx_client.private.sign(
            request_path=request_path,
            method="GET",
            iso_timestamp=ts,
            data={},
        )

        request.payload["apiKey"] = self._dydx_perpetual_api_key
        request.payload["passphrase"] = self._dydx_perpetual_passphrase
        request.payload["timestamp"] = ts
        request.payload["signature"] = signature

        return request

    def get_order_signature(
        self,
        position_id: str,
        client_id: str,
        market: str,
        side: str,
        size: str,
        price: str,
        limit_fee: str,
        expiration_epoch_seconds: int,
    ) -> str:
        order_to_sign = SignableOrder(
            network_id=self.dydx_client.network_id,
            position_id=position_id,
            client_id=client_id,
            market=market,
            side=side,
            human_size=size,
            human_price=price,
            limit_fee=limit_fee,
            expiration_epoch_seconds=expiration_epoch_seconds,
        )
        order_signature = order_to_sign.sign(self._dydx_perpetual_stark_private_key)
        return order_signature
