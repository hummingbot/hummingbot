from hummingbot.connector.connector.uniswap.uniswap_connector import UniswapConnector


class UniswapV3Connector(UniswapConnector):
    """
    UniswapV3Connector extends UniswapConnector to provide v3 specific functionality, e.g. ranged positions
    """

    def add_position(self, token: str):
        return self.name + " " + token
