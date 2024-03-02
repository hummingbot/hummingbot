import hashlib
import hmac
import logging
from typing import Dict

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSJSONRequest, WSRequest
from hummingbot.logger import HummingbotLogger

from .coinbase_advanced_trade_web_utils import endpoint_from_url


class CoinbaseAdvancedTradeAuth(AuthBase):
    """
    Authentication class for Coinbase Advanced Trade API.

    Uses HMAC SHA256 to authenticate REST and websocket requests.

    Coinbase API documentation: https://docs.cloud.coinbase.com/sign-in-with-coinbase/docs/api-key-authentication
    """
    TIME_SYNC_UPDATE_S: float = 30
    _time_sync_last_updated_s: float = -1

    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    __slots__ = (
        'api_key',
        'secret_key',
        'time_provider',
    )

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        """
        :param api_key: The API key.
        :param secret_key: The API secret key.
        :param time_provider: The time provider object.
        """
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self.time_provider: TimeSynchronizer = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.

        All REST requests must contain the following headers:

        CB-ACCESS-KEY API key as a string
        CB-ACCESS-SIGN Message signature (see below)
        CB-ACCESS-TIMESTAMP Timestamp for your request
        All request bodies should have content type application/json and be valid JSON.

        Example request:

        curl https://api.coinbase.com/v2/user \
          --header "CB-ACCESS-KEY: <your api key>" \
          --header "CB-ACCESS-SIGN: <the user generated message signature>" \
          --header "CB-ACCESS-TIMESTAMP: <a timestamp for your request>"

        :param request: the request to be configured for authenticated interaction
        :returns: the authenticated request
        """
        timestamp: str = str(int(self.time_provider.time()))

        endpoint: str = endpoint_from_url(request.url).split('?')[0]  # ex: /v3/orders
        message = timestamp + str(request.method) + endpoint + str(request.data or '')
        signature: str = self._generate_signature(message=message)

        headers: Dict = dict(request.headers or {}) | {
            "accept": 'application/json',
            "content-type": 'application/json',
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
        }
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSJSONRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated.
        :param request: the request to be configured for authenticated interaction
        https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-overview
        {
            "type": "subscribe",
            "product_ids": [
                "ETH-USD",
                "ETH-EUR"
            ],
            "channel": "level2",
            "api_key": "exampleApiKey123",
            "timestamp": 1660838876,
            "signature": "00000000000000000000000000",
        }
        To subscribe to any channel, users must provide a channel name, api_key, timestamp, and signature:
            channel name as a string. You can only subscribe to one channel at a time.
            timestamp should be a string in UNIX format. Example: "1677527973".
            signature should be created by:
        Concatenating and comma-separating the timestamp, channel name, and product Ids, for example: 1660838876level2ETH-USD,ETH-EUR.
        Signing the above message with the passphrase and base64-encoding the signature.
        """
        timestamp: str = str(int(self.time_provider.time()))

        products: str = ",".join(request.payload["product_ids"])
        message: str = timestamp + str(request.payload["channel"]) + products
        signature: str = self._generate_signature(message=message)

        payload: Dict = dict(request.payload or {}) | {
            "api_key": self.api_key,
            "signature": signature,
            "timestamp": timestamp,
        }
        request.payload = payload
        self.logger().debug(f"ws_authenticate payload: {payload}")

        return request

    def _generate_signature(self, *, message: str) -> str:
        """
        Generates an HMAC SHA256 signature from a message and the API secret key.

        :param message: the message to sign
        :returns: the signature
        """
        digest: str = hmac.new(self.secret_key.encode("utf8"), message.encode("utf8"), hashlib.sha256).digest().hex()
        return digest
