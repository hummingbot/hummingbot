import os
from typing import (
    Type,
)

from eth_keys.utils.module_loading import (
    import_string,
)

from .base import (
    BaseECCBackend,
)
from .coincurve import (
    CoinCurveECCBackend,
    is_coincurve_available,
)
from .native import (
    NativeECCBackend,
)


def get_default_backend_class() -> str:
    if is_coincurve_available():
        return "eth_keys.backends.CoinCurveECCBackend"
    else:
        return "eth_keys.backends.NativeECCBackend"


def get_backend_class(import_path: str = None) -> Type[BaseECCBackend]:
    if import_path is None:
        import_path = os.environ.get(
            "ECC_BACKEND_CLASS",
            get_default_backend_class(),
        )
    return import_string(import_path)


def get_backend(import_path: str = None) -> BaseECCBackend:
    backend_class = get_backend_class(import_path)
    return backend_class()
