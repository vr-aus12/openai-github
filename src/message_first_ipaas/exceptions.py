class IPaaSError(Exception):
    """Base class for iPaaS domain errors."""


class ValidationError(IPaaSError):
    """Raised when a payload violates a message contract."""


class RegistrationError(IPaaSError):
    """Raised when duplicate or invalid registry operations are attempted."""


class RoutingError(IPaaSError):
    """Raised when integration map execution cannot be completed."""
