class SequenceClientError(Exception):
    pass


class SequenceServiceUnavailable(SequenceClientError):
    pass
