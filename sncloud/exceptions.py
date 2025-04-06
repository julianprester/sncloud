class ApiError(Exception):
    pass

class AuthenticationError(ApiError):
    pass

class FileFolderNotFound(ApiError):
    pass