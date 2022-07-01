from test.hummingbot.connector.exchange.alpha_point.alpha_point_exchange_connector_test import AlphaPointExchangeTests
from unittest.mock import MagicMock, patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.eve.eve_exchange import EveExchange
from hummingbot.connector.exchange.eve.eve_web_utils import EveURLCreator


class EveExchangeTests(AlphaPointExchangeTests.ExchangeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._url_creator = EveURLCreator(
            rest_base_url="https://some.url",
            ws_base_url="ws://some.url",
        )

    @property
    def url_creator(self):
        return self._url_creator

    @patch("hummingbot.core.utils.tracking_nonce.NonceCreator._time")
    def create_exchange_instance(self, time_mock: MagicMock, authenticated: bool = True) -> EveExchange:
        time_mock.return_value = self.time_mock
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = EveExchange(
            client_config_map=client_config_map,
            eve_api_key=self.api_key,
            eve_secret_key=self.secret,
            eve_user_id=self.user_id,
            trading_pairs=[self.trading_pair],
            url_creator=self.url_creator,
        )
        if authenticated:
            self._initialize_auth(exchange.authenticator)
        return exchange
