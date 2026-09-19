"""QuanTrade institutional runtime kernel.

P1.1 legacy portfolio/risk adapters intentionally remain outside the package
root exports so the core kernel stays dependency-light.
"""

from .service import InstitutionalKernel, InvalidTransition, ImmutableRecordError

__all__ = ["InstitutionalKernel", "InvalidTransition", "ImmutableRecordError"]
