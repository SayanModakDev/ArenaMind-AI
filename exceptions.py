class ArenaMindError(Exception):
    """Base class for all ArenaMind errors."""

class ModelTimeoutError(ArenaMindError):
    """Raised when the LLM times out."""

class ConfigurationError(ArenaMindError):
    """Raised for configuration issues."""

class TelemetryFormatError(ArenaMindError):
    """Raised when telemetry data is malformed or invalid."""

class LanguageDetectionError(ArenaMindError):
    """Raised when language detection fails or returns an unsupported language."""
