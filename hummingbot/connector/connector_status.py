#!/usr/bin/env python

connector_status = {
    # client connectors
    'ascend_ex': 'bronze',
    'binance': 'gold',
    'binance_perpetual': 'gold',
    'binance_perpetual_testnet': 'gold',
    'binance_us': 'bronze',
    'bitfinex': 'bronze',
    'bitget_perpetual': 'bronze',
    'bitmart': 'bronze',
    'bitmex': 'bronze',
    'bitmex_perpetual': 'bronze',
    'bitmex_testnet': 'bronze',
    'bitmex_perpetual_testnet': 'bronze',
    'bit_com_perpetual': 'bronze',
    'bit_com_perpetual_testnet': 'bronze',
    'btc_markets': 'bronze',
    'bybit_perpetual': 'bronze',
    'bybit_perpetual_testnet': 'bronze',
    'bybit_testnet': 'bronze',
    'bybit': 'bronze',
    'coinbase_pro': 'bronze',
    'dydx_perpetual': 'gold',
    'foxbit': 'bronze',
    'gate_io': 'silver',
    'gate_io_perpetual': 'silver',
    'injective_v2': 'silver',
    'injective_v2_perpetual': 'silver',
    'hitbtc': 'bronze',
    'huobi': 'silver',
    'kraken': 'bronze',
    'kucoin': 'silver',
    'kucoin_perpetual': 'silver',
    'mexc': 'bronze',
    'ndax': 'bronze',
    'ndax_testnet': 'bronze',
    'okx': 'bronze',
    'phemex_perpetual': 'bronze',
    'phemex_perpetual_testnet': 'bronze',
    'polkadex': 'silver',
    'vertex': 'bronze',
    'vertex_testnet': 'bronze',
    # gateway connectors
    'curve': 'bronze',
    'dexalot': 'silver',
    'defira': 'bronze',
    'kujira': 'bronze',
    'mad_meerkat': 'bronze',
    'openocean': 'bronze',
    'quickswap': 'bronze',
    'pancakeswap': 'bronze',
    'pangolin': 'bronze',
    'perp': 'bronze',
    'plenty': 'bronze',
    'ref': 'bronze',
    'sushiswap': 'bronze',
    'tinyman': 'bronze',
    'traderjoe': 'bronze',
    'uniswap': 'bronze',
    'uniswapLP': 'bronze',
    'vvs': 'bronze',
    'woo_x': 'bronze',
    'woo_x_testnet': 'bronze',
    'xswap': 'bronze',
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
