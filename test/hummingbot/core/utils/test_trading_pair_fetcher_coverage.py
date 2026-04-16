"""Coverage tests for hummingbot/core/utils/trading_pair_fetcher.py
Missing lines: 61 (continue on ModuleNotFoundError), 71 (exception handler in call_fetch_pairs).
"""

from unittest.mock import MagicMock, patch

import pytest

from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher


@pytest.mark.asyncio
async def test_call_fetch_pairs_logs_error_on_exception():
    """Line 71: exception handler assigns empty list and logs error when fetch_fn raises."""
    fetcher = TradingPairFetcher.__new__(TradingPairFetcher)
    fetcher.trading_pairs = {}
    fetcher.ready = False

    mock_logger = MagicMock()
    fetcher._logger = mock_logger

    async def failing_fetch():
        raise RuntimeError("connection refused")

    with patch.object(TradingPairFetcher, "logger", return_value=mock_logger):
        await fetcher.call_fetch_pairs(failing_fetch(), "test_exchange")

    assert fetcher.trading_pairs["test_exchange"] == []
    mock_logger.error.assert_called_once()
    assert "test_exchange" in mock_logger.error.call_args[0][0]
