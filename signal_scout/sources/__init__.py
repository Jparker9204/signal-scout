"""Source registry. Add a new plugin by subclassing Source and registering it here."""

from .base import Source
from .crypto import CryptoMoversSource
from .jobs import JobsSource

REGISTRY: dict[str, type[Source]] = {
    CryptoMoversSource.name: CryptoMoversSource,
    JobsSource.name: JobsSource,
}

__all__ = ["REGISTRY", "Source", "CryptoMoversSource", "JobsSource"]
