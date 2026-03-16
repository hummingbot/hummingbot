# Binary options controller for Limitless prediction markets.
#
# Public API (import explicitly):
#   from controllers.generic.binary_options.config import BinaryOptionsControllerConfig
#   from controllers.generic.binary_options.controller import BinaryOptionsController


def __getattr__(name):
    """Lazy imports to avoid pulling in heavy hummingbot deps at package init."""
    if name == "BinaryOptionsControllerConfig":
        from .config import BinaryOptionsControllerConfig
        return BinaryOptionsControllerConfig
    if name == "BinaryOptionsController":
        from .controller import BinaryOptionsController
        return BinaryOptionsController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["BinaryOptionsControllerConfig", "BinaryOptionsController"]
