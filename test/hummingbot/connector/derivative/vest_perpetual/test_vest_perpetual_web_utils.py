from hummingbot.connector.derivative.vest_perpetual import vest_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.vest_perpetual import vest_perpetual_web_utils as web_utils


def test_public_rest_url_uses_default_domain():
    url = web_utils.public_rest_url(CONSTANTS.DEPTH_PATH_URL)
    assert url == f"{CONSTANTS.REST_URL_PROD}{CONSTANTS.DEPTH_PATH_URL}"


def test_public_ws_url_includes_account_group_query():
    account_group = 7
    url = web_utils.public_ws_url(account_group=account_group)
    assert url.startswith(CONSTANTS.WSS_URL_PROD)
    assert f"xwebsocketserver=restserver{account_group}" in url


def test_private_ws_url_appends_listen_key():
    url = web_utils.private_ws_url("abc123", account_group=1)
    assert "listenKey=abc123" in url
    assert "websocketserver=restserver1" in url
