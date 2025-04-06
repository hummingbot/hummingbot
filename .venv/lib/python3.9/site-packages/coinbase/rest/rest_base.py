import logging
import os
from multiprocessing import AuthenticationError
from typing import IO, Any, Dict, Optional, Union

import requests
from requests.exceptions import HTTPError

from coinbase import jwt_generator
from coinbase.api_base import APIBase, get_logger
from coinbase.constants import (
    API_ENV_KEY,
    API_SECRET_ENV_KEY,
    BASE_URL,
    RATE_LIMIT_HEADERS,
    USER_AGENT,
)

logger = get_logger("coinbase.RESTClient")


def handle_exception(response):
    """Raises :class:`HTTPError`, if one occurred.

    :meta private:
    """
    http_error_msg = ""
    reason = response.reason

    if 400 <= response.status_code < 500:
        if (
            response.status_code == 403
            and '"error_details":"Missing required scopes"' in response.text
        ):
            http_error_msg = f"{response.status_code} Client Error: Missing Required Scopes. Please verify your API keys include the necessary permissions."
        else:
            http_error_msg = (
                f"{response.status_code} Client Error: {reason} {response.text}"
            )
    elif 500 <= response.status_code < 600:
        http_error_msg = (
            f"{response.status_code} Server Error: {reason} {response.text}"
        )

    if http_error_msg:
        logger.error(f"HTTP Error: {http_error_msg}")
        raise HTTPError(http_error_msg, response=response)


class RESTBase(APIBase):
    """
    :meta private:
    """

    def __init__(
        self,
        api_key: Optional[str] = os.getenv(API_ENV_KEY),
        api_secret: Optional[str] = os.getenv(API_SECRET_ENV_KEY),
        key_file: Optional[Union[IO, str]] = None,
        base_url=BASE_URL,
        timeout: Optional[int] = None,
        verbose: Optional[bool] = False,
        rate_limit_headers: Optional[bool] = False,
    ):
        super().__init__(
            api_key=api_key,
            api_secret=api_secret,
            key_file=key_file,
            base_url=base_url,
            timeout=timeout,
            verbose=verbose,
        )
        self.rate_limit_headers = rate_limit_headers
        self.session = requests.Session()
        if verbose:
            logger.setLevel(logging.DEBUG)

    def get(
        self, url_path, params: Optional[dict] = None, public=False, **kwargs
    ) -> Dict[str, Any]:
        """
        **GET Request**
        _____________________________

        __________

        **Parameters:**

        - **url_path | (str)** - the URL path
        - **params | Optional ([dict])** - the query parameters
        - **public | (bool)** - flag indicating whether to treat endpoint as public


        """

        params = params or {}

        if kwargs:
            params.update(kwargs)

        return self.prepare_and_send_request(
            "GET", url_path, params, data=None, public=public
        )

    def post(
        self,
        url_path,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        **Authenticated POST Request**
        ______________________________

        __________

         **Parameters:**

        - **url_path | (str)** - the URL path
        - **params | Optional ([dict])** - the query parameters
        - **data | Optional ([dict])** - the request body
        """
        data = data or {}

        if kwargs:
            data.update(kwargs)

        return self.prepare_and_send_request("POST", url_path, params, data)

    def put(
        self,
        url_path,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        **Authenticated PUT Request**
        _____________________________

        __________

        **Parameters:**

        - **url_path | (str)** - the URL path
        - **params | Optional ([dict])** - the query parameters
        - **data | Optional ([dict])** - the request body
        """
        data = data or {}

        if kwargs:
            data.update(kwargs)

        return self.prepare_and_send_request("PUT", url_path, params, data)

    def delete(
        self,
        url_path,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        **Authenticated DELETE Request**
        ________________________________

        __________

        **Parameters:**

        - **url_path | (str)** - the URL path
        - **params | Optional ([dict])** - the query parameters
        - **data | Optional ([dict])** - the request body
        """
        data = data or {}

        if kwargs:
            data.update(kwargs)

        return self.prepare_and_send_request("DELETE", url_path, params, data)

    def prepare_and_send_request(
        self,
        http_method,
        url_path,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        public=False,
    ):
        """
        :meta private:
        """
        if not self.is_authenticated and not public:
            raise AuthenticationError(
                "Unauthenticated request to private endpoint. If you wish to access private endpoints, you must provide your API key and secret when initializing the RESTClient."
            )

        headers = self.set_headers(http_method, url_path)

        if params is not None:
            params = {key: value for key, value in params.items() if value is not None}

        if data is not None:
            data = {key: value for key, value in data.items() if value is not None}

        return self.send_request(http_method, url_path, params, headers, data=data)

    def send_request(self, http_method, url_path, params, headers, data=None):
        """
        :meta private:
        """
        if data is None:
            data = {}

        url = f"https://{self.base_url}{url_path}"

        logger.debug(f"Sending {http_method} request to {url}")

        response = self.session.request(
            http_method,
            url,
            params=params,
            json=data,
            headers=headers,
            timeout=self.timeout,
        )
        handle_exception(response)  # Raise an HTTPError for bad responses

        logger.debug(f"Raw response: {response.json()}")

        response_data = response.json()

        if self.rate_limit_headers:
            response_headers = dict(response.headers)
            specific_headers = {
                key: response_headers.get(key, None) for key in RATE_LIMIT_HEADERS
            }

            response_data = {**response_data, **specific_headers}

        return response_data

    def set_headers(self, method, path):
        """
        :meta private:
        """
        uri = f"{method} {self.base_url}{path}"

        return {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            **(
                {
                    "Authorization": f"Bearer {jwt_generator.build_rest_jwt(uri, self.api_key, self.api_secret)}",
                }
                if self.is_authenticated
                else {}
            ),
        }
