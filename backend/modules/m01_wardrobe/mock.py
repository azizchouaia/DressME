"""Week-1 mock of M1: fixed data in the agreed shape. Replace by service.py, same signatures."""

def classify(req: dict) -> dict:
    return {"result": {"todo": "M1 classify mock"}, "mocked": True}

def similar(req: dict) -> dict:
    return {"result": {"todo": "M1 similar mock"}, "mocked": True}

def items(req: dict) -> dict:
    return {"result": {"todo": "M1 items mock"}, "mocked": True}
