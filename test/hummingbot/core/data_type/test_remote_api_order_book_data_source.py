#!/usr/bin/env python
"""
Tests for SafeOrderBookUnpickler and RemoteAPIOrderBookDataSource.

This module tests:
- SafeOrderBookUnpickler blocks arbitrary/untrusted classes
- SafeOrderBookUnpickler allows the expected order book types
- get_tracking_pairs() raises pickle.UnpicklingError on a crafted malicious response
"""
import asyncio
import io
import os
import pickle
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.remote_api_order_book_data_source import (
    RemoteAPIOrderBookDataSource,
    SafeOrderBookUnpickler,
)


class TestSafeOrderBookUnpickler(unittest.TestCase):
    """Tests for SafeOrderBookUnpickler."""

    def test_safe_unpickler_blocks_arbitrary_code(self):
        """A payload that uses __reduce__ to call os.system must raise UnpicklingError."""

        class Exploit:
            def __reduce__(self):
                return (os.system, ("echo pwned",))

        malicious = pickle.dumps(Exploit())

        with self.assertRaises(pickle.UnpicklingError):
            SafeOrderBookUnpickler(io.BytesIO(malicious)).load()

    def test_safe_unpickler_allows_expected_types(self):
        """A payload of dict mapping str -> tuple loads without error."""
        valid_data = {"BTC-USDT": (1.0, 2.0), "ETH-USDT": (3.0, 4.0)}
        payload = pickle.dumps(valid_data)

        result = SafeOrderBookUnpickler(io.BytesIO(payload)).load()

        self.assertEqual(result, valid_data)

    def test_get_tracking_pairs_uses_safe_unpickler(self):
        """get_tracking_pairs() must raise UnpicklingError when the response contains
        an unexpected class rather than silently executing it."""

        class Exploit:
            def __reduce__(self):
                return (os.system, ("echo pwned",))

        malicious_payload = pickle.dumps(Exploit())

        # Build a mock response whose .read() coroutine returns the malicious bytes
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=malicious_payload)

        # Build a mock client session whose .get() returns the mock response
        mock_context_manager = MagicMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_context_manager)

        data_source = RemoteAPIOrderBookDataSource()

        async def run():
            with patch.object(data_source, "get_client_session", new=AsyncMock(return_value=mock_session)):
                # get_tracking_pairs calls session.get directly (not as context manager),
                # so patch the response returned by session.get
                mock_session.get = AsyncMock(return_value=mock_response)
                await data_source.get_tracking_pairs()

        with self.assertRaises(pickle.UnpicklingError):
            asyncio.get_event_loop().run_until_complete(run())


if __name__ == "__main__":
    unittest.main()
