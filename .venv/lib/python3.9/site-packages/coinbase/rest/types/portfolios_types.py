from typing import List, Optional

from coinbase.rest.types.base_response import BaseResponse
from coinbase.rest.types.common_types import Amount


# List Portfolios
class ListPortfoliosResponse(BaseResponse):
    def __init__(self, response: dict):
        if "portfolios" in response:
            self.portfolios: Optional[List[Portfolio]] = [
                Portfolio(**portfolio) for portfolio in response.pop("portfolios")
            ]
        super().__init__(**response)


# Create Portfolio
class CreatePortfolioResponse(BaseResponse):
    def __init__(self, response: dict):
        if "portfolio" in response:
            self.portfolio: Optional[Portfolio] = Portfolio(**response.pop("portfolio"))
        super().__init__(**response)


# Move Portfolio Funds
class MovePortfolioFundsResponse(BaseResponse):
    def __init__(self, response: dict):
        if "source_portfolio_uuid" in response:
            self.source_portfolio_uuid: Optional[str] = response.pop(
                "source_portfolio_uuid"
            )
        if "target_portfolio_uuid" in response:
            self.target_portfolio_uuid: Optional[str] = response.pop(
                "target_portfolio_uuid"
            )
        super().__init__(**response)


# Get Portfolio Breakdown
class GetPortfolioBreakdownResponse(BaseResponse):
    def __init__(self, response: dict):
        if "breakdown" in response:
            self.breakdown: Optional[PortfolioBreakdown] = PortfolioBreakdown(
                **response.pop("breakdown")
            )
        super().__init__(**response)


# Delete Portfolio
class DeletePortfolioResponse(BaseResponse):
    def __init__(self, response: dict):
        super().__init__(**response)


# Edit Portfolio
class EditPortfolioResponse(BaseResponse):
    def __init__(self, response: dict):
        if "portfolio" in response:
            self.portfolio: Optional[Portfolio] = Portfolio(**response.pop("portfolio"))
        super().__init__(**response)


# ----------------------------------------------------------------


class PortfolioBreakdown(BaseResponse):
    def __init__(self, **kwargs):
        if "portfolio" in kwargs:
            self.portfolio: Optional[Portfolio] = Portfolio(**kwargs.pop("portfolio"))
        if "portfolio_balances" in kwargs:
            self.portfolio_balances: Optional[PortfolioBalances] = kwargs.pop(
                "portfolio_balances"
            )
        if "spot_positions" in kwargs:
            self.spot_positions: Optional[List[PortfolioPosition]] = [
                PortfolioPosition(**portfolio_position)
                for portfolio_position in kwargs.pop("spot_positions")
            ]
        if "perp_positions" in kwargs:
            self.perp_positions: Optional[List[PortfolioPosition]] = [
                PortfolioPosition(**portfolio_position)
                for portfolio_position in kwargs.pop("perp_positions")
            ]
        if "futures_positions" in kwargs:
            self.futures_positions: Optional[List[PortfolioPosition]] = [
                PortfolioPosition(**portfolio_position)
                for portfolio_position in kwargs.pop("futures_positions")
            ]
        super().__init__(**kwargs)


class PortfolioPosition(BaseResponse):
    def __init__(self, **kwargs):
        if "asset" in kwargs:
            self.asset: Optional[str] = kwargs.pop("asset")
        if "account_uuid" in kwargs:
            self.account_uuid: Optional[str] = kwargs.pop("account_uuid")
        if "total_balance_fiat" in kwargs:
            self.total_balance_fiat: Optional[float] = kwargs.pop("total_balance_fiat")
        if "total_balance_crypto" in kwargs:
            self.total_balance_crypto: Optional[float] = kwargs.pop(
                "total_balance_crypto"
            )
        if "available_to_trade_fiat" in kwargs:
            self.available_to_trade_fiat: Optional[float] = kwargs.pop(
                "available_to_trade_fiat"
            )
        if "allocation" in kwargs:
            self.allocation: Optional[float] = kwargs.pop("allocation")
        if "one_day_change" in kwargs:
            self.one_day_change: Optional[float] = kwargs.pop("one_day_change")
        if "cost_basis" in kwargs:
            self.cost_basis: Optional[Amount] = kwargs.pop("cost_basis")
        if "expires_at" in kwargs:
            self.expires_at: Optional[str] = kwargs.pop("expires_at")
        if "leverage" in kwargs:
            self.leverage: Optional[float] = kwargs.pop("leverage")
        if "rate" in kwargs:
            self.rate: Optional[float] = kwargs.pop("rate")
        super().__init__(**kwargs)


class PortfolioBalances(BaseResponse):
    def __init__(self, **kwargs):
        if "total_balance" in kwargs:
            self.total_balance: Optional[Amount] = kwargs.pop("total_balance")
        if "total_futures_balance" in kwargs:
            self.total_futures_balance: Optional[Amount] = kwargs.pop(
                "total_futures_balance"
            )
        if "total_cash_equivalent_balance" in kwargs:
            self.total_cash_equivalent_balance: Optional[Amount] = kwargs.pop(
                "total_cash_equivalent_balance"
            )
        if "total_crypto_balance" in kwargs:
            self.total_crypto_balance: Optional[Amount] = kwargs.pop(
                "total_crypto_balance"
            )
        if "total_neptune_balance" in kwargs:
            self.total_neptune_balance: Optional[Amount] = kwargs.pop(
                "total_neptune_balance"
            )
        super().__init__(**kwargs)


class Portfolio(BaseResponse):
    def __init__(self, **kwargs):
        if "name" in kwargs:
            self.name: Optional[str] = kwargs.pop("name")
        if "uuid" in kwargs:
            self.uuid: Optional[str] = kwargs.pop("uuid")
        if "type" in kwargs:
            self.type: Optional[str] = kwargs.pop("type")
        super().__init__(**kwargs)
