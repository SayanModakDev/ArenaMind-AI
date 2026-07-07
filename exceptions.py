class ArenaMindError(Exception):
    """Base class for all ArenaMind errors."""
    pass

class ModelTimeoutError(ArenaMindError):
    """Raised when the LLM times out."""
    pass

class ConfigurationError(ArenaMindError):
    """Raised for configuration issues."""
    pass
