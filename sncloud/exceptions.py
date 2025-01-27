class ApiError(Exception):
    pass

class AuthenticationError(ApiError):
    pass