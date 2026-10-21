"""Access to the other modules. Mocks today, real HTTP calls later — same interface."""

from .base import Clients
from .mocks import MockClients


def get_clients(use_mocks: bool, dataset: str = "synthetic") -> Clients:
    if use_mocks:
        return MockClients(dataset)
    from .http import HttpClients
    return HttpClients()
