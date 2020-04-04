from typing import Optional


class ApiException(Exception):
    code: int = 500
    message: str = "Internal Server Error"

    def __init__(self, message: Optional[str] = None, code: Optional[int] = None):
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code


class BadRequest(ApiException):
    code = 400
    message = "Bad Request"


class AuthenticationRequired(ApiException):
    code = 401
    message = "Authentication Required"


class UnprocessableEntity(ApiException):
    code = 422
    message = "Unprocessable Entity"
