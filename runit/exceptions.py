class RunitError(Exception):
    """Base exception for all runit errors."""


class ConfigNotFoundError(RunitError):
    """No runit.yaml found in the current directory."""


class ConfigError(RunitError):
    """Invalid or malformed runit.yaml."""


class CommandNotFoundError(RunitError):
    """Command name not found in runit.yaml."""
