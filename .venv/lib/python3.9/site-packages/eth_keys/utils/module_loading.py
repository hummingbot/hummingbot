from importlib import (
    import_module,
)
import operator
from typing import (
    Any,
    Tuple,
)


def import_string(dotted_path: str) -> Any:
    """
    Source: django.utils.module_loading
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError:
        msg = f"{dotted_path} doesn't look like a module path"
        raise ImportError(msg)

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError:
        msg = f'Module "{module_path}" does not define a "{class_name}" attribute/class'
        raise ImportError(msg)


def split_at_longest_importable_path(dotted_path: str) -> Tuple[str, str]:
    num_path_parts = len(dotted_path.split("."))

    for i in range(1, num_path_parts):
        path_parts = dotted_path.rsplit(".", i)
        import_part = path_parts[0]
        remainder = ".".join(path_parts[1:])

        try:
            module = import_module(import_part)
        except ImportError:
            continue

        try:
            operator.attrgetter(remainder)(module)
        except AttributeError:
            raise ImportError(
                f"Unable to derive appropriate import path for {dotted_path}"
            )
        else:
            return import_part, remainder
    else:
        return "", dotted_path
