import inspect
from io import (
    UnsupportedOperation,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Union,
)

from web3.exceptions import (
    Web3AttributeError,
    Web3ValidationError,
)
from web3.module import (
    Module,
)

if TYPE_CHECKING:
    from web3.main import BaseWeb3  # noqa: F401


def _validate_init_params_and_return_if_found(module_class: Any) -> List[str]:
    init_params_raw = list(inspect.signature(module_class.__init__).parameters)
    module_init_params = [
        param for param in init_params_raw if param not in ["self", "args", "kwargs"]
    ]

    if len(module_init_params) > 1:
        raise UnsupportedOperation(
            "A module class may accept a single `Web3` instance as the first "
            "argument of its __init__() method. More than one argument found for "
            f"{module_class.__name__}: {module_init_params}"
        )

    return module_init_params


def attach_modules(
    parent_module: Union["BaseWeb3", "Module"],
    module_definitions: Dict[str, Any],
    w3: Optional[Union["BaseWeb3", "Module"]] = None,
) -> None:
    for module_name, module_info in module_definitions.items():
        module_info_is_list_like = isinstance(module_info, Sequence)

        module_class = module_info[0] if module_info_is_list_like else module_info

        if hasattr(parent_module, module_name):
            raise Web3AttributeError(
                f"Cannot set {parent_module} module named '{module_name}'. "
                " The web3 object already has an attribute with that name"
            )

        # The parent module is the ``Web3`` instance on first run of the loop and w3 is
        # None. Thus, set w3 to the parent_module. The import needs to happen locally
        # due to circular import issues.
        if w3 is None:
            from web3 import (
                AsyncWeb3,
                Web3,
            )

            if isinstance(parent_module, Web3) or isinstance(parent_module, AsyncWeb3):
                w3 = parent_module

        module_init_params = _validate_init_params_and_return_if_found(module_class)
        if len(module_init_params) == 1:
            # Modules that need access to the ``Web3`` instance may accept the
            # instance as the first arg in their ``__init__()`` method. This is the
            # case for any module that inherits from ``web3.module.Module``.
            # e.g. def __init__(self, w3):
            setattr(parent_module, module_name, module_class(w3))
        else:
            # Modules need not take in a ``Web3`` instance in
            # their ``__init__()`` if not needed
            setattr(parent_module, module_name, module_class())

        if module_info_is_list_like:
            if len(module_info) == 2:
                submodule_definitions = module_info[1]
                module = getattr(parent_module, module_name)
                attach_modules(module, submodule_definitions, w3)
            elif len(module_info) != 1:
                raise Web3ValidationError(
                    "Module definitions can only have 1 or 2 elements."
                )
