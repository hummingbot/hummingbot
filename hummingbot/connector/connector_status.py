#!/usr/bin/env python

connector_status = {
    'binance': 'green',
    'binance_us': 'yellow',
    'bitfinex': 'green',
    'bittrex': 'yellow',
    'celo': 'green',
    'coinbase_pro': 'green',
    'crypto_com': 'yellow',
    'eterbase': 'red',
    'ethereum': 'red',
    'huobi': 'green',
    'kraken': 'yellow',
    'kucoin': 'green',
    'liquid': 'green',
    'loopring': 'green',
    'okex': 'red'
}


def get_connector_status(connector_name: str) -> str:
    """
    Indicator whether a connector is working properly or not. UNKNOWN means the connector is not in the dict.
    RED means a connector doesn't work, YELLOW means the connector is either new or has one or more issues.
    GREEN means a connector is working properly. The connector_status dict is updated every new release.
    """
    if connector_name not in connector_status.keys():
        status = "UNKNOWN"
    else:
        return connector_status[connector_name].upper()
    return status
