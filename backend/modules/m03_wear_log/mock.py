"""Week-1 mock of M3: fixed data in the agreed shape. Replace by service.py, same signatures."""

def worn(req: dict) -> dict:
    return {"result": {"todo": "M3 worn mock"}, "mocked": True}

def stats(req: dict) -> dict:
    return {"result": {"todo": "M3 stats mock"}, "mocked": True}
