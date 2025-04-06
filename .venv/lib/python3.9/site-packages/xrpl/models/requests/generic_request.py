"""A generic request that can be used for unsupported requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Type, Union, cast

from typing_extensions import Self

from xrpl.models.exceptions import XRPLModelException
from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(init=False, frozen=True, **KW_ONLY_DATACLASS)
class GenericRequest(Request):
    """
    A request object representing all unsupported requests.

    There is no analog in rippled - this is an xrpl-py-specific model.
    """

    method: RequestMethod = field(default=RequestMethod.GENERIC_REQUEST, init=False)
    """
    This field is required.

    :meta hide-value:
    """

    def __init__(self: Self, **kwargs: Any) -> None:  # noqa: ANN401
        """
        Initializes a GenericRequest.

        Arguments:
            kwargs: All the arguments for the request.
        """
        # initialize all the dataclass stuff
        super().__init__(
            id=(cast(Union[str, int, None], kwargs["id"]) if "id" in kwargs else None),
            method=RequestMethod.GENERIC_REQUEST,
        )
        # pass in all the kwargs into the object (so self.key == value)
        for key, value in kwargs.items():
            object.__setattr__(self, key, value)

    @classmethod
    def from_dict(cls: Type[Self], value: Dict[str, Any]) -> Self:
        """
        Construct a new GenericRequest from a dictionary of parameters. Also converts
        from JSON and WS formatting.

        Args:
            value: The value to construct the GenericRequest from.

        Returns:
            A new GenericRequest object, constructed using the given parameters.

        Raises:
            XRPLModelException: If the dictionary provided is invalid.
        """
        if "command" in value:  # websocket formatting
            value["method"] = value["command"]
            del value["command"]

        elif "method" in value:  # JSON RPC formatting
            if "params" in value:  # actual JSON RPC formatting
                value = {
                    "api_version": value["api_version"],
                    "method": value["method"],
                    **value["params"],
                }
            # else is the internal request formatting

        else:
            raise XRPLModelException("Must have a command or a method in a request")

        return cls(**value)

    def to_dict(self: Self) -> Dict[str, Any]:
        """
        Returns the dictionary representation of a GenericRequest.

        Returns:
            The dictionary representation of a GenericRequest.
        """
        # uses self.__dict__ instead of self.__dataclass_fields__.keys(), which is what
        # the other models do, because this model doesn't have any dataclass fields
        dict = {
            key: self._to_dict_elem(getattr(self, key))
            for key in self.__dict__
            if getattr(self, key) is not None
        }

        if "command" in dict:
            dict["method"] = dict["command"]
            del dict["command"]

        return dict
