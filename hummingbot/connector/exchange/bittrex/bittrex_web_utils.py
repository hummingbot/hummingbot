from hummingbot.connector.exchange.bittrex import bittrex_constants as CONSTANTS


def public_rest_url(path_url: str, domain = None) -> str:
    return CONSTANTS.BITTREX_REST_URL + path_url


def private_rest_url(path_url: str, domain: str = None) -> str:
    return public_rest_url(path_url)
