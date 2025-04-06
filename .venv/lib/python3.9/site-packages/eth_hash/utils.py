import importlib
import logging
import os

from eth_hash.abc import (
    BackendAPI,
)
from eth_hash.backends import (
    SUPPORTED_BACKENDS,
)


def auto_choose_backend() -> BackendAPI:
    env_backend = get_backend_in_environment()

    if env_backend:
        return load_environment_backend(env_backend)
    else:
        return choose_available_backend()


def get_backend_in_environment() -> str:
    return os.environ.get("ETH_HASH_BACKEND", "")


def load_backend(backend_name: str) -> BackendAPI:
    import_path = f"eth_hash.backends.{backend_name}"
    module = importlib.import_module(import_path)

    try:
        backend = module.backend
    except AttributeError as e:
        raise ValueError(
            f"Import of {import_path} failed, because {module} does not have "
            "'backend' attribute"
        ) from e

    if isinstance(backend, BackendAPI):
        return backend
    else:
        raise ValueError(
            f"Import of {import_path} failed, because {backend} is an invalid back end"
        )


def load_environment_backend(env_backend: str) -> BackendAPI:
    if env_backend in SUPPORTED_BACKENDS:
        try:
            return load_backend(env_backend)
        except ImportError as e:
            raise ImportError(
                f"The backend specified in ETH_HASH_BACKEND, '{env_backend}', is not "
                f"installed. Install with `python -m pip install "
                f'"eth-hash[{env_backend}]"`.'
            ) from e
    else:
        raise ValueError(
            f"The backend specified in ETH_HASH_BACKEND, '{env_backend}', is not "
            f"supported. Choose one of: {SUPPORTED_BACKENDS}"
        )


def choose_available_backend() -> BackendAPI:
    for backend in SUPPORTED_BACKENDS:
        try:
            return load_backend(backend)
        except ImportError:
            logging.getLogger("eth_hash").debug(
                f"Failed to import {backend}", exc_info=True
            )
    raise ImportError(
        f"None of these hashing backends are installed: {SUPPORTED_BACKENDS}.\n"
        f'Install with `python -m pip install "eth-hash[{SUPPORTED_BACKENDS[0]}]"`.'
    )
