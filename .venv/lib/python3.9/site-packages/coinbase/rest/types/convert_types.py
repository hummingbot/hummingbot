from typing import Any, Dict, List, Optional

from coinbase.rest.types.base_response import BaseResponse
from coinbase.rest.types.common_types import Amount


# Create Convert Quote
class CreateConvertQuoteResponse(BaseResponse):
    def __init__(self, response: dict):
        if "trade" in response:
            self.trade: Optional[ConvertTrade] = ConvertTrade(**response.pop("trade"))
        super().__init__(**response)


# Get Convert Trade
class GetConvertTradeResponse(BaseResponse):
    def __init__(self, response: dict):
        if "trade" in response:
            self.trade: Optional[ConvertTrade] = ConvertTrade(**response.pop("trade"))
        super().__init__(**response)


# Commit Convert Trade
class CommitConvertTradeResponse(BaseResponse):
    def __init__(self, response: dict):
        if "trade" in response:
            self.trade: Optional[ConvertTrade] = ConvertTrade(**response.pop("trade"))
        super().__init__(**response)


# ----------------------------------------------------------------


class ConvertTrade(BaseResponse):
    def __init__(self, **kwargs):
        if "id" in kwargs:
            self.id: Optional[str] = kwargs.pop("id")
        if "status" in kwargs:
            self.status: Optional[str] = kwargs.pop("status")
        if "user_entered_amount" in kwargs:
            self.user_entered_amount: Optional[Amount] = kwargs.pop(
                "user_entered_amount"
            )
        if "amount" in kwargs:
            self.amount: Optional[Amount] = kwargs.pop("amount")
        if "subtotal" in kwargs:
            self.subtotal: Optional[Amount] = kwargs.pop("subtotal")
        if "total" in kwargs:
            self.total: Optional[Amount] = kwargs.pop("total")
        if "fees" in kwargs:
            self.fees: Optional[List[Fee]] = [Fee(**fee) for fee in kwargs.pop("fees")]
        if "total_fee" in kwargs:
            self.total_fee: Optional[Fee] = kwargs.pop("total_fee")
        if "source" in kwargs:
            self.source: Optional[ConvertTradePaymentMethod] = kwargs.pop("source")
        if "target" in kwargs:
            self.target: Optional[ConvertTradePaymentMethod] = kwargs.pop("target")
        if "unit_price" in kwargs:
            self.unit_price: Optional[Dict[str, Any]] = kwargs.pop("unit_price")
        if "user_warnings" in kwargs:
            self.user_warnings: Optional[Dict[str, Any]] = kwargs.pop("user_warnings")
        if "user_reference" in kwargs:
            self.user_reference: Optional[str] = kwargs.pop("user_reference")
        if "source_currency" in kwargs:
            self.source_currency: Optional[str] = kwargs.pop("source_currency")
        if "cancellation_reason" in kwargs:
            self.cancellation_reason: Optional[Dict[str, Any]] = kwargs.pop(
                "cancellation_reason"
            )
        if "source_id" in kwargs:
            self.source_id: Optional[str] = kwargs.pop("source_id")
        if "target_id" in kwargs:
            self.target_id: Optional[str] = kwargs.pop("target_id")
        if "subscription_info" in kwargs:
            self.subscription_info: Optional[Dict[str, Any]] = kwargs.pop(
                "subscription_info"
            )
        if "exchange_rate" in kwargs:
            self.exchange_rate: Optional[Amount] = kwargs.pop("exchange_rate")
        if "tax_details" in kwargs:
            self.tax_details: Optional[Dict[str, Any]] = kwargs.pop("tax_details")
        if "trade_incentive_info" in kwargs:
            self.trade_incentive_info: Optional[Dict[str, Any]] = kwargs.pop(
                "trade_incentive_info"
            )
        if "total_fee_without_tax" in kwargs:
            self.total_fee_without_tax: Optional[Dict[str, Any]] = kwargs.pop(
                "total_fee_without_tax"
            )
        if "fiat_denoted_total" in kwargs:
            self.fiat_denoted_total: Optional[Amount] = kwargs.pop("fiat_denoted_total")
        super().__init__(**kwargs)


class ConvertTradePaymentMethod(BaseResponse):
    def __init__(self, **kwargs):
        if "type" in kwargs:
            self.type: Optional[str] = kwargs.pop("type")
        if "network" in kwargs:
            self.network: Optional[str] = kwargs.pop("network")
        if "identifier" in kwargs:
            self.network: Optional[Dict[str, Any]] = kwargs.pop("identifier")
        super().__init__(**kwargs)


class Fee(BaseResponse):
    def __init__(self, **kwargs):
        if "title" in kwargs:
            self.title: Optional[str] = kwargs.pop("title")
        if "description" in kwargs:
            self.description: Optional[str] = kwargs.pop("description")
        if "amount" in kwargs:
            self.amount: Optional[Amount] = kwargs.pop("amount")
        if "label" in kwargs:
            self.label: Optional[str] = kwargs.pop("label")
        if "disclosure" in kwargs:
            self.disclosure: Optional[Dict[str, Any]] = kwargs.pop("disclosure")
        super().__init__(**kwargs)
