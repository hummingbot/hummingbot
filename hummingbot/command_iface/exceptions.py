class CommandError(Exception):
    """Base exception for command execution errors"""
    pass


class AuthenticationError(CommandError):
    """Raised when authentication fails"""
    pass


class CommandDisabledError(CommandError):
    """Raised when trying to execute a disabled command"""
    pass
