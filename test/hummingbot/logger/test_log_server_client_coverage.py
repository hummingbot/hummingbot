import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger.log_server_client import LogServerClient


@pytest.fixture()
def client():
    LogServerClient._lsc_shared_instance = None
    c = LogServerClient(log_server_url="http://test-log-server/")
    yield c
    # clean up any running tasks
    if c.consume_queue_task is not None:
        c.consume_queue_task.cancel()
    LogServerClient._lsc_shared_instance = None


# ---------------------------------------------------------------------------
# send_log — line 45: successful response path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_log_success(client):
    """Line 45: send_log reads response text and logs on success (status 200)."""
    mock_resp = AsyncMock()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_resp.status = 200
    mock_resp.url = "http://test-log-server/"
    mock_resp.text = AsyncMock(return_value="OK")

    mock_session = MagicMock()
    mock_session.request = MagicMock(return_value=mock_resp)

    request_dict = {
        "method": "POST",
        "url": "http://test-log-server/",
        "request_obj": {"json": {"msg": "hello"}},
    }

    await client.send_log(mock_session, request_dict)
    mock_session.request.assert_called_once_with("POST", "http://test-log-server/", json={"msg": "hello"})


@pytest.mark.asyncio
async def test_send_log_raises_on_bad_status(client):
    """send_log raises EnvironmentError for a non-200, non-skip status."""
    mock_resp = AsyncMock()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_resp.status = 500
    mock_resp.url = "http://test-log-server/"
    mock_resp.text = AsyncMock(return_value="Server Error")

    mock_session = MagicMock()
    mock_session.request = MagicMock(return_value=mock_resp)

    request_dict = {
        "method": "POST",
        "url": "http://test-log-server/",
        "request_obj": {},
    }

    with pytest.raises(EnvironmentError):
        await client.send_log(mock_session, request_dict)


# ---------------------------------------------------------------------------
# request_loop — line 68: session context manager entered; line 75: exception path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_loop_session_created_then_cancelled(client):
    """Line 68: request_loop creates aiohttp.ClientSession and calls consume_queue.
    We cancel immediately after one iteration to avoid an infinite loop."""
    call_order = []

    async def fake_consume_queue(session):
        call_order.append("consume_queue_called")
        # raise CancelledError to exit gracefully
        raise asyncio.CancelledError

    with (
        patch.object(client, "consume_queue", side_effect=fake_consume_queue),
        patch("hummingbot.logger.log_server_client.aiohttp.ClientSession") as mock_session_cls,
        patch("hummingbot.logger.log_server_client.aiohttp.TCPConnector"),
    ):
        mock_session_instance = AsyncMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session_instance

        with pytest.raises(asyncio.CancelledError):
            await client.request_loop()

    assert "consume_queue_called" in call_order


@pytest.mark.asyncio
async def test_request_loop_logs_on_unexpected_exception(client):
    """Line 75: when consume_queue raises a non-CancelledError exception,
    request_loop logs the error then sleeps before looping."""
    iterations = []

    async def fake_consume_queue(session):
        iterations.append(len(iterations))
        if len(iterations) == 1:
            raise RuntimeError("unexpected!")
        # second iteration: cancel so test terminates
        raise asyncio.CancelledError

    with (
        patch.object(client, "consume_queue", side_effect=fake_consume_queue),
        patch("hummingbot.logger.log_server_client.aiohttp.ClientSession") as mock_session_cls,
        patch("hummingbot.logger.log_server_client.aiohttp.TCPConnector"),
        patch("hummingbot.logger.log_server_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_session_instance = AsyncMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session_instance

        with pytest.raises(asyncio.CancelledError):
            await client.request_loop()

    # sleep must have been called after the RuntimeError
    mock_sleep.assert_called_once_with(5.0)
    assert len(iterations) == 2


# ---------------------------------------------------------------------------
# check_network — line 91: CONNECTED / NOT_CONNECTED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_network_connected(client):
    """check_network returns CONNECTED when server responds 200."""
    mock_resp = AsyncMock()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_resp.status = 200

    mock_get = MagicMock(return_value=mock_resp)
    mock_session = MagicMock()
    mock_session.get = mock_get
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("hummingbot.logger.log_server_client.aiohttp.ClientSession", return_value=mock_session),
        patch("hummingbot.logger.log_server_client.aiohttp.TCPConnector"),
    ):
        status = await client.check_network()

    assert status == NetworkStatus.CONNECTED


@pytest.mark.asyncio
async def test_check_network_not_connected_on_non_200(client):
    """check_network returns NOT_CONNECTED when server returns non-200."""
    mock_resp = AsyncMock()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_resp.status = 503

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("hummingbot.logger.log_server_client.aiohttp.ClientSession", return_value=mock_session),
        patch("hummingbot.logger.log_server_client.aiohttp.TCPConnector"),
    ):
        status = await client.check_network()

    assert status == NetworkStatus.NOT_CONNECTED


@pytest.mark.asyncio
async def test_check_network_not_connected_on_exception(client):
    """check_network returns NOT_CONNECTED when a connection exception is raised."""
    with (
        patch("hummingbot.logger.log_server_client.aiohttp.ClientSession", side_effect=OSError("no route")),
        patch("hummingbot.logger.log_server_client.aiohttp.TCPConnector"),
    ):
        status = await client.check_network()

    assert status == NetworkStatus.NOT_CONNECTED
