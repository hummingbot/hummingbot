# TODO remove this file!!!
from hummingbot.connector.gateway.clob.clob_types import Chain

# from hummingbot.connector.gateway.clob.gateway_clob import GatewayCLOB


# def test_01():
#     chain = 'solana'
#     network = 'testnet'
#     connector = 'serum'
#     wallet_address = '0x0000000000000000000000000000000000000000'
#     trading_pairs = ['SOL-USDT', 'SOL-USDC', 'SRM-SOL']
#     is_trading_required = True
#
#     exchange = GatewayCLOB(
#         connector,
#         chain,
#         network,
#         wallet_address,
#         trading_pairs,
#         is_trading_required
#     )
#
#     print('name', exchange.name)

def test_02():
    print('chain', Chain.SOLANA.chain)
    print('native_currency', Chain.SOLANA.native_currency)


if __name__ == '__main__':
    test_02()
