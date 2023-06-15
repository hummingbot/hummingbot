import inspect
from typing import Any, Dict, Type

from pydantic import BaseModel


def collect_pydantic_class_annotations(module: Any, base_class: Type) -> Dict[str, Type[Any]]:
    """
    Collects annotations from classes within a specified module.

    :param module: The module from which to collect annotations.
    :param base_class: Base class for annotations collection
    :return: A dictionary containing the collected annotations, where the keys are the annotated attribute names
             and the values are the corresponding types.
    """
    annotations = {}

    # Iterate over all objects in the module
    for name, obj in inspect.getmembers(module):
        # Check if the object is a class and meets the specified conditions
        if (
                inspect.isclass(obj) and
                issubclass(obj, BaseModel) and
                issubclass(obj, base_class) and
                obj != BaseModel
        ):
            # Update the annotations dictionary with the annotations from the class
            annotations.update(obj.__annotations__)

    return annotations
