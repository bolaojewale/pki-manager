"""Custom exceptions for PKI operations."""


class PKIError(Exception):
    """Base exception for all PKI-related errors."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON response."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class PKINotInitializedError(PKIError):
    """PKI structure has not been initialized."""

    def __init__(self, message: str = "PKI has not been initialized. Run pki_init first."):
        super().__init__(message)


class PKIAlreadyInitializedError(PKIError):
    """PKI structure already exists."""

    def __init__(self, message: str = "PKI already initialized.", details: dict | None = None):
        super().__init__(message, details)


class RootCAOfflineError(PKIError):
    """Root CA private key is offline/unavailable."""

    def __init__(self, message: str = "Root CA private key is offline."):
        super().__init__(message)


class RootCAOnlineError(PKIError):
    """Root CA private key is still online when expected offline."""

    def __init__(self, message: str = "Root CA private key is still online."):
        super().__init__(message)


class CertificateNotFoundError(PKIError):
    """Certificate file not found."""

    def __init__(self, service_name: str, path: str | None = None):
        details = {"service_name": service_name}
        if path:
            details["path"] = path
        super().__init__(f"Certificate not found for service: {service_name}", details)


class ServiceNotFoundError(PKIError):
    """Service directory not found."""

    def __init__(self, service_name: str):
        super().__init__(
            f"Service not found: {service_name}",
            {"service_name": service_name},
        )


class ServiceAlreadyExistsError(PKIError):
    """Service already has a certificate."""

    def __init__(self, service_name: str):
        super().__init__(
            f"Service already exists: {service_name}",
            {"service_name": service_name},
        )


class CSRNotFoundError(PKIError):
    """CSR file not found."""

    def __init__(self, path: str):
        super().__init__(f"CSR file not found: {path}", {"path": path})


class InvalidCSRError(PKIError):
    """CSR file is invalid or malformed."""

    def __init__(self, message: str = "Invalid CSR file"):
        super().__init__(message)


class KeyGenerationError(PKIError):
    """Error generating cryptographic key."""

    def __init__(self, message: str, curve: str | None = None):
        details = {}
        if curve:
            details["curve"] = curve
        super().__init__(message, details)


class CertificateGenerationError(PKIError):
    """Error generating certificate."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, details)


class CertificateExpiredError(PKIError):
    """Certificate has expired."""

    def __init__(self, service_name: str, expired_days: int):
        super().__init__(
            f"Certificate for {service_name} expired {abs(expired_days)} days ago",
            {"service_name": service_name, "expired_days": expired_days},
        )


class BackupError(PKIError):
    """Error during backup operation."""

    def __init__(self, message: str, path: str | None = None):
        details = {}
        if path:
            details["path"] = path
        super().__init__(message, details)


class ConfirmationRequiredError(PKIError):
    """Operation requires explicit confirmation."""

    def __init__(self, operation: str):
        super().__init__(
            f"Destructive operation '{operation}' requires confirm_destructive=true",
            {"operation": operation, "requires_confirmation": True},
        )


class SecureDeletionError(PKIError):
    """Error during secure file deletion."""

    def __init__(self, path: str, message: str = "Failed to securely delete file"):
        super().__init__(message, {"path": path})
