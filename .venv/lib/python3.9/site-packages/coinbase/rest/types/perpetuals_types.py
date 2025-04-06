from typing import Any, Dict, List, Optional

from coinbase.rest.types.base_response import BaseResponse
from coinbase.rest.types.common_types import Amount


# Allocate Portfolio
class AllocatePortfolioResponse(BaseResponse):
    def __init__(self, response: dict):
        super().__init__(**response)


# Get Perpetuals Portfolio Summary
class GetPerpetualsPortfolioSummaryResponse(BaseResponse):
    def __init__(self, response: dict):
        if "portfolios" in response:
            self.portfolios: Optional[List[PerpetualPortfolio]] = [
                PerpetualPortfolio(**portfolio)
                for portfolio in response.pop("portfolios")
            ]
        if "summary" in response:
            self.summary: Optional[PortfolioSummary] = PortfolioSummary(
                **response.pop("summary")
            )
        super().__init__(**response)


# List Perpetuals Positions
class ListPerpetualsPositionsResponse(BaseResponse):
    def __init__(self, response: dict):
        if "positions" in response:
            self.positions: Optional[List[Position]] = [
                Position(**pos) for pos in response.pop("positions")
            ]
        if "summary" in response:
            self.summary: Optional[PositionSummary] = PositionSummary(
                **response.pop("summary")
            )
        super().__init__(**response)


# Get Perpetuals Position
class GetPerpetualsPositionResponse(BaseResponse):
    def __init__(self, response: dict):
        if "position" in response:
            self.position: Optional[Position] = Position(**response.pop("position"))
        super().__init__(**response)


# Get Portfolio Balances
class GetPortfolioBalancesResponse(BaseResponse):
    def __init__(self, response: dict):
        if "portfolio_balances" in response:
            self.portfolio_balances: Optional[List[PortfolioBalance]] = [
                PortfolioBalance(**balance)
                for balance in response.pop("portfolio_balances")
            ]
        super().__init__(**response)


# Opt In or Out of Multi Asset Collateral
class OptInOutMultiAssetCollateralResponse(BaseResponse):
    def __init__(self, response: dict):
        if "cross_collateral_enabled" in response:
            self.cross_collateral_enabled: Optional[bool] = response.pop(
                "cross_collateral_enabled"
            )
        super().__init__(**response)


# ----------------------------------------------------------------


class PerpetualPortfolio(BaseResponse):
    def __init__(self, **kwargs):
        if "portfolio_uuid" in kwargs:
            self.portfolio_uuid: Optional[str] = kwargs.pop("portfolio_uuid")
        if "collateral" in kwargs:
            self.collateral: Optional[str] = kwargs.pop("collateral")
        if "position_notional" in kwargs:
            self.position_notional: Optional[str] = kwargs.pop("position_notional")
        if "open_position_notional" in kwargs:
            self.open_position_notional: Optional[str] = kwargs.pop(
                "open_position_notional"
            )
        if "pending_fees" in kwargs:
            self.pending_fees: Optional[str] = kwargs.pop("pending_fees")
        if "borrow" in kwargs:
            self.borrow: Optional[str] = kwargs.pop("borrow")
        if "accrued_interest" in kwargs:
            self.accrued_interest: Optional[str] = kwargs.pop("accrued_interest")
        if "rolling_debt" in kwargs:
            self.rolling_debt: Optional[str] = kwargs.pop("rolling_debt")
        if "portfolio_initial_margin" in kwargs:
            self.portfolio_initial_margin: Optional[str] = kwargs.pop(
                "portfolio_initial_margin"
            )
        if "portfolio_im_notional" in kwargs:
            self.portfolio_im_notional: Optional[Amount] = kwargs.pop(
                "portfolio_im_notional"
            )
        if "portfolio_maintenance_margin" in kwargs:
            self.portfolio_maintenance_margin: Optional[str] = kwargs.pop(
                "portfolio_maintenance_margin"
            )
        if "portfolio_mm_notional" in kwargs:
            self.portfolio_mm_notional: Optional[Amount] = kwargs.pop(
                "portfolio_mm_notional"
            )
        if "liquidation_percentage" in kwargs:
            self.liquidation_percentage: Optional[str] = kwargs.pop(
                "liquidation_percentage"
            )
        if "liquidation_buffer" in kwargs:
            self.liquidation_buffer: Optional[str] = kwargs.pop("liquidation_buffer")
        if "margin_type" in kwargs:
            self.margin_type: Optional[str] = kwargs.pop("margin_type")
        if "margin_flags" in kwargs:
            self.margin_flags: Optional[str] = kwargs.pop("margin_flags")
        if "liquidation_status" in kwargs:
            self.liquidation_status: Optional[str] = kwargs.pop("liquidation_status")
        if "unrealized_pnl" in kwargs:
            self.unrealized_pnl: Optional[Amount] = kwargs.pop("unrealized_pnl")
        if "total_balance" in kwargs:
            self.total_balance: Optional[Amount] = kwargs.pop("total_balance")
        super().__init__(**kwargs)


