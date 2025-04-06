import json
import logging
import os
from typing import IO, Optional, Union

from coinbase.constants import API_ENV_KEY, API_SECRET_ENV_KEY


def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


class APIBase(object):
    def __init__(
        self,
        api_key: Optional[str] = os.getenv(API_ENV_KEY),
        api_secret: Optional[str] = os.getenv(API_SECRET_ENV_KEY),
        key_file: Optional[Union[IO, str]] = None,
        base_url=None,
        timeout: Optional[int] = None,
        verbose: Optional[bool] = False,
    ):
        if (api_key is not None or api_secret is not None) and key_file is not None:
            raise Exception(f"Cannot specify both api_key and key_file in constructor")

        if key_file is not None:
            try:
                if isinstance(key_file, str):
                    with open(key_file, "r") as file:
                        key_json = json.load(file)
                else:
                    key_json = json.load(key_file)
                api_key = key_json["name"]
                api_secret = key_json["privateKey"]
            except json.JSONDecodeError as e:
                raise Exception(f"Error decoding JSON: {e}")

        self.is_authenticated = False
        if api_key is not None and api_secret is not None:
            self.api_key = api_key
            self.api_secret = bytes(api_secret, encoding="utf8").decode(
                "unicode_escape"
            )
            self.is_authenticated = True
        elif api_key is not None:
            raise Exception(
                f"Only api_key provided in constructor. Please also provide api_secret"
            )
        elif api_secret is not None:
            raise Exception(
                f"Only api_secret provided in constructor. Please also provide api_key"
            )

        self.base_url = base_url
        self.timeout = timeout
