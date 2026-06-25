"""GSAB utilities."""

from .encryption import Encryptor

# Note: `quota_monitor.QuotaMonitor` is intentionally not exported yet — it's an unused
# seed for the planned rate-aware batching layer, not part of the public surface.
__all__ = ["Encryptor"]