class PortfolioSummary(BaseResponse):
    def __init__(self, **kwargs):
        if "unrealized_pnl" in kwargs:
            self.unrealized_pnl: Optional[Amount] = kwargs.pop("unrealized_pnl")
        if "buying_power" in kwargs:
            self.buying_power: Optional[Amount] = kwargs.pop("buying_power")
        if "total_balance" in kwargs:
            self.total_balance: Optional[Amount] = kwargs.pop("total_balance")
        if "max_withdrawal_amount" in kwargs:
            self.max_withdrawal_amount: Optional[Amount] = kwargs.pop(
                "max_withdrawal_amount"
            )
        super().__init__(**kwargs)


class Position(BaseResponse):
    def __init__(self, **kwargs):
        if "product_id" in kwargs:
            self.product_id: Optional[str] = kwargs.pop("product_id")
        if "product_uuid" in kwargs:
            self.product_uuid: Optional[str] = kwargs.pop("product_uuid")
        if "portfolio_uuid" in kwargs:
            self.portfolio_uuid: Optional[str] = kwargs.pop("portfolio_uuid")
        if "symbol" in kwargs:
            self.symbol: Optional[str] = kwargs.pop("symbol")
        if "vwap" in kwargs:
            self.vwap: Optional[Amount] = kwargs.pop("vwap")
        if "entry_vwap" in kwargs:
            self.entry_vwap: Optional[Amount] = kwargs.pop("entry_vwap")
        if "position_side" in kwargs:
            self.position_side: Optional[str] = kwargs.pop("position_side")
        if "margin_type" in kwargs:
            self.margin_type: Optional[str] = kwargs.pop("margin_type")
        if "net_size" in kwargs:
            self.net_size: Optional[str] = kwargs.pop("net_size")
        if "buy_order_size" in kwargs:
            self.buy_order_size: Optional[str] = kwargs.pop("buy_order_size")
        if "sell_order_size" in kwargs:
            self.sell_order_size: Optional[str] = kwargs.pop("sell_order_size")
        if "im_contribution" in kwargs:
            self.im_contribution: Optional[str] = kwargs.pop("im_contribution")
        if "unrealized_pnl" in kwargs:
            self.unrealized_pnl: Optional[Amount] = kwargs.pop("unrealized_pnl")
        if "mark_price" in kwargs:
            self.mark_price: Optional[Amount] = kwargs.pop("mark_price")
        if "liquidation_price" in kwargs:
            self.liquidation_price: Optional[Amount] = kwargs.pop("liquidation_price")
        if "leverage" in kwargs:
            self.leverage: Optional[str] = kwargs.pop("leverage")
        if "im_notional" in kwargs:
            self.im_notional: Optional[Amount] = kwargs.pop("im_notional")
        if "mm_notional" in kwargs:
            self.mm_notional: Optional[Amount] = kwargs.pop("mm_notional")
        if "position_notional" in kwargs:
            self.position_notional: Optional[Amount] = kwargs.pop("position_notional")
        if "aggregated_pnl" in kwargs:
            self.aggregated_pnl: Optional[Amount] = kwargs.pop("aggregated_pnl")

        super().__init__(**kwargs)


class PositionSummary(BaseResponse):
    def __init__(self, **kwargs):
        if "aggregated_pnl" in kwargs:
            self.aggregated_pnl: Optional[Dict[str, Any]] = kwargs.pop("aggregated_pnl")
        super().__init__(**kwargs)


class PortfolioBalance(BaseResponse):
    def __init__(self, **kwargs):
        if "portfolio_uuid" in kwargs:
            self.portfolio_uuid: Optional[str] = kwargs.pop("portfolio_uuid")
        if "balances" in kwargs:
            self.balances: Optional[List[Balance]] = [
                Balance(**balance) for balance in kwargs.pop("balances")
            ]
        if "is_margin_limit_reached" in kwargs:
            self.is_margin_limit_reached: Optional[bool] = kwargs.pop(
                "is_margin_limit_reached"
            )
        super().__init__(**kwargs)


class Balance(BaseResponse):
    def __init__(self, **kwargs):
        if "asset" in kwargs:
            self.asset: Dict[str, Any] = kwargs.pop("asset")
        if "quantity" in kwargs:
            self.quantity: str = kwargs.pop("quantity")
        if "hold" in kwargs:
            self.hold: str = kwargs.pop("hold")
        if "transfer_hold" in kwargs:
            self.transfer_hold: str = kwargs.pop("transfer_hold")
        if "collateral_value" in kwargs:
            self.collateral_value: str = kwargs.pop("collateral_value")
        if "collateral_weight" in kwargs:
            self.collateral_weight: str = kwargs.pop("collateral_weight")
        if "max_withdraw_amount" in kwargs:
            self.max_withdraw_amount: str = kwargs.pop("max_withdraw_amount")
        if "loan" in kwargs:
            self.loan: str = kwargs.pop("loan")
        if "loan_collateral_requirement_usd" in kwargs:
            self.loan_collateral_requirement_usd: str = kwargs.pop(
                "loan_collateral_requirement_usd"
            )
        if "pledged_quantity" in kwargs:
            self.pledged_quantity: str = kwargs.pop("pledged_quantity")
        super().__init__(**kwargs)
