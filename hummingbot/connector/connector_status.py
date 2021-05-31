#!/usr/bin/env python

connector_status = {
    'ascend_ex': 'yellow',
    'balancer': 'green',
    'beaxy': 'green',
    'binance': 'green',
    'binance_perpetual': 'yellow',
    'binance_perpetual_testnet': 'yellow',
    'binance_us': 'yellow',
    'bitfinex': 'yellow',
    'bittrex': 'yellow',
    'blocktane': 'green',
    'celo': 'green',
    'coinbase_pro': 'yellow',
    'coinzoom': 'yellow',
    'crypto_com': 'yellow',
    'digifinex': "yellow",
    'dydx': 'green',
    'dydx_perpetual': 'yellow',
    'ethereum': 'red',
    'ftx': 'yellow',
    'hitbtc': 'green',
    'huobi': 'green',
    'kraken': 'green',
    'kucoin': 'green',
    'k2': 'red',
    'liquid': 'green',
    'loopring': 'yellow',
    'okex': 'yellow',
    'perpetual_finance': 'yellow',
    'probit': 'yellow',
    'probit_kr': 'yellow',
    'terra': 'green',
    'uniswap': 'green'
}

warning_messages = {
    'eterbase': 'Hack investigation and security audit is ongoing for Eterbase. Trading is currently disabled.'
}


def get_connector_status(connector_name: str) -> str:
    """
    Indicator whether a connector is working properly or not.
    UNKNOWN means the connector is not in connector_status dict.
    RED means a connector doesn't work.
    YELLOW means the connector is either new or has one or more issues.
    GREEN means a connector is working properly.
    """
    if connector_name not in connector_status.keys():
        status = "UNKNOWN"
    else:
        return connector_status[connector_name].upper()
    return status
