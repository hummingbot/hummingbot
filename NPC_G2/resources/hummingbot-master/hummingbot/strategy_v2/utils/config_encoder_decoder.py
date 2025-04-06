import json
from decimal import Decimal
from enum import Enum

import yaml


class ConfigEncoderDecoder:

    def __init__(self, *enum_classes):
        self.enum_classes = {enum_class.__name__: enum_class for enum_class in enum_classes}

    def recursive_encode(self, value):
        if isinstance(value, dict):
            return {key: self.recursive_encode(val) for key, val in value.items()}
        elif isinstance(value, list):
            return [self.recursive_encode(val) for val in value]
        elif isinstance(value, Enum):
            return {"__enum__": True, "class": type(value).__name__, "value": value.name}
        elif isinstance(value, Decimal):
            return {"__decimal__": True, "value": str(value)}
        else:
            return value

    def recursive_decode(self, value):
        if isinstance(value, dict):
            if value.get("__enum__"):
                enum_class = self.enum_classes.get(value['class'])
                if enum_class:
                    return enum_class[value["value"]]
            elif value.get("__decimal__"):
                return Decimal(value["value"])
            else:
                return {key: self.recursive_decode(val) for key, val in value.items()}
        elif isinstance(value, list):
            return [self.recursive_decode(val) for val in value]
        else:
            return value

    def encode(self, d):
        return json.dumps(self.recursive_encode(d))

    def decode(self, s):
        return self.recursive_decode(json.loads(s))

    def yaml_dump(self, d, file_path):
        with open(file_path, 'w') as file:
            yaml.dump(self.recursive_encode(d), file)

    def yaml_load(self, file_path):
        with open(file_path, 'r') as file:
            return self.recursive_decode(yaml.safe_load(file))
