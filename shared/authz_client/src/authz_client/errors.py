class AuthzClientError(Exception):
    pass


class AuthzServiceUnavailable(AuthzClientError):
    pass
