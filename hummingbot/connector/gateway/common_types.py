from enum import Enum


class Chain(Enum):
    SOLANA = ('solana', 'SOL')
    ETHEREUM = ('ethereum', 'ETH')

    def __init__(self, chain: str, native_currency: str):
        self.chain = chain
        self.native_currency = native_currency


class Connector(Enum):
    def __int__(self, chain: Chain, connector: str):
        self.chain = chain
        self.connector = connector
