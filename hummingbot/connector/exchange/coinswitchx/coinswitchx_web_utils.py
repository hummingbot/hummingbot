import hummingbot.connector.exchange.coinswitchx.coinswitchx_constants as CONSTANTS


def rest_url(path_url: str) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :return: the full URL to the endpoint
    """
    return f"https://{CONSTANTS.REST_URL}/api/{path_url}"


def websocket_url() -> str:
    """
    Creates a full URL for provided WebSocket endpoint
    :return: the full URL to the endpoint
    """
    return f"wss://{CONSTANTS.WSS_URL}/"
