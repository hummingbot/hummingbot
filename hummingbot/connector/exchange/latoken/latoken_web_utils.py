# import inspect
# from types import FrameType
from decimal import Decimal
from typing import Any, Callable, Dict, Optional  # , cast

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
from hummingbot.connector.exchange.latoken.latoken_stomper import LatokenConnectionsFactory
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

# Order States for REST
ORDER_STATE = {
    # "PENDING": OrderState.PENDING_CREATE,
    "ORDER_STATUS_PLACED": OrderState.OPEN,
    "ORDER_STATUS_CLOSED": OrderState.FILLED,
    "ORDER_STATUS_FILLED": OrderState.PARTIALLY_FILLED,
    # "PENDING_CANCEL": OrderState.OPEN,
    "ORDER_STATUS_CANCELLED": OrderState.CANCELED,
    "ORDER_STATUS_REJECTED": OrderState.FAILED,
    # "EXPIRED": OrderState.FAILED,
}


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Latoken domain to connect to. Public default is "com"
    :return: the full URL to the endpoint
    """
    endpoint = CONSTANTS.DOMAIN_TO_ENDPOINT[domain]
    return CONSTANTS.REST_URL.format(endpoint, domain) + CONSTANTS.REST_API_VERSION + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the Latoken domain to connect to. Public default is "com"
    :return: the full URL to the endpoint
    """
    endpoint = CONSTANTS.DOMAIN_TO_ENDPOINT[domain]
    return CONSTANTS.REST_URL.format(endpoint, domain) + CONSTANTS.REST_API_VERSION + path_url


def ws_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the Latoken domain to connect to. Public default is "com"
    :return: the full URL to the endpoint
    """
    endpoint = CONSTANTS.DOMAIN_TO_ENDPOINT[domain]
    return CONSTANTS.WSS_URL.format(endpoint, domain)


# Order States for WS
def get_order_status_ws(change_type: str, status: str, quantity: Decimal, filled: Decimal, delta_filled: Decimal):

    order_state = None  # None is not used to update order in hbot order mgmt
    if status == "ORDER_STATUS_PLACED":
        if change_type == 'ORDER_CHANGE_TYPE_PLACED':
            order_state = OrderState.OPEN
        elif change_type == "ORDER_CHANGE_TYPE_FILLED" and delta_filled > Decimal(0):
            order_state = OrderState.FILLED if quantity == filled else OrderState.PARTIALLY_FILLED
        # elif change_type == 'ORDER_CHANGE_TYPE_UNCHANGED':
        #     order_state = None
    # elif status == "ORDER_STATUS_CLOSED":
    #     if change_type == "ORDER_CHANGE_TYPE_CLOSED" or change_type == "ORDER_CHANGE_TYPE_UNCHANGED":
    #         order_state = None  # don't handle this for now, this is a confirmation from Latoken for fill
    elif status == "ORDER_STATUS_CANCELLED":
        if change_type == 'ORDER_CHANGE_TYPE_PLACED':
            order_state = OrderState.PENDING_CANCEL
        if change_type == "ORDER_CHANGE_TYPE_CANCELLED":
            order_state = OrderState.CANCELED
        # elif change_type == 'ORDER_CHANGE_TYPE_UNCHANGED':
        #     order_state = None
    elif status == "ORDER_STATUS_REJECTED":
        if change_type == "ORDER_CHANGE_TYPE_REJECTED":
            order_state = OrderState.FAILED
    elif status == "ORDER_STATUS_NOT_PROCESSED":
        if change_type == "ORDER_CHANGE_TYPE_REJECTED":
            order_state = OrderState.FAILED
    elif status == "ORDER_STATUS_UNKNOWN":
        if change_type == "ORDER_CHANGE_TYPE_REJECTED":
            order_state = OrderState.FAILED

    return order_state


def get_order_status_rest(status: str, filled: Decimal, quantity: Decimal):
    new_state = ORDER_STATE[status]
    if new_state == OrderState.FILLED and quantity != filled:
        new_state = OrderState.PARTIALLY_FILLED
    return new_state


def create_full_mapping(ticker_list, currency_list, pair_list):
    ticker_dict = {f"{ticker['baseCurrency']}/{ticker['quoteCurrency']}": ticker for ticker in ticker_list}
    # pair_dict = {f"{pair['baseCurrency']}/{pair['quoteCurrency']}": pair for pair in pair_list}
    currency_dict = {currency["id"]: currency for currency in currency_list}

    for pt in pair_list:
        key = f"{pt['baseCurrency']}/{pt['quoteCurrency']}"
        is_valid = key in ticker_dict
        pt["is_valid"] = is_valid
        pt["id"] = ticker_dict[key] if is_valid else {"id": key}
        base_id = pt["baseCurrency"]
        if base_id in currency_dict:
            pt["baseCurrency"] = currency_dict[base_id]
        quote_id = pt["quoteCurrency"]
        if quote_id in currency_dict:
            pt["quoteCurrency"] = currency_dict[quote_id]

    return pair_list


def get_book_side(book):
    return tuple((row['price'], row['quantity']) for row in book)


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,) -> WebAssistantsFactory:
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain,
    ))
    api_factory = WebAssistantsFactory(
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ])
    api_factory._connections_factory = LatokenConnectionsFactory()
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor() -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory()
    api_factory._connections_factory = LatokenConnectionsFactory()
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def api_request(path: str,
                      api_factory: Optional[WebAssistantsFactory] = None,
                      throttler: Optional[AsyncThrottler] = None,
                      time_synchronizer: Optional[TimeSynchronizer] = None,
                      domain: str = CONSTANTS.DEFAULT_DOMAIN,
                      params: Optional[Dict[str, Any]] = None,
                      data: Optional[Dict[str, Any]] = None,
                      method: RESTMethod = RESTMethod.GET,
                      is_auth_required: bool = False,
                      return_err: bool = False,
                      limit_id: Optional[str] = None,
                      timeout: Optional[float] = None,
                      headers=None):
    if headers is None:
        headers = {}

    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    # If api_factory is not provided a default one is created
    # The default instance has no authentication capabilities and all authenticated requests will fail
    api_factory = api_factory or build_api_factory(
        throttler=throttler,
        time_synchronizer=time_synchronizer,
        domain=domain,
    )
    rest_assistant = await api_factory.get_rest_assistant()

    local_headers = {"Content-Type": "application/json"}
    local_headers.update(headers)
    url = private_rest_url(path, domain=domain) if is_auth_required else public_rest_url(path, domain=domain)
    # top_level_function_name = cast(FrameType, cast(FrameType, inspect.currentframe()).f_back).f_code.co_name
    # print(f"top_level_function_name={top_level_function_name} limit_id={limit_id} url={url}")
    request = RESTRequest(
        method=method,
        url=url,
        params=params,
        data=data,
        headers=local_headers,
        is_auth_required=is_auth_required,
        throttler_limit_id=limit_id if limit_id else path
    )

    async with throttler.execute_task(limit_id=limit_id if limit_id else path):
        response = await rest_assistant.call(request=request, timeout=timeout)

        if response.status != 200 and not return_err:
            raise IOError(f"Error for Response: {response}.")

        return await response.json()


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    api_factory = build_api_factory_without_time_synchronizer_pre_processor()
    response = await api_request(
        path=CONSTANTS.PING_PATH_URL,
        api_factory=api_factory,
        throttler=throttler,
        domain=domain,
        method=RESTMethod.GET,
        return_err=True
    )
    return response["serverTime"]
