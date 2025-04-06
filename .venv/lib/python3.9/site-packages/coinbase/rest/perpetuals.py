from coinbase.constants import API_PREFIX
from coinbase.rest.types.perpetuals_types import (
    AllocatePortfolioResponse,
    GetPerpetualsPortfolioSummaryResponse,
    GetPerpetualsPositionResponse,
    GetPortfolioBalancesResponse,
    ListPerpetualsPositionsResponse,
    OptInOutMultiAssetCollateralResponse,
)


def allocate_portfolio(
    self, portfolio_uuid: str, symbol: str, amount: str, currency: str, **kwargs
) -> AllocatePortfolioResponse:
    """
    **Allocate Portfolio**
    ________________

    [POST] https://api.coinbase.com/api/v3/brokerage/intx/allocate

    __________

    **Description:**

    Allocate more funds to an isolated position in your Perpetuals portfolio.

    __________

    **Read more on the official documentation:** `Allocate Portfolio
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_allocateportfolio>`_
    """

    endpoint = f"{API_PREFIX}/intx/allocate"

    data = {
        "portfolio_uuid": portfolio_uuid,
        "symbol": symbol,
        "amount": amount,
        "currency": currency,
    }

    return AllocatePortfolioResponse(self.post(endpoint, data=data, **kwargs))


def get_perps_portfolio_summary(
    self, portfolio_uuid: str, **kwargs
) -> GetPerpetualsPortfolioSummaryResponse:
    """
    **Get Perpetuals Portfolio Summary**
    ________________

    [GET] https://api.coinbase.com/api/v3/brokerage/intx/portfolio/{portfolio_uuid}

    __________

    **Description:**

    Get a summary of your Perpetuals portfolio.

    __________

    **Read more on the official documentation:** `Get Perpetuals Portfolio Summary
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getintxportfoliosummary>`_
    """
    endpoint = f"{API_PREFIX}/intx/portfolio/{portfolio_uuid}"

    return GetPerpetualsPortfolioSummaryResponse(self.get(endpoint, **kwargs))


def list_perps_positions(
    self, portfolio_uuid: str, **kwargs
) -> ListPerpetualsPositionsResponse:
    """
    **List Perpetuals Positions**
    ________________

    [GET] https://api.coinbase.com/api/v3/brokerage/intx/positions/{portfolio_uuid}

    __________

    **Description:**

    Get a list of open positions in your Perpetuals portfolio.

    __________

    **Read more on the official documentation:** `List Perpetuals Positions
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getintxpositions>`_
    """
    endpoint = f"{API_PREFIX}/intx/positions/{portfolio_uuid}"

    return ListPerpetualsPositionsResponse(self.get(endpoint, **kwargs))


def get_perps_position(
    self, portfolio_uuid: str, symbol: str, **kwargs
) -> GetPerpetualsPositionResponse:
    """
    **Get Perpetuals Position**
    ________________

    [GET] https://api.coinbase.com/api/v3/brokerage/intx/positions/{portfolio_uuid}/{symbol}

    __________

    **Description:**

    Get a specific open position in your Perpetuals portfolio

    __________

    **Read more on the official documentation:** `Get Perpetuals Positions
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getintxposition>`_
    """
    endpoint = f"{API_PREFIX}/intx/positions/{portfolio_uuid}/{symbol}"

    return GetPerpetualsPositionResponse(self.get(endpoint, **kwargs))


def get_perps_portfolio_balances(
    self, portfolio_uuid: str, **kwargs
) -> GetPortfolioBalancesResponse:
    """
    **Get Portfolio Balances**
    ________________

    [GET] https://api.coinbase.com/api/v3/brokerage/intx/balances/{portfolio_uuid}

    __________

    **Description:**

    Get a list of asset balances on Intx for a given Portfolio

    __________

    **Read more on the official documentation:** `Get Portfolio Balances
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getintxbalances>`_
    """
    endpoint = f"{API_PREFIX}/intx/balances/{portfolio_uuid}"

    return GetPortfolioBalancesResponse(self.get(endpoint, **kwargs))


def opt_in_or_out_multi_asset_collateral(
    self, portfolio_uuid: str, multi_asset_collateral_enabled: bool, **kwargs
) -> OptInOutMultiAssetCollateralResponse:
    """
    **Opt In or Out of Multi Asset Collateral**
    ________________

    [POST] https://api.coinbase.com/api/v3/brokerage/intx/multi_asset_collateral

    __________

    **Description:**

    Enable or Disable Multi Asset Collateral for a given Portfolio.

    __________

    **Read more on the official documentation:** `Opt In or Out of Multi Asset Collateral
    <https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_intxmultiassetcollateral>`_
    """

    endpoint = f"{API_PREFIX}/intx/multi_asset_collateral"

    data = {
        "portfolio_uuid": portfolio_uuid,
        "multi_asset_collateral_enabled": multi_asset_collateral_enabled,
    }

    return OptInOutMultiAssetCollateralResponse(
        self.post(endpoint, data=data, **kwargs)
    )
