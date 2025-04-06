import secrets
import time

import jwt
from cryptography.hazmat.primitives import serialization

from coinbase.constants import BASE_URL


def build_jwt(key_var, secret_var, uri=None) -> str:
    """
    :meta private:
    """
    try:
        private_key_bytes = secret_var.encode("utf-8")
        private_key = serialization.load_pem_private_key(
            private_key_bytes, password=None
        )
    except ValueError as e:
        # This handles errors like incorrect key format
        raise Exception(
            f"{e}\n"
            "Are you sure you generated your key at https://cloud.coinbase.com/access/api ?"
        )

    jwt_data = {
        "sub": key_var,
        "iss": "cdp",
        "nbf": int(time.time()),
        "exp": int(time.time()) + 120,
    }

    if uri:
        jwt_data["uri"] = uri

    jwt_token = jwt.encode(
        jwt_data,
        private_key,
        algorithm="ES256",
        headers={"kid": key_var, "nonce": secrets.token_hex()},
    )

    return jwt_token


def build_rest_jwt(uri, key_var, secret_var) -> str:
    """
    **Build REST JWT**
    __________

    **Description:**

    Builds and returns a JWT token for connecting to the REST API.

    __________

    Parameters:

    - **uri (str)** - Formatted URI for the endpoint (e.g. "GET api.coinbase.com/api/v3/brokerage/accounts") Can be generated using ``format_jwt_uri``
    - **key_var (str)** - The API key
    - **secret_var (str)** - The API key secret
    """
    return build_jwt(key_var, secret_var, uri=uri)


def build_ws_jwt(key_var, secret_var) -> str:
    """
    **Build WebSocket JWT**
    __________

    **Description:**

    Builds and returns a JWT token for connecting to the WebSocket API.

    __________

    Parameters:

    - **key_var (str)** - The API key
    - **secret_var (str)** - The API key secret
    """
    return build_jwt(key_var, secret_var)


def format_jwt_uri(method, path) -> str:
    """
    **Format JWT URI**
    __________

    **Description:**

    Formats method and path into valid URI for JWT generation.

    __________

    Parameters:

    - **method (str)** - The REST request method. E.g. GET, POST, PUT, DELETE
    - **path (str)** - The path of the endpoint. E.g. "/api/v3/brokerage/accounts"

    """
    return f"{method} {BASE_URL}{path}"
