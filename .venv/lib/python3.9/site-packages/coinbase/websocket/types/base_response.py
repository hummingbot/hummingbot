from typing import Any


class BaseResponse:
    def __init__(self, **data):
        for key in list(data.keys()):
            setattr(self, key, data.pop(key))

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
