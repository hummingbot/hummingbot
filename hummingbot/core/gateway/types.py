from typing import Any, Dict, Optional

from pydantic import BaseModel


class WalletBalances(BaseModel):
    network: str
    timestamp: int
    latency: float
    balances: Dict[str, str]


class Transaction(BaseModel):
    network: str
    timestamp: int
    latency: float
    base: str
    quote: str
    amount: str
    rawAmount: str
    expectedIn: str
    price: str
    gasPrice: int
    gasPriceToken: str
    gasLimit: int
    gasCost: str
    nonce: int
    txHash: str


class TransactionStatus(BaseModel):
    network: str
    currentBlock: int
    timestamp: int
    txHash: str
    txBlock: int
    txStatus: int
    txData: Dict[str, Any]
    txReceipt: Optional[Any]


class TokenPrice(BaseModel):
    network: str
    timestamp: int
    latency: float
    base: str
    quote: str
    amount: str
    rawAmount: str
    expectedAmount: str
    price: str
    gasPrice: int
    gasPriceToken: str
    gasLimit: int
    gasCost: str
