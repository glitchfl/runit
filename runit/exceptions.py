class RunitError(Exception):
    """Base exception for all runit errors."""


class ConfigError(RunitError):
    """Invalid or malformed config."""
