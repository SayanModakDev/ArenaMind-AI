class ArenaMindError(Exception):
    """Base class for all ArenaMind errors."""
    pass

class ModelTimeoutError(ArenaMindError):
    """Raised when the LLM times out."""
    pass

class ConfigurationError(ArenaMindError):
    """Raised for configuration issues."""
    pass

class TelemetryFormatError(ArenaMindError):
    """Raised when telemetry data is malformed or invalid."""
    pass

class LanguageDetectionError(ArenaMindError):
    """Raised when language detection fails or returns an unsupported language."""
    pass
