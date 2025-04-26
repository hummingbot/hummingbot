import json
from typing import Callable, Dict, Any, Optional

from hummingbot.connector.exchange.swaphere import swaphere_constants as CONSTANTS
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTResponse
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = None) -> str:
    """
    Creates a full URL for public REST endpoints
    :param path_url: the specific endpoint path
    :param domain: the domain to connect to
    :return: the full URL for public endpoint
    """
    return CONSTANTS.SWAPHERE_BASE_URL + path_url


def private_rest_url(path_url: str, domain: str = None) -> str:
    """
    Creates a full URL for private REST endpoints
    :param path_url: the specific endpoint path
    :param domain: the domain to connect to
    :return: the full URL for private endpoint
    """
    return CONSTANTS.SWAPHERE_BASE_URL + path_url


async def api_request(
    path: str,
    api_factory: WebAssistantsFactory,
    rest_method: RESTMethod = RESTMethod.GET,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    is_auth_required: bool = False,
) -> Dict[str, Any]:
    """
    Makes an API request to Swaphere
    :param path: the path for the API endpoint
    :param api_factory: the web assistant factory to create the REST assistant
    :param rest_method: the HTTP method
    :param params: additional parameters for the request
    :param data: data to include in the request body
    :param is_auth_required: whether authentication is required
    :return: the response from the API
    """
    rest_assistant: RESTAssistant = await api_factory.get_rest_assistant()
    
    if is_auth_required:
        url = private_rest_url(path)
    else:
        url = public_rest_url(path)
        
    response = await rest_assistant.execute_request(
        method=rest_method,
        url=url,
        params=params,
        data=json.dumps(data) if data else None,
        headers={"Content-Type": "application/json"} if data else None,
    )
    
    response_json = await response.json()
    
    return response_json 