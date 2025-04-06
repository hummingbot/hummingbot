from typing import Any, Dict, Optional

from coinbase.rest.types.base_response import BaseResponse


# Get Transaction Summary
class GetTransactionSummaryResponse(BaseResponse):
    def __init__(self, response: dict):
        if "total_volume" in response:
            self.total_volume: float = response.pop("total_volume", 0.0)
        if "total_fees" in response:
            self.total_fees: float = response.pop("total_fees", 0.0)
        if "fee_tier" in response:
            self.fee_tier: FeeTier = response.pop("fee_tier")
        if "margin_rate" in response:
            self.margin_rate: Optional[Dict[str, Any]] = response.pop("margin_rate")
        if "goods_and_services_tax" in response:
            self.goods_and_services_tax: Optional[Dict[str, Any]] = response.pop(
                "goods_and_services_tax"
            )
        if "advanced_trade_only_volumes" in response:
            self.advanced_trade_only_volumes: Optional[float] = response.pop(
                "advanced_trade_only_volumes"
            )
        if "advanced_trade_only_fees" in response:
            self.advanced_trade_only_fees: Optional[float] = response.pop(
                "advanced_trade_only_fees"
            )
        if "coinbase_pro_volume" in response:  # deprecated
            self.coinbase_pro_volume: Optional[float] = response.pop(
                "coinbase_pro_volume"
            )
        if "coinbase_pro_fees" in response:  # deprecated
            self.coinbase_pro_fees: Optional[float] = response.pop("coinbase_pro_fees")
        if "total_balance" in response:
            self.total_balance: Optional[str] = response.pop("total_balance")
        if "has_promo_fee" in response:
            self.has_promo_fee: Optional[bool] = response.pop("has_promo_fee")
        super().__init__(**response)


# ----------------------------------------------------------------


class FeeTier(BaseResponse):
    def __init__(self, **kwargs):
        if "pricing_tier" in kwargs:
            self.pricing_tier: Optional[str] = kwargs.pop("pricing_tier")
        if "usd_from" in kwargs:
            self.usd_from: Optional[str] = kwargs.pop("usd_from")
        if "usd_to" in kwargs:
            self.usd_to: Optional[str] = kwargs.pop("usd_to")
        if "taker_fee_rate" in kwargs:
            self.taker_fee_rate: Optional[str] = kwargs.pop("taker_fee_rate")
        if "maker_fee_rate" in kwargs:
            self.maker_fee_rate: Optional[str] = kwargs.pop("maker_fee_rate")
        if "aop_from" in kwargs:
            self.aop_from: Optional[str] = kwargs.pop("aop_from")
        if "aop_to" in kwargs:
            self.aop_to: Optional[str] = kwargs.pop("aop_to")
        super().__init__(**kwargs)
