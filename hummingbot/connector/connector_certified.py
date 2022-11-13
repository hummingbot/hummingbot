certified_connector = {
    'binance': 'green',
    'binance_perpetual': 'yellow',
    'ascendex': 'green',
    'gate_io': 'green',
    'kucoin': 'green',
    'kucoin_testnet': 'green',
    'hitbtc': 'green',
    'okx': 'green',
    'ftx': 'green',
    'bybit': 'green',
    'bybit_perpetual': 'green',
    'huobi': 'green'
}


def get_connector_certified(connector_name):
    """
    Filters connectors that are certified by adding background of GREEN color
    """
    if connector_name in certified_connector:
        return f"{connector_name}"
    else:
        return connector_name
