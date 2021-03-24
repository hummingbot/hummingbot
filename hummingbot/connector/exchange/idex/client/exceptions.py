#
#
# class RemoteApiError(Exception):
#
#     code: str = None
#     message: str = None
#
#     def __init__(self, code: str, message: str):
#         self.code = code
#         self.message = message
#
#     def __str__(self):
#         return f"{self.code}: {self.message}"
#
#     def __repr__(self):
#         return f"<ApiError {self.code}: {self.message}>"
#
#
# class TooManyRequestError(Exception):
#     pass
#
#
# class ResourceNotFoundError(Exception):
#     pass
