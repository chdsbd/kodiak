class ApiException(Exception):
    code: int = 500
    message: str = "Internal Server Error"


class AuthenticationRequired(ApiException):
    code = 401
    message = "Authentication Required"
