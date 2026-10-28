"""Access to the other modules. Mocks today, real modules one by one — same interface."""

from .base import Clients
from .mocks import MockClients


def get_clients(use_mocks: bool, dataset: str = "synthetic", real: list[str] | None = None) -> Clients:
    """real: modules called for real (m1, m2, m7...), each with the mock as fallback."""
    if real:
        from .real import HybridClients
        return HybridClients(real, dataset)
    if use_mocks:
        return MockClients(dataset)
    from .http import HttpClients
    return HttpClients()
