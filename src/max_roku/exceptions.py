class RokuError(Exception):
    """Base exception for Roku controller errors."""
    pass

class RokuConnectionError(RokuError):
    """Raised when the Roku device is unreachable."""
    pass

class RokuCommandError(RokuError):
    """Raised when the Roku rejects a command or returns an unexpected status."""
    pass

class RokuParsingError(RokuError):
    """Raised when the response from the Roku device is malformed or unexpected."""
    pass

class RokuUnexpectedState(RokuError):
    """Raised when the Roku device returns an unexpected state following a sequence of commands."""
    pass