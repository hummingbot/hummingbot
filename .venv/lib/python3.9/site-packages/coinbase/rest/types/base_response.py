from typing import Any

common_fields = {
    "x-ratelimit-remaining": "rate_limit_remaining",
    "x-ratelimit-reset": "rate_limit_reset",
    "x-ratelimit-limit": "rate_limit_limit",
}


class BaseResponse:
    def __init__(self, **kwargs):
        for field, formattedField in common_fields.items():
            if field in kwargs:
                setattr(self, formattedField, kwargs.pop(field))

        for key in list(kwargs.keys()):
            setattr(self, key, kwargs.pop(key))

    def __getitem__(self, key: str) -> Any:
        return self.__dict__.get(key)

    def __repr__(self):
        return str(self.__dict__)

    def to_dict(self) -> dict:
        dict_response = {}
        for key, value in self.__dict__.items():
            if isinstance(value, BaseResponse):
                dict_response[key] = value.to_dict()
            elif isinstance(value, list):
                dict_response[key] = [
                    item.to_dict() if isinstance(item, BaseResponse) else item
                    for item in value
                ]
            else:
                dict_response[key] = value
        return dict_response
