from hummingbot.connector.derivative.vest_perpetual import (
    vest_perpetual_constants as CONSTANTS,
)


def test_default_domain_equals_exchange_name():
    assert CONSTANTS.DEFAULT_DOMAIN == CONSTANTS.EXCHANGE_NAME


def test_rest_and_ws_urls_use_expected_endpoints():
    assert CONSTANTS.REST_URLS[CONSTANTS.DEFAULT_DOMAIN] == CONSTANTS.REST_URL_PROD
    assert CONSTANTS.REST_URLS[CONSTANTS.TESTNET_DOMAIN] == CONSTANTS.REST_URL_DEV
    assert CONSTANTS.WSS_URLS[CONSTANTS.DEFAULT_DOMAIN] == CONSTANTS.WSS_URL_PROD
    assert CONSTANTS.WSS_URLS[CONSTANTS.TESTNET_DOMAIN] == CONSTANTS.WSS_URL_DEV


def test_rate_limits_include_core_private_paths():
    limit_ids = {limit.limit_id for limit in CONSTANTS.RATE_LIMITS}
    required_paths = {
        CONSTANTS.ORDERS_PATH_URL,
        CONSTANTS.ORDERS_CANCEL_PATH_URL,
        CONSTANTS.ACCOUNT_PATH_URL,
        CONSTANTS.LISTEN_KEY_PATH_URL,
    }
    assert required_paths.issubset(limit_ids)
