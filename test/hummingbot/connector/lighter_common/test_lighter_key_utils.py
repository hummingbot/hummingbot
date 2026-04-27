import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as perp_constants
from hummingbot.connector.exchange.lighter import lighter_constants as spot_constants
from hummingbot.connector.lighter_common.lighter_key_utils import fetch_lighter_public_key


class LighterKeyUtilsTest(TestCase):
    def test_fetch_public_key_uses_spot_testnet_url(self):
        captured_url = []

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"api_keys": []})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        def capture_get(url, **kwargs):
            captured_url.append(url)
            return mock_response

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=capture_get)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            asyncio.run(fetch_lighter_public_key("lighter_testnet", "100", "4"))

        self.assertIn(spot_constants.TESTNET_REST_URL, captured_url[0])

    def test_fetch_public_key_uses_perpetual_testnet_url(self):
        captured_url = []

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"api_keys": []})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        def capture_get(url, **kwargs):
            captured_url.append(url)
            return mock_response

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=capture_get)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            asyncio.run(fetch_lighter_public_key("lighter_perpetual_testnet", "100", "4"))

        self.assertIn(perp_constants.TESTNET_REST_URL, captured_url[0])
