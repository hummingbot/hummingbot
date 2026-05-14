from test.hummingbot.connector.derivative.pacifica_perpetual.test_pacifica_perpetual_derivative import (
    PacificaPerpetualDerivativeUnitTest,
)
from unittest.mock import AsyncMock


class PacificaPerpetualAPIConfigKeyTest(PacificaPerpetualDerivativeUnitTest):
    def setUp(self):
        super().setUp()

    async def test_fetch_or_create_api_config_key_uses_existing_key_from_config(self):
        mock_rest_assistant = AsyncMock()
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)

        self.exchange.api_config_key = "existing_key"

        await self.exchange._fetch_or_create_api_config_key()

        self.assertEqual(self.exchange.api_config_key, "existing_key")
        mock_rest_assistant.execute_request.assert_not_called()

    async def test_fetch_or_create_api_config_key_fetches_existing_key_from_exchange(self):
        mock_rest_assistant = AsyncMock()
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)

        self.exchange.api_config_key = ""

        mock_rest_assistant.execute_request.return_value = {
            "success": True,
            "data": {"active_api_keys": ["fetched_key"]}
        }

        await self.exchange._fetch_or_create_api_config_key()

        self.assertEqual(self.exchange.api_config_key, "fetched_key")
        mock_rest_assistant.execute_request.assert_awaited()

    async def test_fetch_or_create_api_config_key_creates_new_key_when_none_exist(self):
        mock_rest_assistant = AsyncMock()
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)

        self.exchange.api_config_key = ""

        # First call (list keys) returns empty list
        # Second call (create key) returns new key
        mock_rest_assistant.execute_request.side_effect = [
            {"success": True, "data": {"active_api_keys": []}},
            {"success": True, "data": {"api_key": "created_key"}}
        ]

        await self.exchange._fetch_or_create_api_config_key()

        self.assertEqual(self.exchange.api_config_key, "created_key")
        self.assertEqual(mock_rest_assistant.execute_request.call_count, 2)

    async def test_api_request_injects_header_when_key_present(self):
        mock_rest_assistant = AsyncMock()
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)

        self.exchange.api_config_key = "test_key"
        mock_rest_assistant.execute_request.return_value = {"success": True}

        await self.exchange._api_request(path_url="/test")

        call_args = mock_rest_assistant.execute_request.call_args
        self.assertIsNotNone(call_args)
        kwargs = call_args.kwargs
        self.assertIn("headers", kwargs)
        self.assertIn("PF-API-KEY", kwargs["headers"])
        self.assertEqual(kwargs["headers"]["PF-API-KEY"], "test_key")

    async def test_api_request_does_not_inject_header_when_key_absent(self):
        mock_rest_assistant = AsyncMock()
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)

        self.exchange.api_config_key = ""
        mock_rest_assistant.execute_request.return_value = {"success": True}

        await self.exchange._api_request(path_url="/test")

        call_args = mock_rest_assistant.execute_request.call_args
        self.assertIsNotNone(call_args)
        kwargs = call_args.kwargs
        self.assertIn("headers", kwargs)
        if kwargs["headers"] is not None:
            self.assertNotIn("PF-API-KEY", kwargs["headers"])
