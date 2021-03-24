# import typing
#
# from dataclasses import dataclass
#
# from ..enums import OrderSelfTradePrevention, OrderTimeInForce, OrderType, OrderSide
#
#
# @dataclass
# class RestRequestCancelOrder:
#     wallet: str = None
#     nonce: typing.Optional[str] = None
#     orderId: typing.Optional[str] = None
#
#
# @dataclass
# class RestRequestCancelAllOrders:
#     wallet: str = None
#     nonce: typing.Optional[str] = None
#
#
# @dataclass
# class RestRequestCancelOrdersBody:
#     parameters: RestRequestCancelOrder
#     signature: str = None
#
#
# @dataclass
# class RestRequestFindByWallet:
#     nonce: str
#     wallet: str
#
#
# @dataclass
# class RestRequestFindWithPagination:
#     start: typing.Optional[int]
#     end: typing.Optional[int]
#     limit: typing.Optional[int]
#
#
# @dataclass
# class RestRequestFindBalances:
#     wallet: str
#     asset: typing.Optional[str] = None
#
#
# # @dataclass
# # class RestRequestFindCandles(RestRequestFindWithPagination):
# #     market: str
# #     interval: CandleInterval
#
#
# @dataclass
# class RestRequestFindDeposit(RestRequestFindByWallet):
#     depositId: str
#
#
# @dataclass
# class RestRequestFindDeposits(RestRequestFindByWallet, RestRequestFindWithPagination):
#     asset: typing.Optional[str]
#     fromId: typing.Optional[str]
#
#
# @dataclass
# class RestRequestFindFill(RestRequestFindByWallet):
#     fillId: str
#
#
# @dataclass
# class RestRequestFindFills(RestRequestFindByWallet, RestRequestFindWithPagination):
#     market: typing.Optional[str]
#     fromId: typing.Optional[str]
#
#
# @dataclass
# class RestRequestFindMarkets:
#     market: typing.Optional[str] = None
#     regionOnly: typing.Optional[bool] = None
#
#
# @dataclass
# class RestRequestFindOrder(RestRequestFindByWallet):
#     orderId: str
#
#
# @dataclass
# class RestRequestFindOrders():
#     nonce: str
#     orderId: str
#     wallet: str
#
#
# @dataclass
# class RestRequestFindTrades(RestRequestFindWithPagination):
#     market: typing.Optional[str]
#     fromId: typing.Optional[str]
#
#
# @dataclass
# class RestRequestFindWithdrawal(RestRequestFindByWallet):
#     withdrawalId: str
#
#
# @dataclass
# class RestRequestFindWithdrawals(RestRequestFindByWallet, RestRequestFindWithPagination):
#     asset: typing.Optional[str]
#     assetContractAddress: typing.Optional[str]
#     fromId: typing.Optional[str]
#
#
# @dataclass
# class RestRequestAllOrderParameters:
#     """
#     NOTE: Is not documented
#     """
#     wallet: str
#     market: typing.Optional[str] = None
#     type: typing.Optional[OrderType] = None
#     side: typing.Optional[OrderSide] = None
#     nonce: typing.Optional[str] = None
#     quantity: typing.Optional[str] = None
#     # quoteOrderQuantity: typing.Optional[str] = None
#     price: typing.Optional[str] = None
#     # stopPrice: typing.Optional[str] = None
#     clientOrderId: typing.Optional[str] = None
#     timeInForce: typing.Optional[OrderTimeInForce] = None
#     selfTradePrevention: typing.Optional[OrderSelfTradePrevention] = "dc"
#     # cancelAfter: typing.Optional[typing.Union[int, float]] = "dc"
#
#
# @dataclass
# class RestRequestOrder(RestRequestAllOrderParameters):
#     pass
#
#
# @dataclass
# class RestRequestCreateOrderBody:
#     parameters: RestRequestOrder
#     signature: str = None
#
#
# @dataclass
# class RestRequestWithdrawalBase:
#     nonce: str
#     wallet: str
#     quantity: str
#     # Currently has no effect
#     autoDispatchEnabled: typing.Optional[bool]
#
#
# @dataclass
# class RestRequestWithdrawalBySymbol(RestRequestWithdrawalBase):
#     asset: str
#     assetContractAddress: typing.Optional[str]
#
#
# @dataclass
# class RestRequestWithdrawalByAddress(RestRequestWithdrawalBase):
#     assetContractAddress: str
#     asset: typing.Optional[str]
#
#
# RestRequestWithdrawal = typing.Union[RestRequestWithdrawalBySymbol, RestRequestWithdrawalByAddress]
#
#
# @dataclass
# class RestRequestCreateWithdrawalBody:
#     parameters: RestRequestWithdrawal
#     signature: str = None
#
#
# @dataclass
# class RestRequestAssociateWallet:
#     nonce: str
#     wallet: str
#
#
# @dataclass
# class RestRequestOrderBook:
#     market: str
#     level: typing.Optional[int] = None
#     limit: typing.Optional[int] = None
