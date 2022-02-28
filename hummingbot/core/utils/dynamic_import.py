import importlib
import inspect
import os

from hummingbot.strategy.lite_strategy_base import LiteStrategyBase
from hummingbot.exceptions import InvalidLiteStrategyFile


def import_lite_strategy_sub_class(lite_file_name: str) -> LiteStrategyBase:
    """
    Imports a Lite strategy class (any classes that derive from LiteStrategyBase) at run-time.
    """
    name = os.path.basename(lite_file_name).split(".")[0]
    spec = importlib.util.spec_from_file_location(name, lite_file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for x in dir(module):
        obj = getattr(module, x)
        if inspect.isclass(obj) and issubclass(obj, LiteStrategyBase) and obj.__name__ != "LiteStrategyBase":
            return obj
    raise InvalidLiteStrategyFile("The file does not contain any LiteStrategyBase derived class.")
