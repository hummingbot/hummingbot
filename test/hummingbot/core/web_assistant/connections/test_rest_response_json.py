"""Tests for RESTResponse.json() handling of non-JSON content types (Issue #7929)."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from hummingbot.core.web_assistant.connections.data_types import RESTResponse


class TestRESTResponseJson(unittest.TestCase):
    """Tests for RESTResponse.json() handling of non-JSON content types."""

    def _make_mock_response(self, content_type, body, json_side_effect=None):
        mock_resp = MagicMock()
        type(mock_resp).content_type = PropertyMock(return_value=content_type)
        type(mock_resp).status = PropertyMock(return_value=200)
        type(mock_resp).url = PropertyMock(return_value='http://example.com/test')
        type(mock_resp).method = PropertyMock(return_value='GET')
        type(mock_resp).headers = PropertyMock(return_value={})
        mock_resp.read = AsyncMock(return_value=body)
        if json_side_effect is not None:
            mock_resp.json = AsyncMock(side_effect=json_side_effect)
        else:
            try:
                parsed = json.loads(body)
                mock_resp.json = AsyncMock(return_value=parsed)
            except (json.JSONDecodeError, TypeError):
                mock_resp.json = AsyncMock(side_effect=Exception('ContentTypeError'))
        return mock_resp

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_text_plain_non_json_returns_raw_string(self):
        """text/plain 'pong' should return the raw string, not crash."""
        mock_resp = self._make_mock_response('text/plain', b'pong')
        rest_response = RESTResponse(mock_resp)
        result = self._run(rest_response.json())
        self.assertEqual(result, 'pong')

    def test_text_plain_valid_json_returns_parsed(self):
        """text/plain with valid JSON body should return parsed dict."""
        mock_resp = self._make_mock_response('text/plain', b'{"status": "ok"}')
        rest_response = RESTResponse(mock_resp)
        result = self._run(rest_response.json())
        self.assertEqual(result, {'status': 'ok'})

    def test_text_html_non_json_returns_raw_string(self):
        """text/html with non-JSON body should return the raw string."""
        mock_resp = self._make_mock_response('text/html', b'<html>error</html>')
        rest_response = RESTResponse(mock_resp)
        result = self._run(rest_response.json())
        self.assertEqual(result, '<html>error</html>')

    def test_application_json_valid(self):
        """application/json with valid JSON should return parsed dict."""
        mock_resp = self._make_mock_response('application/json', b'{"data": 42}')
        rest_response = RESTResponse(mock_resp)
        result = self._run(rest_response.json())
        self.assertEqual(result, {'data': 42})

    def test_application_json_invalid_falls_back_to_text(self):
        """application/json that fails to parse should fall back to raw text."""
        mock_resp = self._make_mock_response(
            'application/json', b'not-json-at-all',
            json_side_effect=Exception('ContentTypeError')
        )
        rest_response = RESTResponse(mock_resp)
        result = self._run(rest_response.json())
        self.assertEqual(result, 'not-json-at-all')

    def test_unknown_content_type_with_json_body(self):
        """Unknown content type but valid JSON body should parse via fallback."""
        mock_resp = self._make_mock_response(
            'application/octet-stream', b'{"key": "value"}',
            json_side_effect=Exception('ContentTypeError')
        )
        rest_response = RESTResponse(mock_resp)
        result = self._run(rest_response.json())
        self.assertEqual(result, {'key': 'value'})


if __name__ == '__main__':
    unittest.main()
