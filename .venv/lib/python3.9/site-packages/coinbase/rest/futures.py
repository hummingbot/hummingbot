from typing import Any, Dict, Optional

from coinbase.constants import API_PREFIX
from coinbase.rest.types.futures_types import (
    CancelPendingFuturesSweepResponse,
    GetCurrentMarginWindowResponse,
    GetFuturesBalanceSummaryResponse,
    GetFuturesPositionResponse,
    GetIntradayMarginSettingResponse,
    ListFuturesPositionsResponse,
    ListFuturesSweepsResponse,
    ScheduleFuturesSweepResponse,
    SetIntradayMarginSettingResponse,
)


def get_futures_balance_summary(self, **kwargs) -> GetFuturesBalanceSummaryResponse:
    """
    **Get Futures Balance Summary**
    _______________________________

    [GET] https://api.coinbase.com/api/v3/brokerage/cfm/balance_summary

    __________

    **Description:**

    Get information on your balances related to `Coinbase Financial Markets <https://www.coinbase.com/fcm>`_ (CFM) futures trading.

    __________

    **Read more on the official documentation:** `Get Futures Balance Summary
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getfcmbalancesummary>`_
    """
    endpoint = f"{API_PREFIX}/cfm/balance_summary"

    return GetFuturesBalanceSummaryResponse(self.get(endpoint, **kwargs))


def list_futures_positions(self, **kwargs) -> ListFuturesPositionsResponse:
    """
    **List Futures Positions**
    __________________________

    [GET] https://api.coinbase.com/api/v3/brokerage/cfm/positions

    __________

    **Description:**

    Get a list of all open positions in CFM futures products.

    __________

    **Read more on the official documentation:** `List Futures Positions
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getfcmpositions>`_
    """
    endpoint = f"{API_PREFIX}/cfm/positions"

    return ListFuturesPositionsResponse(self.get(endpoint, **kwargs))


def get_futures_position(self, product_id: str, **kwargs) -> GetFuturesPositionResponse:
    """
    **Get Futures Position**
    _________________________

    [GET] https://api.coinbase.com/api/v3/brokerage/cfm/positions/{product_id}

    __________

    **Description:**

    Get the position of a specific CFM futures product.

    __________

    **Read more on the official documentation:** `Get Futures Position
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getfcmposition>`_
    """
    endpoint = f"{API_PREFIX}/cfm/positions/{product_id}"

    return GetFuturesPositionResponse(self.get(endpoint, **kwargs))


def schedule_futures_sweep(
    self, usd_amount: str, **kwargs
) -> ScheduleFuturesSweepResponse:
    """
    **Schedule Futures Sweep**
    __________________________

    [POST] https://api.coinbase.com/api/v3/brokerage/cfm/sweeps/schedule

    __________

    **Description:**

    Schedule a sweep of funds from your CFTC-regulated futures account to your Coinbase Inc. USD Spot wallet.

    __________

    **Read more on the official documentation:** `Schedule Futures Sweep
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_schedulefcmsweep>`_
    """
    endpoint = f"{API_PREFIX}/cfm/sweeps/schedule"

    data = {"usd_amount": usd_amount}

    return ScheduleFuturesSweepResponse(self.post(endpoint, data=data, **kwargs))


def list_futures_sweeps(self, **kwargs) -> ListFuturesSweepsResponse:
    """
    **List Futures Sweeps**
    _______________________

    [GET] https://api.coinbase.com/api/v3/brokerage/cfm/sweeps

    __________

    **Description:**

    Get information on your pending and/or processing requests to sweep funds from your CFTC-regulated futures account to your Coinbase Inc. USD Spot wallet.

    __________

    **Read more on the official documentation:** `List Futures Sweeps
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getfcmsweeps>`_
    """
    endpoint = f"{API_PREFIX}/cfm/sweeps"

    return ListFuturesSweepsResponse(self.get(endpoint, **kwargs))


def cancel_pending_futures_sweep(self, **kwargs) -> CancelPendingFuturesSweepResponse:
    """
    **Cancel Pending Futures Sweep**
    ________________________________

    [DELETE] https://api.coinbase.com/api/v3/brokerage/cfm/sweeps

    __________

    **Description:**

    Cancel your pending sweep of funds from your CFTC-regulated futures account to your Coinbase Inc. USD Spot wallet.

    __________

    **Read more on the official documentation:** `Cancel Pending Futures Sweep
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_cancelfcmsweep>`_
    """
    endpoint = f"{API_PREFIX}/cfm/sweeps"

    return CancelPendingFuturesSweepResponse(self.delete(endpoint, **kwargs))


def get_intraday_margin_setting(self, **kwargs) -> GetIntradayMarginSettingResponse:
    """
    **Get Intraday Margin Setting**
    _______________________________

    [GET] https://api.coinbase.com/api/v3/brokerage/cfm/intraday/margin_setting

    __________

    **Description:**

    Get the status of whether your account is opted in to receive increased leverage on futures trades on weekdays from 8am-4pm ET.

    __________

    **Read more on the official documentation:** `Get Intraday Margin Setting
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getintradaymarginsetting>`_
    """
    endpoint = f"{API_PREFIX}/cfm/intraday/margin_setting"

    return GetIntradayMarginSettingResponse(self.get(endpoint, **kwargs))


def get_current_margin_window(
    self, margin_profile_type: str, **kwargs
) -> GetCurrentMarginWindowResponse:
    """
    **Get Current Margin Window**
    ________________________________

    [GET] https://api.coinbase.com/api/v3/brokerage/cfm/intraday/current_margin_window

    __________

    **Description:**

    Get the current margin window to determine whether intraday or overnight margin rates are in effect.

    __________

    **Read more on the official documentation:** `Get Current Margin Window
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getcurrentmarginwindow>`_
    """

    endpoint = f"{API_PREFIX}/cfm/intraday/current_margin_window"

    params = {"margin_profile_type": margin_profile_type}

    return GetCurrentMarginWindowResponse(self.get(endpoint, params=params, **kwargs))


def set_intraday_margin_setting(
    self, setting: str, **kwargs
) -> SetIntradayMarginSettingResponse:
    """
    **Set Intraday Margin Setting**
    ________________________________

    [POST] https://api.coinbase.com/api/v3/brokerage/cfm/intraday/margin_setting

    __________

    **Description:**

    Opt in to receive increased leverage on futures trades on weekdays from 8am-4pm ET.

    __________

    **Read more on the official documentation:** `Set Intraday Margin Setting
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_setintradaymarginsetting>`_
    """

    endpoint = f"{API_PREFIX}/cfm/intraday/margin_setting"

    data = {"setting": setting}

    return SetIntradayMarginSettingResponse(self.post(endpoint, data=data, **kwargs))
