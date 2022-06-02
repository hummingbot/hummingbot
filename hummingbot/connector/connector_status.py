#!/usr/bin/env python

connector_status = {
    'altmarkets': 'green',
    'ascend_ex': 'yellow',
    'balancer': 'red',
    'beaxy': 'green',
    'binance': 'green',
    'binance_perpetual': 'yellow',
    'binance_perpetual_testnet': 'yellow',
    'binance_us': 'green',
    'bitfinex': 'yellow',
    'bitmart': 'yellow',
    'bittrex': 'yellow',
    'blocktane': 'yellow',
    'bybit_perpetual': 'green',
    'bybit_perpetual_testnet': 'green',
    'celo': 'yellow',
    'coinbase_pro': 'yellow',
    'coinflex': 'green',
    'coinflex_test': 'green',
    'coinzoom': 'yellow',
    'crypto_com': 'green',
    'digifinex': "yellow",
    'dydx_perpetual': 'yellow',
    'ethereum': 'red',
    'ftx': 'green',
    'gate_io': 'green',
    'hitbtc': 'green',
    'huobi': 'yellow',
    'kraken': 'green',
    'kucoin': 'yellow',
    'kucoin_testnet': 'yellow',
    'k2': 'red',
    'liquid': 'green',
    'loopring': 'yellow',
    'mexc': 'yellow',
    'ndax': 'yellow',
    'ndax_testnet': 'yellow',
    'okex': 'green',
    'pangolin_avalanche_avalanche': 'yellow',
    'perpetual_finance': 'red',
    'probit': 'yellow',
    'probit_kr': 'yellow',
    'terra': 'red',
    'uniswap': 'yellow',
    'uniswap_v3': 'yellow',
    'uniswap_ethereum_kovan': 'yellow',
    'wazirx': 'yellow'
}

warning_messages = {
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
        return f"&c{connector_status[connector_name].upper()}"
    return status
