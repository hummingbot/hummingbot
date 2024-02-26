#!/usr/bin/env python

connector_status = {
    # client connectors
    'ascend_ex': 'bronze',
    'binance': 'bronze',
    'binance_perpetual': 'bronze',
    'binance_perpetual_testnet': 'bronze',
    'binance_us': 'bronze',
    'bitfinex': 'bronze',
    'bitget_perpetual': 'bronze',
    'bitmart': 'bronze',
    'bit_com_perpetual': 'bronze',
    'bit_com_perpetual_testnet': 'bronze',
    'btc_markets': 'bronze',
    'bybit_perpetual': 'bronze',
    'bybit_perpetual_testnet': 'bronze',
    'bybit_testnet': 'bronze',
    'bybit': 'bronze',
    'coinbase_pro': 'silver',
    'dydx_perpetual': 'gold',
    'foxbit': 'bronze',
    'gate_io': 'bronze',
    'gate_io_perpetual': 'bronze',
    'injective_v2': 'bronze',
    'injective_v2_perpetual': 'bronze',
    'hitbtc': 'bronze',
    'hyperliquid_perpetual_testnet': 'bronze',
    'hyperliquid_perpetual': 'bronze',
    'htx': 'bronze',
    'kraken': 'silver',
    'kucoin': 'silver',
    'kucoin_perpetual': 'silver',
    'mexc': 'bronze',
    'ndax': 'bronze',
    'ndax_testnet': 'bronze',
    'okx': 'gold',
    'phemex_perpetual': 'bronze',
    'phemex_perpetual_testnet': 'bronze',
    'polkadex': 'bronze',
    'vertex': 'bronze',
    'vertex_testnet': 'bronze',
    # gateway connectors
    'curve': 'bronze',
    'dexalot': 'bronze',
    'defira': 'bronze',
    'kujira': 'bronze',
    'mad_meerkat': 'bronze',
    'openocean': 'bronze',
    'quickswap': 'bronze',
    'quipuswap': 'bronze',
    'pancakeswap': 'silver',
    'pancakeswapLP': 'silver',
    'pangolin': 'bronze',
    'perp': 'bronze',
    'plenty': 'bronze',
    'ref': 'bronze',
    'sushiswap': 'bronze',
    'tinyman': 'bronze',
    'traderjoe': 'bronze',
    'uniswap': 'silver',
    'uniswapLP': 'silver',
    'vega_perpetual': 'bronze',
    'vega_perpetual_testnet': 'bronze',
    'vvs': 'bronze',
    'xswap': 'bronze',
    'xrpl': 'silver',
    'carbonamm': 'bronze',
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
