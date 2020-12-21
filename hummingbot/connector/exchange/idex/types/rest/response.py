import typing
from dataclasses import dataclass

from ..enums import *


@dataclass
class RestResponseAsset:
    name: str
    symbol: str
    contractAddress: str
    assetDecimals: int
    exchangeDecimals: typing.Literal[8]


@dataclass
class RestResponseBalance:
    asset: str
    quantity: str
    availableForTrade: str
    locked: str
    usdValue: str


@dataclass
class RestResponseCandle:
    start: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    sequence: int


@dataclass
class RestResponseDeposit:
    depositId: str
    asset: str
    quantity: str
    txId: str
    txTime: float
    confirmationTime: float


@dataclass
class RestResponseExchangeInfo:
    timeZone: str
    serverTime: float
    ethereumDepositContractAddress: str
    ethUsdPrice: str
    gasPrice: float
    volume24hUsd: str
    makerFeeRate: str
    takerFeeRate: str
    makerTradeMinimum: str
    takerTradeMinimum: str
    withdrawMinimum: str


@dataclass
class RestResponseOrderFill:
    fillId: str
    price: str
    quantity: str
    quoteQuantity: str
    time: float
    makerSide: OrderSide
    sequence: int
    fee: str
    feeAsset: str
    liquidity: Liquidity
    txStatus: EthTransactionStatus
    gas: typing.Optional[str]
    txId: typing.Optional[str]


@dataclass
class RestResponseFill(RestResponseOrderFill):
    orderId: str
    market: str
    side: OrderSide
    clientOrderId: typing.Optional[str]


@dataclass
class RestResponseMarket:
    market: str
    status: MarketStatus
    baseAsset: str
    baseAssetPrecision: int
    quoteAsset: str
    quoteAssetPrecision: int


@dataclass
class RestResponseOrder:
    market: str
    orderId: str
    wallet: str
    time: float
    status: OrderStatus
    type: OrderType
    side: OrderSide
    executedQuantity: str
    cumulativeQuoteQuantity: str
    timeInForce: OrderTimeInForce
    selfTradePrevention: OrderSelfTradePrevention
    originalQuoteQuantity: typing.Optional[str]
    originalQuantity: typing.Optional[str]
    avgExecutionPrice: typing.Optional[str]
    errorCode: typing.Optional[str]
    errorMessage: typing.Optional[str]
    price: typing.Optional[str]
    clientOrderId: typing.Optional[str]
    stopPrice: typing.Optional[str]
    fills: typing.Optional[
        typing.List[RestResponseOrderFill]
    ]


@dataclass
class RestResponseCanceledOrderItem:
    orderId: str


RestResponseCanceledOrder = typing.List[RestResponseCanceledOrderItem]

Price = str
Size = str
NumOrders = int


RestResponseOrderBookPriceLevel = typing.Tuple[Price, Size, NumOrders]


@dataclass
class RestResponseOrderBook:
    sequence: int
    bids: typing.List[RestResponseOrderBookPriceLevel]
    asks: typing.List[RestResponseOrderBookPriceLevel]


@dataclass
class RestResponseOrderBookLevel1(RestResponseOrderBook):
    bids: typing.List[RestResponseOrderBookPriceLevel]  # Single record
    asks: typing.List[RestResponseOrderBookPriceLevel]  # Single record


@dataclass
class RestResponseOrderBookLevel2(RestResponseOrderBook):
    bids: typing.List[RestResponseOrderBookPriceLevel]
    asks: typing.List[RestResponseOrderBookPriceLevel]


@dataclass
class RestResponseTicker:
    market: typing.Optional[str]
    percentChange: typing.Optional[str]
    baseVolume: typing.Optional[str]
    quoteVolume: typing.Optional[str]
    time: float
    numTrades: int
    low: typing.Optional[str] = None
    high: typing.Optional[str] = None
    bid: typing.Optional[str] = None
    ask: typing.Optional[str] = None
    open: typing.Optional[str] = None
    close: typing.Optional[str] = None
    closeQuantity: typing.Optional[str] = None
    sequence: typing.Optional[int] = None


@dataclass
class RestResponseTime:
    serverTime: int


@dataclass
class RestResponseTrade:
    fillId: str
    price: str
    quantity: str
    quoteQuantity: str
    time: float
    makerSide: OrderSide
    sequence: int


@dataclass
class RestResponseUser:
    depositEnabled: bool
    orderEnabled: bool
    cancelEnabled: bool
    withdrawEnabled: bool
    kycTier: typing.Literal[0, 1, 2]
    totalPortfolioValueUsd: str
    withdrawalLimit: str
    withdrawalRemaining: str
    makerFeeRate: str
    takerFeeRate: str


@dataclass
class RestResponseWallet:
    address: str
    totalPortfolioValueUsd: str
    time: float


@dataclass
class RestResponseWebSocketToken:
    token: str


@dataclass
class RestResponseWithdrawalBase:
    withdrawalId: str
    quantity: str
    time: float
    fee: str
    txStatus: EthTransactionStatus
    txId: typing.Optional[str]


@dataclass
class RestResponseWithdrawalBySymbol(RestResponseWithdrawalBase):
    asset: str
    assetContractAddress: typing.Optional[str]


@dataclass
class RestResponseWithdrawalByAddress(RestResponseWithdrawalBase):
    assetContractAddress: str
    asset: typing.Optional[str]


RestResponseWithdrawal = typing.Union[
    RestResponseWithdrawalBySymbol,
    RestResponseWithdrawalByAddress
]


@dataclass
class RestResponseAssociateWallet:
    address: str
    totalPortfolioValueUsd: str
    time: float
