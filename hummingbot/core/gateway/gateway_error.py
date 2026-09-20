from typing import Optional


class GatewayError(ValueError):
    """
    A non-200 response from Gateway, carrying its structured error fields.

    Gateway's HttpError body is::

        {"message": "<detail>", "code": "<machine code>", "error": "<HTTP name>", "name": "<error type>"}

    Those fields used to be flattened into a single ValueError message, so the HTTP
    status was lost and the machine-readable code was only recoverable by matching
    "[code: X]" out of the prose. This type keeps them addressable while rendering
    the exact same string as before, so string-matching callers keep working.

    Subclasses ValueError because that is what Gateway failures have always been.

    :param message: Gateway's detail message (the "message" field), NOT the rendered string
    :param status: HTTP status code of the response
    :param code: Gateway's machine-readable error code (the "code" field)
    :param error_type: Gateway's error type (the "name" field)
    :param http_error: Gateway's generic HTTP error name (the "error" field)
    """

    def __init__(
        self,
        message: str,
        status: Optional[int] = None,
        code: Optional[str] = None,
        error_type: Optional[str] = None,
        http_error: Optional[str] = None,
    ):
        self.message = message
        self.status = status
        self.code = code
        self.error_type = error_type
        self.http_error = http_error
        super().__init__(self._render())

    def _render(self) -> str:
        type_prefix = f"{self.error_type}: " if self.error_type else ""
        name_suffix = f" ({self.http_error})" if self.http_error else ""
        code_suffix = f" [code: {self.code}]" if self.code else ""
        return f"Gateway error: {type_prefix}{self.message}{name_suffix}{code_suffix}"
