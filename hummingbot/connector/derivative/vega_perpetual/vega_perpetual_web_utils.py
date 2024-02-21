from decimal import Decimal
from typing import Callable, Dict, Optional

import hummingbot.connector.derivative.vega_perpetual.vega_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class VegaPerpetualRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = (
            "application/json" if request.method == RESTMethod.POST else "application/x-www-form-urlencoded"
        )
        return request


def rest_url(path_url: str, domain: str = "vega_perpetual", api_version: str = CONSTANTS.API_VERSION):
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == "vega_perpetual" else CONSTANTS.TESTNET_BASE_URL
    return base_url + "api/" + api_version + path_url


def _rest_url(path_url: str, base: str, api_version: str = CONSTANTS.API_VERSION):
    base_url = base
    return base_url + "api/" + api_version + path_url


def short_url(path_url: str, domain: str = "vega_perpetual"):
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == "vega_perpetual" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def _short_url(path_url: str, base: str):
    base_url = base
    return base_url + path_url


def wss_url(endpoint: str, domain: str = "vega_perpetual", api_version: str = CONSTANTS.API_VERSION):
    base_ws_url = CONSTANTS.PERPETUAL_WS_URL if domain == "vega_perpetual" else CONSTANTS.TESTNET_WS_URL
    return base_ws_url + "api/" + api_version + endpoint


def _wss_url(endpoint: str, base: str, api_version: str = CONSTANTS.API_VERSION):
    base_ws_url = process_ws_url_from_https(base)
    return base_ws_url + "api/" + api_version + endpoint


def explorer_url(path_url: str, domain: str = "vega_perpetual"):  # pragma: no cover
    base_url = CONSTANTS.PERPETAUL_EXPLORER_URL if domain == "vega_perpetual" else CONSTANTS.TESTNET_EXPLORER_URL
    return base_url + path_url


def grpc_url(domain: str = "vega_perpetual"):
    base_url = CONSTANTS.PERPETUAL_GRPC_URL if domain == "vega_perpetual" else CONSTANTS.TESTNET_GRPC_URL
    return base_url


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        domain: str = CONSTANTS.DOMAIN,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain,
    ))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
            VegaPerpetualRESTPreProcessor(),
        ])
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[VegaPerpetualRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DOMAIN,
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=rest_url(path_url=CONSTANTS.SERVER_TIME_PATH_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.ALL_URLS,
    )

    # server time is in nanoseconds, convert to seconds
    server_time = hb_time_from_vega(response["timestamp"])

    return server_time


def hb_time_from_vega(timestamp: str) -> float:
    return float(int(timestamp) * 1e-9)


def calculate_fees(fees: Dict[str, any], quantum: Decimal, is_taker: bool) -> Decimal:
    # discounts
    infraFeeRefererDiscount = int(fees.get("infrastructureFeeRefererDiscount", 0))
    infraFeeVolumeDiscount = int(fees.get("infrastructureFeeVolumeDiscount", 0))

    liquidityFeeRefererDiscount = int(fees.get("liquidityFeeRefererDiscount", 0))
    liquidityFeeVolumeDiscount = int(fees.get("liquidityFeeVolumeDiscount", 0))

    makerFeeRefererDiscount = int(fees.get("makerFeeRefererDiscount", 0))
    makerFeeVolumeDiscount = int(fees.get("makerFeeVolumeDiscount", 0))

    # fees
    infraFee = int(fees.get("infrastructureFee", 0))
    liquidityFee = int(fees.get("liquidityFee", 0))
    makerFee = int(fees.get("makerFee", 0))

    # figure out actual fees
    calcInfraFee = max(0, infraFee - infraFeeRefererDiscount - infraFeeVolumeDiscount)
    calcLiquidityFee = max(0, liquidityFee - liquidityFeeRefererDiscount - liquidityFeeVolumeDiscount)
    calcMakerFee = max(0, makerFee - makerFeeRefererDiscount - makerFeeVolumeDiscount)
    # check as rebates
    if not is_taker:
        calcInfraFee = 0
        calcLiquidityFee = 0
        calcMakerFee = min(0, -1 * (makerFee - makerFeeRefererDiscount - makerFeeVolumeDiscount))

    fee = Decimal(calcInfraFee + calcLiquidityFee + calcMakerFee) / quantum
    return fee


def get_account_type(account_type: any) -> Optional[str]:
    VegaIntAccountType = {
        0: "ACCOUNT_TYPE_UNSPECIFIED",
        1: "ACCOUNT_TYPE_INSURANCE",
        2: "ACCOUNT_TYPE_SETTLEMENT",
        3: "ACCOUNT_TYPE_MARGIN",
        4: "ACCOUNT_TYPE_GENERAL",
    }
    if isinstance(account_type, int) and (account_type in VegaIntAccountType.keys()):
        account_type = VegaIntAccountType[account_type]
    return account_type


def process_ws_url_from_https(url: str) -> str:
    return f"{url}".replace("https", "wss")
