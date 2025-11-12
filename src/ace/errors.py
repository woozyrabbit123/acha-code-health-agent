"""ACE error taxonomy and exit codes."""

from enum import IntEnum


class ExitCode(IntEnum):
    """
    Uniform exit codes for ACE CLI.

    Exit codes follow common Unix conventions:
    - 0: Success
    - 1: Operational/runtime error
    - 2: Policy violation/safety check failed
    - 3: Invalid arguments or configuration
    """

    SUCCESS = 0
    OPERATIONAL_ERROR = 1
    POLICY_DENY = 2
    INVALID_ARGS = 3


class ACEError(Exception):
    """Base exception for all ACE errors."""

    def __init__(self, message: str, exit_code: ExitCode = ExitCode.OPERATIONAL_ERROR):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class OperationalError(ACEError):
    """Runtime errors: file not found, parse failures, etc."""

    def __init__(self, message: str):
        super().__init__(message, ExitCode.OPERATIONAL_ERROR)


class PolicyDenyError(ACEError):
    """Policy violations: dirty git tree, high-risk edits denied, etc."""

    def __init__(self, message: str):
        super().__init__(message, ExitCode.POLICY_DENY)


class InvalidArgsError(ACEError):
    """Invalid CLI arguments or configuration."""

    def __init__(self, message: str):
        super().__init__(message, ExitCode.INVALID_ARGS)


def format_error(error: Exception, verbose: bool = False) -> str:
    """
    Format error for CLI output.

    Args:
        error: Exception to format
        verbose: If True, include stack trace

    Returns:
        Formatted error message

    Examples:
        >>> err = OperationalError("File not found: test.py")
        >>> format_error(err)
        'Error: File not found: test.py'
    """
    if isinstance(error, ACEError):
        return f"Error: {error.message}"

    # Generic exception handling
    if verbose:
        import traceback
        return f"Unexpected error: {error}\n{traceback.format_exc()}"

    return f"Unexpected error: {error}"
