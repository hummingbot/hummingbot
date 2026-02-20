from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants import REST_URL, WS_URL


def rest_url() -> str:
    return REST_URL


def ws_url() -> str:
    return WS_URL


def private_rest_url(path: str) -> str:
    return REST_URL + path
