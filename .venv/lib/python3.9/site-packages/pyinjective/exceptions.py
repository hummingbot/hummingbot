class PyInjectiveError(Exception):
    pass


class ValueTooLargeError(PyInjectiveError):
    pass


class EmptyMsgError(PyInjectiveError):
    pass


class NotFoundError(PyInjectiveError):
    pass


class UndefinedError(PyInjectiveError):
    pass


class DecodeError(PyInjectiveError):
    pass


class ConvertError(PyInjectiveError):
    pass


class SchemaError(PyInjectiveError):
    pass
