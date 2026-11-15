class DGGraphicsAnalyzerError(Exception):
    """Base exception for expected application-domain failures."""


class ConfigurationError(DGGraphicsAnalyzerError):
    """Raised when application configuration is invalid."""


class ProjectValidationError(DGGraphicsAnalyzerError):
    """Raised when a project model contains invalid values."""


class MediaError(DGGraphicsAnalyzerError):
    """Base exception for media inspection and decoding failures."""


class MediaOpenError(MediaError):
    """Raised when a media source cannot be opened or decoded."""


class ExternalToolNotFoundError(MediaError):
    """Raised when a required external executable cannot be located."""


class ExternalToolError(MediaError):
    """Raised when FFmpeg or FFprobe returns an error."""
