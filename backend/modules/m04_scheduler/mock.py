"""Week-1 mock of M4: fixed data in the agreed shape. Replace by service.py, same signatures."""

def schedule(req: dict) -> dict:
    return {"result": {"todo": "M4 schedule mock"}, "mocked": True}

def calendar(req: dict) -> dict:
    return {"result": {"todo": "M4 calendar mock"}, "mocked": True}
